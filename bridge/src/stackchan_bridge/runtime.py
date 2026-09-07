"""Composition root for the two Bridge network surfaces."""

from __future__ import annotations

import asyncio
import logging
import re
import signal
import threading
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from ipaddress import ip_address
from socket import getaddrinfo, gethostname
from tempfile import NamedTemporaryFile
from types import FrameType

import httpx
from fastapi import FastAPI
from ifaddr import get_adapters
from uvicorn import Config, Server
from uvicorn.server import HANDLED_SIGNALS

from stackchan_bridge.audio.codec import OpusCodec, OpusCodecConfig
from stackchan_bridge.audio.debug_store import DebugAudioStore
from stackchan_bridge.audio.input import VoiceAudioInputHandler
from stackchan_bridge.audio.output import AudioOutputStreamer
from stackchan_bridge.audio.vad import RmsVadConfig
from stackchan_bridge.captures.coordinator import CaptureCoordinator
from stackchan_bridge.captures.store import CaptureStore
from stackchan_bridge.config import BridgeSettings
from stackchan_bridge.control.application import create_control_app
from stackchan_bridge.device_gateway.application import (
    DeviceGatewayConfig,
    DeviceRegistry,
    create_device_gateway_app,
)
from stackchan_bridge.discovery.mdns import MdnsAdvertiser
from stackchan_bridge.hermes.client import HermesClient, HermesClientConfig
from stackchan_bridge.hermes.segmenter import SpeechSegmenterConfig
from stackchan_bridge.observability.logging import configure_bridge_logging
from stackchan_bridge.observability.metrics import BridgeMetrics
from stackchan_bridge.security.tokens import hash_device_token
from stackchan_bridge.stt.adapters import (
    FasterWhisperSttAdapter,
    GenericHttpSttAdapter,
    MockSttAdapter,
    SttAdapter,
)
from stackchan_bridge.tts.adapters import (
    GenericHttpWavTtsAdapter,
    MockTtsAdapter,
    OpenAICompatibleTtsAdapter,
    TtsAdapter,
    VoicevoxTtsAdapter,
)
from stackchan_bridge.tts.pipeline import SegmentPlaybackPipeline
from stackchan_bridge.turns.coordinator import TurnCoordinator
from stackchan_bridge.turns.events import TurnEventHandler
from stackchan_bridge.turns.notifications import (
    DeviceTurnFailureNotifier,
    DeviceTurnProgressNotifier,
)
from stackchan_bridge.turns.service import VoiceTurnService
from stackchan_bridge.turns.vision import VisionTurnService

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class BridgeRuntime:
    settings: BridgeSettings = field(repr=False)
    gateway: FastAPI
    control: FastAPI
    registry: DeviceRegistry
    capture_store: CaptureStore
    debug_audio_store: DebugAudioStore
    capture_coordinator: CaptureCoordinator
    vision_turn_service: VisionTurnService
    turn_coordinator: TurnCoordinator
    voice_turn_service: VoiceTurnService
    failure_notifier: DeviceTurnFailureNotifier
    progress_notifier: DeviceTurnProgressNotifier
    audio_input_handler: VoiceAudioInputHandler
    event_handler: TurnEventHandler
    stt_adapter: SttAdapter
    tts_adapter: TtsAdapter
    hermes_client: HermesClient
    hermes_http_client: httpx.AsyncClient = field(repr=False)
    provider_http_clients: tuple[httpx.AsyncClient, ...] = field(repr=False)
    mdns_advertiser: MdnsAdvertiser | None
    metrics: BridgeMetrics

    async def aclose(self) -> None:
        await asyncio.gather(
            self.hermes_http_client.aclose(),
            *(client.aclose() for client in self.provider_http_clients),
        )


def build_runtime(
    settings: BridgeSettings,
    *,
    environment: Mapping[str, str],
    hermes_transport: httpx.AsyncBaseTransport | None = None,
    stt_transport: httpx.AsyncBaseTransport | None = None,
    tts_transport: httpx.AsyncBaseTransport | None = None,
) -> BridgeRuntime:
    """Build shared state without starting sockets or retaining plaintext device tokens."""

    token_hashes = _resolve_device_token_hashes(settings, environment)
    metrics = BridgeMetrics(enabled=settings.observability.metrics_enabled)
    capture_store = CaptureStore(
        directory=settings.captures.directory,
        ttl_seconds=settings.captures.ttl_seconds,
        max_bytes=settings.captures.max_bytes,
        persist=settings.captures.persist,
    )
    debug_audio_store = DebugAudioStore(
        directory=settings.audio.debug_directory,
        ttl_seconds=settings.audio.debug_ttl_seconds,
        enabled=settings.audio.debug_save_enabled,
    )
    if debug_audio_store.enabled:
        purged = debug_audio_store.purge_expired()
        _LOGGER.warning(
            "debug microphone audio persistence is enabled",
            extra={"event": "audio.debug_storage_enabled", "purged_files": purged},
        )
    registry = DeviceRegistry(
        command_timeout_seconds=settings.security.command_timeout_ms / 1_000,
        metrics=metrics,
        max_connections=settings.device_gateway.max_connections,
    )
    api_key = settings.hermes.api_key
    if api_key is None:
        raise ValueError("Hermes API key environment variable is required")
    hermes_http_client = httpx.AsyncClient(
        base_url=settings.hermes.base_url,
        timeout=settings.hermes.timeout_seconds,
        transport=hermes_transport,
        trust_env=False,
    )
    hermes = HermesClient(
        hermes_http_client,
        HermesClientConfig(
            api_key=api_key,
            profile=settings.hermes.profile,
            model=settings.hermes.model or None,
            responses_path=settings.hermes.responses_path,
            health_path=settings.hermes.health_path,
            capabilities_path=settings.hermes.capabilities_path,
            session_key_prefix=settings.hermes.session_key_prefix,
            timeout_seconds=settings.hermes.timeout_seconds,
        ),
    )
    stt_adapter, stt_clients = _build_stt_adapter(settings, transport=stt_transport)
    tts_adapter, tts_clients = _build_tts_adapter(settings, transport=tts_transport)
    turn_coordinator = TurnCoordinator(metrics=metrics)
    output_streamer = AudioOutputStreamer(
        registry,
        frame_ms=settings.audio.frame_ms,
    )
    tts_pipeline = SegmentPlaybackPipeline(
        tts_adapter,
        output_streamer,
        timeout_seconds=settings.tts.timeout_seconds,
        failure_policy=settings.tts.failure_policy,
        metrics=metrics,
    )
    segmenter_config = SpeechSegmenterConfig(
        max_segments=settings.tts.max_segments,
        segment_max_characters=settings.tts.segment_max_characters,
        response_max_characters=settings.tts.response_max_characters,
    )
    failure_notifier = DeviceTurnFailureNotifier(registry)
    progress_notifier = DeviceTurnProgressNotifier(
        registry,
        expression_enabled=settings.automation.expression_enabled,
        led_enabled=settings.automation.led_enabled,
    )
    voice_service = VoiceTurnService(
        coordinator=turn_coordinator,
        stt=stt_adapter,
        hermes=hermes,
        tts_pipeline=tts_pipeline,
        segmenter_config=segmenter_config,
        stt_timeout_seconds=settings.stt.timeout_seconds,
        metrics=metrics,
        failure_notifier=failure_notifier,
        progress_notifier=progress_notifier,
    )
    audio_input_handler = VoiceAudioInputHandler(
        turn_coordinator,
        voice_service,
        max_recording_ms=settings.audio.max_recording_ms,
        vad_config=RmsVadConfig(
            start_speech_ms=settings.vad.start_speech_ms,
            end_silence_ms=settings.vad.end_silence_ms,
            minimum_speech_ms=settings.vad.minimum_speech_ms,
            preroll_ms=settings.vad.preroll_ms,
            maximum_recording_ms=settings.audio.max_recording_ms,
            start_threshold=settings.vad.start_threshold,
            end_threshold=settings.vad.end_threshold,
            initial_noise_floor=settings.vad.initial_noise_floor,
            noise_floor_alpha=settings.vad.noise_floor_alpha,
            noise_start_ratio=settings.vad.noise_start_ratio,
            noise_end_ratio=settings.vad.noise_end_ratio,
        ),
        metrics=metrics,
        debug_audio_store=debug_audio_store,
    )
    capture_coordinator = CaptureCoordinator(
        registry,
        capture_store,
        timeout_seconds=settings.captures.timeout_seconds,
    )
    event_handler = TurnEventHandler(
        turn_coordinator,
        registry,
        capture_failures=capture_coordinator,
        metrics=metrics,
    )
    gateway = create_device_gateway_app(
        DeviceGatewayConfig(
            device_token_hashes=token_hashes,
            handshake_timeout_seconds=settings.device_gateway.handshake_timeout_ms / 1_000,
            heartbeat_interval_ms=settings.device_gateway.heartbeat_interval_ms,
            command_timeout_ms=settings.security.command_timeout_ms,
            max_audio_packet_bytes=settings.device_gateway.max_audio_packet_bytes,
            max_connections=settings.device_gateway.max_connections,
            authentication_rate_per_second=(settings.security.authentication_rate_per_second),
            authentication_rate_burst=settings.security.authentication_rate_burst,
            max_concurrent_authentications=(settings.security.max_concurrent_authentications),
            request_rate_per_second=settings.security.request_rate_per_second,
            request_rate_burst=settings.security.request_rate_burst,
            audio_packet_rate_per_second=settings.security.audio_packet_rate_per_second,
            audio_packet_rate_burst=settings.security.audio_packet_rate_burst,
            capture_rate_per_minute=settings.security.capture_rate_per_minute,
            capture_rate_burst=settings.security.capture_rate_burst,
        ),
        metrics=metrics,
        capture_store=capture_store,
        debug_audio_store=debug_audio_store,
        audio_input_handler=audio_input_handler,
        event_handler=event_handler,
        registry=registry,
        turn_coordinator=turn_coordinator,
    )
    vision_turn_service = VisionTurnService(
        coordinator=turn_coordinator,
        captures=capture_coordinator,
        hermes=hermes,
        tts_pipeline=tts_pipeline,
        segmenter_config=segmenter_config,
        metrics=metrics,
        progress_notifier=progress_notifier,
    )
    control = create_control_app(
        registry,
        readiness_checks={
            "configuration": _ready,
            "capture_store": lambda: _capture_store_ready(capture_store),
            "libopus": lambda: _opus_ready(settings.audio.frame_ms),
            "hermes": lambda: _hermes_ready(hermes),
            "stt": _ready,
            "tts": _ready,
        },
        metrics=metrics,
        capture_store=capture_store,
        capture_coordinator=capture_coordinator,
        turn_coordinator=turn_coordinator,
        vision_turn_service=vision_turn_service,
        conversation_resetter=hermes,
        touch_state=event_handler,
    )
    mdns_advertiser = _build_mdns_advertiser(settings)
    return BridgeRuntime(
        settings=settings,
        gateway=gateway,
        control=control,
        registry=registry,
        capture_store=capture_store,
        debug_audio_store=debug_audio_store,
        capture_coordinator=capture_coordinator,
        vision_turn_service=vision_turn_service,
        turn_coordinator=turn_coordinator,
        voice_turn_service=voice_service,
        failure_notifier=failure_notifier,
        progress_notifier=progress_notifier,
        audio_input_handler=audio_input_handler,
        event_handler=event_handler,
        stt_adapter=stt_adapter,
        tts_adapter=tts_adapter,
        hermes_client=hermes,
        hermes_http_client=hermes_http_client,
        provider_http_clients=(*stt_clients, *tts_clients),
        mdns_advertiser=mdns_advertiser,
        metrics=metrics,
    )


def run_servers(settings: BridgeSettings, environment: Mapping[str, str]) -> int:
    """Run the LAN Gateway and loopback Control API until both stop."""

    configure_bridge_logging(
        level=settings.observability.log_level,
        json_logs=settings.observability.json_logs,
        privacy_debug_transcripts=settings.observability.privacy_debug_transcripts,
    )
    runtime = build_runtime(settings, environment=environment)
    try:
        return asyncio.run(_serve_both(runtime))
    except KeyboardInterrupt:  # pragma: no cover - exercised by an operator signal
        return 130


async def _serve_both(runtime: BridgeRuntime) -> int:
    settings = runtime.settings
    control_server = _NoSignalServer(
        Config(
            runtime.control,
            host=settings.control_api.host,
            port=settings.control_api.port,
            log_level=settings.observability.log_level.lower(),
        )
    )
    gateway_server = _CoordinatingServer(
        Config(
            runtime.gateway,
            host=settings.device_gateway.host,
            port=settings.device_gateway.port,
            ws_max_size=settings.device_gateway.max_json_bytes,
            ws_ping_interval=settings.device_gateway.heartbeat_interval_ms / 1_000,
            ws_ping_timeout=settings.device_gateway.heartbeat_interval_ms * 3 / 1_000,
            log_level=settings.observability.log_level.lower(),
        ),
        peers=(control_server,),
    )
    if runtime.mdns_advertiser is not None:
        await runtime.mdns_advertiser.start()
    try:
        await asyncio.gather(gateway_server.serve(), control_server.serve())
    finally:
        if runtime.mdns_advertiser is not None:
            await runtime.mdns_advertiser.stop()
        await runtime.aclose()
    return gateway_server.signal_exit_code


class _NoSignalServer(Server):
    @contextmanager
    def capture_signals(self) -> Generator[None, None, None]:
        yield


class _CoordinatingServer(Server):
    def __init__(self, config: Config, *, peers: tuple[Server, ...]) -> None:
        super().__init__(config)
        self._peers = peers
        self.signal_exit_code = 0

    @contextmanager
    def capture_signals(self) -> Generator[None, None, None]:
        if threading.current_thread() is not threading.main_thread():
            yield
            return
        original_handlers = {
            captured_signal: signal.signal(captured_signal, self.handle_exit)
            for captured_signal in HANDLED_SIGNALS
        }
        try:
            yield
        finally:
            for captured_signal, handler in original_handlers.items():
                signal.signal(captured_signal, handler)

    def handle_exit(self, sig: int, frame: FrameType | None) -> None:
        if self.signal_exit_code == 0:
            self.signal_exit_code = 128 + sig
        for peer in self._peers:
            peer.should_exit = True
        super().handle_exit(sig, frame)


def _resolve_device_token_hashes(
    settings: BridgeSettings,
    environment: Mapping[str, str],
) -> dict[str, str]:
    allowed = set(settings.security.allowed_devices)
    hashes = dict(settings.security.device_token_hashes)
    if not set(hashes).issubset(allowed):
        raise ValueError("device token hash configured for a device that is not allowed")
    raw_token = environment.get(settings.security.device_token_env)
    missing = allowed.difference(hashes)
    if raw_token and len(missing) == 1:
        hashes[missing.pop()] = hash_device_token(raw_token)
    if allowed.difference(hashes):
        raise ValueError("every allowed device requires a token hash")
    return hashes


async def _ready() -> bool:
    return True


async def _capture_store_ready(store: CaptureStore) -> bool:
    try:
        with NamedTemporaryFile(dir=store.directory, prefix=".readiness-", delete=True) as probe:
            probe.write(b"ready")
            probe.flush()
    except OSError:
        return False
    return True


async def _opus_ready(frame_ms: int) -> bool:
    try:
        OpusCodec(OpusCodecConfig(frame_ms=frame_ms))
    except Exception:
        return False
    return True


async def _hermes_ready(client: HermesClient) -> bool:
    return (await client.probe()).ready


def _build_stt_adapter(
    settings: BridgeSettings,
    *,
    transport: httpx.AsyncBaseTransport | None,
) -> tuple[SttAdapter, tuple[httpx.AsyncClient, ...]]:
    selected = settings.stt
    if selected.adapter == "mock":
        return MockSttAdapter(language=selected.language), ()
    if selected.adapter == "faster-whisper":
        return (
            FasterWhisperSttAdapter(
                model_name=selected.model_name,
                language=selected.language,
                device=selected.device,
                compute_type=selected.compute_type,
            ),
            (),
        )
    if selected.endpoint is None:  # pragma: no cover - rejected by configuration validation
        raise ValueError("HTTP STT endpoint is required")
    client = httpx.AsyncClient(
        timeout=selected.timeout_seconds,
        transport=transport,
        trust_env=False,
    )
    return (
        GenericHttpSttAdapter(
            client=client,
            endpoint=selected.endpoint,
            api_key=selected.api_key,
            language=selected.language,
        ),
        (client,),
    )


def _build_tts_adapter(
    settings: BridgeSettings,
    *,
    transport: httpx.AsyncBaseTransport | None,
) -> tuple[TtsAdapter, tuple[httpx.AsyncClient, ...]]:
    selected = settings.tts
    if selected.adapter == "mock":
        return MockTtsAdapter(), ()
    if selected.endpoint is None:  # pragma: no cover - rejected by configuration validation
        raise ValueError("HTTP TTS endpoint is required")
    if selected.adapter == "voicevox":
        client = httpx.AsyncClient(
            base_url=selected.endpoint,
            timeout=selected.timeout_seconds,
            transport=transport,
            trust_env=False,
        )
        return (
            VoicevoxTtsAdapter(
                client=client,
                speaker=selected.speaker,
                gain=settings.audio.tts_gain,
                leading_silence_ms=settings.audio.tts_preroll_ms,
                trailing_silence_ms=settings.audio.tts_postroll_ms,
            ),
            (client,),
        )
    client = httpx.AsyncClient(
        timeout=selected.timeout_seconds,
        transport=transport,
        trust_env=False,
    )
    if selected.adapter == "openai":
        # Configuration validation guarantees both required speech identifiers.
        assert selected.model is not None and selected.voice is not None
        return (
            OpenAICompatibleTtsAdapter(
                client=client,
                endpoint=selected.endpoint,
                model=selected.model,
                voice=selected.voice,
                speed=selected.speed,
                api_key=selected.api_key,
                gain=settings.audio.tts_gain,
                leading_silence_ms=settings.audio.tts_preroll_ms,
                trailing_silence_ms=settings.audio.tts_postroll_ms,
            ),
            (client,),
        )
    return (
        GenericHttpWavTtsAdapter(
            client=client,
            endpoint=selected.endpoint,
            api_key=selected.api_key,
            gain=settings.audio.tts_gain,
            leading_silence_ms=settings.audio.tts_preroll_ms,
            trailing_silence_ms=settings.audio.tts_postroll_ms,
        ),
        (client,),
    )


def _build_mdns_advertiser(settings: BridgeSettings) -> MdnsAdvertiser | None:
    if not settings.mdns.enabled:
        return None
    hostname = settings.mdns.hostname or _safe_dns_label(gethostname())
    addresses = _local_addresses(settings.device_gateway.host)
    return MdnsAdvertiser(
        service_name=settings.mdns.service_name,
        port=settings.device_gateway.port,
        server_version="0.1.0",
        hostname=hostname,
        addresses=addresses,
    )


def _safe_dns_label(value: str) -> str:
    label = re.sub(r"[^A-Za-z0-9-]+", "-", value).strip("-")
    label = label[:63].rstrip("-")
    return label or "stackchan-bridge"


def _is_advertisable_address(value: str) -> bool:
    try:
        address = ip_address(value)
    except ValueError:
        return False
    return address.version == 4 and not (
        address.is_loopback
        or address.is_unspecified
        or address.is_multicast
        or address.is_link_local
    )


def _local_addresses(bind_host: str) -> tuple[str, ...]:
    try:
        bound_address = ip_address(bind_host)
    except ValueError:
        try:
            candidates = {str(entry[4][0]) for entry in getaddrinfo(bind_host, None)}
        except OSError:
            return ()
    else:
        if not bound_address.is_unspecified:
            candidates = {str(bound_address)}
        else:
            try:
                candidates = {
                    adapter_ip.ip
                    for adapter in get_adapters()
                    for adapter_ip in adapter.ips
                    if isinstance(adapter_ip.ip, str)
                }
            except OSError:
                return ()
    return tuple(sorted(value for value in candidates if _is_advertisable_address(value)))
