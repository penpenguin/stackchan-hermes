from __future__ import annotations

import asyncio
import json
import os
import signal
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from prometheus_client import generate_latest
from stackchan_bridge.audio.debug_store import DebugAudioStore
from stackchan_bridge.audio.input import VoiceAudioInputHandler
from stackchan_bridge.audio.types import PcmAudio
from stackchan_bridge.captures.store import CaptureValidationError
from stackchan_bridge.config import load_settings
from stackchan_bridge.discovery.mdns import MdnsAdvertiser
from stackchan_bridge.hermes.client import HermesClient
from stackchan_bridge.protocol.models import EventMessage
from stackchan_bridge.runtime import (
    _build_mdns_advertiser,
    _CoordinatingServer,
    _local_addresses,
    _serve_both,
    build_runtime,
)
from stackchan_bridge.stt.adapters import FasterWhisperSttAdapter, GenericHttpSttAdapter
from stackchan_bridge.tts.adapters import (
    GenericHttpWavTtsAdapter,
    OpenAICompatibleTtsAdapter,
    VoicevoxTtsAdapter,
)
from stackchan_bridge.turns.events import TurnEventHandler
from stackchan_bridge.turns.notifications import (
    DeviceTurnFailureNotifier,
    DeviceTurnProgressNotifier,
)
from stackchan_bridge.turns.service import VoiceTurnService
from stackchan_bridge.turns.vision import VisionTurnService
from stackchan_simulator.mock_hermes import MockHermesConfig, create_mock_hermes_app
from uvicorn import Config, Server

from .test_openai_tts import make_wav
from .test_turn_events import touch_tap

ROOT = Path(__file__).resolve().parents[2]


def test_coordinating_server_does_not_reraise_a_captured_shutdown_signal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    peer = Server(Config(app=lambda _scope, _receive, _send: None))
    server = _CoordinatingServer(
        Config(app=lambda _scope, _receive, _send: None),
        peers=(peer,),
    )
    reraised: list[int] = []

    monkeypatch.setattr(signal, "signal", lambda _signal, _handler: signal.SIG_DFL)
    monkeypatch.setattr(signal, "raise_signal", reraised.append)

    with server.capture_signals():
        server.handle_exit(signal.SIGINT, None)

    assert reraised == []
    assert peer.should_exit is True
    assert server.signal_exit_code == 130


@pytest.mark.asyncio
async def test_runtime_does_not_apply_the_websocket_limit_to_http_uploads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    environment = {
        "STACKCHAN_DEVICE_TOKEN": "runtime-device-token",  # pragma: allowlist secret
        "HERMES_API_KEY": "runtime-hermes-key",  # pragma: allowlist secret
    }
    settings = load_settings(
        ROOT / "config.example.toml",
        environment=environment,
        cli_overrides={
            "captures": {"directory": str(tmp_path)},
            "device_gateway": {"max_connections": 1},
            "mdns": {"enabled": False},
        },
    )
    configs: list[Config] = []

    class RecordingServer:
        def __init__(self, config: Config, **_kwargs: object) -> None:
            configs.append(config)
            self.signal_exit_code = 0

        async def serve(self) -> None:
            return None

    monkeypatch.setattr("stackchan_bridge.runtime._NoSignalServer", RecordingServer)
    monkeypatch.setattr("stackchan_bridge.runtime._CoordinatingServer", RecordingServer)
    runtime = build_runtime(settings, environment=environment)

    await _serve_both(runtime)

    gateway_config = configs[1]
    assert gateway_config.limit_concurrency is None
    assert gateway_config.ws_ping_interval == 15
    assert gateway_config.ws_ping_timeout == 45


@pytest.mark.asyncio
@pytest.mark.parametrize("enabled,fail_once", [(True, False), (True, True), (False, False)])
async def test_runtime_purges_debug_audio_during_gateway_lifespan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    enabled: bool,
    fail_once: bool,
) -> None:
    environment = {
        "STACKCHAN_DEVICE_TOKEN": "runtime-device-token",  # pragma: allowlist secret
        "HERMES_API_KEY": "runtime-hermes-key",  # pragma: allowlist secret
    }
    settings = load_settings(
        ROOT / "config.example.toml",
        environment=environment,
        cli_overrides={
            "captures": {"directory": str(tmp_path / "captures")},
            "audio": {"debug_directory": str(tmp_path / "audio"), "debug_save_enabled": enabled},
            "mdns": {"enabled": False},
        },
    )
    runtime = build_runtime(settings, environment=environment)
    calls = 0
    original_purge = DebugAudioStore.purge_expired

    def purge(store: DebugAudioStore, *, now: float | None = None) -> int:
        nonlocal calls
        if store is runtime.debug_audio_store:
            calls += 1
            if fail_once and calls == 1:
                raise OSError("temporary debug directory failure")
        return original_purge(store, now=now)

    monkeypatch.setattr(DebugAudioStore, "purge_expired", purge)
    monkeypatch.setattr(
        "stackchan_bridge.device_gateway.application._DEBUG_AUDIO_CLEANUP_INTERVAL_SECONDS",
        0.01,
        raising=False,
    )
    writer = DebugAudioStore(directory=tmp_path / "audio", ttl_seconds=600, enabled=True)
    try:
        async with runtime.gateway.router.lifespan_context(runtime.gateway):
            expired = writer.save(uuid4(), PcmAudio(pcm=b"\x00\x00" * 320))
            recent = writer.save(uuid4(), PcmAudio(pcm=b"\x00\x00" * 320))
            assert expired is not None and recent is not None
            os.utime(expired, (0, 0))
            unrelated = writer.directory / "unrelated.wav"
            unrelated.write_bytes(b"unrelated")
            if enabled:

                async def wait_for_purge() -> None:
                    while expired.exists():
                        await asyncio.sleep(0.005)

                await asyncio.wait_for(wait_for_purge(), timeout=0.3)
                assert calls >= (2 if fail_once else 1)
            else:
                await asyncio.sleep(0.03)
                assert calls == 0
                assert expired.exists()
            assert recent.exists()
            assert unrelated.exists()
        stopped_calls = calls
        await asyncio.sleep(0.03)
        assert calls == stopped_calls
    finally:
        await runtime.aclose()


def test_runtime_wires_shared_apps_without_retaining_the_device_token(tmp_path: Path) -> None:
    token = "runtime-device-token"  # pragma: allowlist secret
    environment = {
        "STACKCHAN_DEVICE_TOKEN": token,
        "HERMES_API_KEY": "runtime-hermes-key",  # pragma: allowlist secret
    }
    settings = load_settings(
        ROOT / "config.example.toml",
        environment=environment,
        cli_overrides={
            "captures": {"directory": str(tmp_path)},
            "audio": {"debug_directory": str(tmp_path / "debug-audio")},
            "security": {
                "authentication_rate_per_second": 3,
                "authentication_rate_burst": 7,
                "max_concurrent_authentications": 2,
                "audio_packet_rate_per_second": 55,
                "audio_packet_rate_burst": 80,
            },
        },
    )

    runtime = build_runtime(settings, environment=environment)

    assert runtime.gateway.state.device_registry is runtime.registry
    assert runtime.gateway.state.gateway_config.request_rate_per_second == 100
    assert runtime.gateway.state.gateway_config.request_rate_burst == 200
    assert runtime.gateway.state.gateway_config.authentication_rate_per_second == 3
    assert runtime.gateway.state.gateway_config.authentication_rate_burst == 7
    assert runtime.gateway.state.gateway_config.max_concurrent_authentications == 2
    assert runtime.gateway.state.gateway_config.audio_packet_rate_per_second == 55
    assert runtime.gateway.state.gateway_config.audio_packet_rate_burst == 80
    assert runtime.gateway.state.gateway_config.capture_rate_burst == 2
    assert runtime.control.state.capture_store is runtime.capture_store
    assert runtime.gateway.state.capture_store is runtime.capture_store
    assert isinstance(runtime.gateway.state.audio_input_handler, VoiceAudioInputHandler)
    assert isinstance(runtime.debug_audio_store, DebugAudioStore)
    assert runtime.debug_audio_store.enabled is False
    assert runtime.debug_audio_store.directory == tmp_path / "debug-audio"
    assert isinstance(runtime.voice_turn_service, VoiceTurnService)
    assert isinstance(runtime.failure_notifier, DeviceTurnFailureNotifier)
    assert runtime.voice_turn_service.failure_notifier is runtime.failure_notifier
    assert isinstance(runtime.progress_notifier, DeviceTurnProgressNotifier)
    assert runtime.voice_turn_service.progress_notifier is runtime.progress_notifier
    assert isinstance(runtime.gateway.state.event_handler, TurnEventHandler)
    assert isinstance(runtime.mdns_advertiser, MdnsAdvertiser)
    assert runtime.mdns_advertiser.info.port == 8765
    assert runtime.mdns_advertiser.info.name.startswith("stackchan-bridge.")
    assert runtime.control.state.capture_coordinator is runtime.capture_coordinator
    assert isinstance(runtime.vision_turn_service, VisionTurnService)
    assert runtime.control.state.vision_turn_service is runtime.vision_turn_service
    assert isinstance(runtime.hermes_client, HermesClient)
    assert runtime.control.state.conversation_resetter is runtime.hermes_client
    assert runtime.capture_store.directory == tmp_path.resolve()
    asyncio.run(runtime.event_handler.handle("sim-001", touch_tap()))
    assert b"touch_events_total 1.0" in generate_latest(runtime.metrics.registry)

    async def assert_camera_failure_wiring() -> None:
        reservation = runtime.capture_store.reserve("sim-001")
        event = EventMessage.model_validate(
            {
                "v": 1,
                "type": "event",
                "message_id": "6cf29039-ce46-4585-b2a4-86c9e9e4d2d0",
                "device_id": "sim-001",
                "sent_at_ms": 2,
                "payload": {
                    "name": "camera.completed",
                    "data": {
                        "capture_id": str(reservation.capture_id),
                        "ok": False,
                        "error_code": "CAPTURE_FAILED",
                    },
                },
            }
        )
        await runtime.event_handler.handle("sim-001", event)
        with pytest.raises(CaptureValidationError) as error:
            await runtime.capture_store.wait_for(reservation.capture_id, timeout_seconds=0.01)
        assert error.value.code == "CAPTURE_FAILED"
        runtime.capture_store.cancel(reservation.capture_id)

    asyncio.run(assert_camera_failure_wiring())
    assert token not in repr(runtime)
    assert token not in repr(runtime.gateway.state.device_registry)


@pytest.mark.asyncio
async def test_runtime_readiness_checks_public_dependencies_without_a_device(
    tmp_path: Path,
) -> None:
    api_key = "runtime-readiness-key"  # pragma: allowlist secret
    environment = {
        "STACKCHAN_DEVICE_TOKEN": "runtime-device-token",  # pragma: allowlist secret
        "HERMES_API_KEY": api_key,  # pragma: allowlist secret
    }
    settings = load_settings(
        ROOT / "config.example.toml",
        environment=environment,
        cli_overrides={"captures": {"directory": str(tmp_path)}},
    )
    hermes_transport = httpx.ASGITransport(
        app=create_mock_hermes_app(MockHermesConfig(api_key=api_key))
    )
    runtime = build_runtime(
        settings,
        environment=environment,
        hermes_transport=hermes_transport,
    )
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=runtime.control),
            base_url="http://control",
        ) as client:
            response = await client.get("/health/ready")
    finally:
        await runtime.hermes_http_client.aclose()

    assert response.status_code == 200
    assert response.json() == {
        "ready": True,
        "connected_devices": 0,
        "checks": {
            "capture_store": True,
            "configuration": True,
            "hermes": True,
            "libopus": True,
            "stt": True,
            "tts": True,
        },
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("tts_adapter", ["http", "openai"])
async def test_runtime_readiness_does_not_run_stt_or_tts_inference(
    tmp_path: Path, tts_adapter: str
) -> None:
    api_key = "runtime-readiness-key"  # pragma: allowlist secret
    environment = {
        "STACKCHAN_DEVICE_TOKEN": "runtime-device-token",  # pragma: allowlist secret
        "HERMES_API_KEY": api_key,  # pragma: allowlist secret
    }
    settings = load_settings(
        ROOT / "config.example.toml",
        environment=environment,
        cli_overrides={
            "captures": {"directory": str(tmp_path)},
            "stt": {
                "adapter": "http",
                "endpoint": "https://stt.example.test/transcribe",
            },
            "tts": {
                "adapter": tts_adapter,
                "endpoint": "https://tts.example.test/synthesize",
                "model": "irodori-tts",
                "voice": "sample",
            },
        },
    )
    provider_requests: list[str] = []

    async def reject_inference(request: httpx.Request) -> httpx.Response:
        provider_requests.append(str(request.url))
        return httpx.Response(503)

    runtime = build_runtime(
        settings,
        environment=environment,
        hermes_transport=httpx.ASGITransport(
            app=create_mock_hermes_app(MockHermesConfig(api_key=api_key))
        ),
        stt_transport=httpx.MockTransport(reject_inference),
        tts_transport=httpx.MockTransport(reject_inference),
    )
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=runtime.control),
            base_url="http://control",
        ) as client:
            response = await client.get("/health/ready")
    finally:
        await runtime.aclose()

    assert response.status_code == 200
    assert response.json()["checks"]["stt"] is True
    assert response.json()["checks"]["tts"] is True
    assert provider_requests == []


async def test_runtime_synthesizes_with_openai_tts_and_closes_its_client(tmp_path: Path) -> None:
    api_key = "runtime-irodori-key"  # pragma: allowlist secret
    environment = {
        "STACKCHAN_DEVICE_TOKEN": "runtime-device-token",  # pragma: allowlist secret
        "HERMES_API_KEY": "runtime-hermes-key",  # pragma: allowlist secret
        "STACKCHAN_TTS_API_KEY": api_key,  # pragma: allowlist secret
    }
    settings = load_settings(
        ROOT / "config.example.toml",
        environment=environment,
        cli_overrides={
            "captures": {"directory": str(tmp_path)},
            "audio": {"tts_gain": 0.5},
            "tts": {
                "adapter": "openai",
                "endpoint": "http://127.0.0.1:8088/v1/audio/speech",
                "model": "irodori-tts",
                "voice": "sample",
                "speed": 1.25,
                "timeout_seconds": 120,
            },
        },
    )

    async def handle(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == settings.tts.endpoint
        assert request.headers["authorization"] == f"Bearer {api_key}"
        assert json.loads(await request.aread()) == {
            "model": "irodori-tts",
            "voice": "sample",
            "speed": 1.25,
            "input": "こんにちは。",
            "response_format": "wav",
        }
        return httpx.Response(200, content=make_wav(), headers={"Content-Type": "audio/wav"})

    runtime = build_runtime(
        settings, environment=environment, tts_transport=httpx.MockTransport(handle)
    )
    try:
        adapter = runtime.tts_adapter
        assert isinstance(adapter, OpenAICompatibleTtsAdapter)
        assert adapter.gain == 0.5
        assert adapter.leading_silence_ms == 500
        assert adapter.trailing_silence_ms == 100
        assert adapter.client.timeout.read == 120
        assert api_key not in repr(runtime)
        result = await adapter.synthesize("こんにちは。")
        assert result.audio.duration_seconds == 1.1
    finally:
        await runtime.aclose()

    assert adapter.client.is_closed


@pytest.mark.asyncio
async def test_runtime_selects_faster_whisper_and_voicevox_adapters(tmp_path: Path) -> None:
    environment = {
        "STACKCHAN_DEVICE_TOKEN": "runtime-device-token",  # pragma: allowlist secret
        "HERMES_API_KEY": "runtime-hermes-key",  # pragma: allowlist secret
    }
    settings = load_settings(
        ROOT / "config.example.toml",
        environment=environment,
        cli_overrides={
            "captures": {"directory": str(tmp_path)},
            "stt": {
                "adapter": "faster-whisper",
                "model_name": "tiny",
                "device": "cpu",
                "compute_type": "int8",
            },
            "tts": {
                "adapter": "voicevox",
                "endpoint": "http://127.0.0.1:50021",
                "speaker": 8,
            },
        },
    )

    runtime = build_runtime(settings, environment=environment)
    try:
        assert isinstance(runtime.stt_adapter, FasterWhisperSttAdapter)
        assert runtime.stt_adapter.model_name == "tiny"
        assert isinstance(runtime.tts_adapter, VoicevoxTtsAdapter)
        assert runtime.tts_adapter.speaker == 8
        assert runtime.tts_adapter.leading_silence_ms == 500
        assert runtime.tts_adapter.trailing_silence_ms == 100
    finally:
        await runtime.aclose()


@pytest.mark.asyncio
async def test_runtime_selects_generic_http_adapters_and_can_disable_mdns(tmp_path: Path) -> None:
    stt_key = "runtime-stt-key"  # pragma: allowlist secret
    tts_key = "runtime-tts-key"  # pragma: allowlist secret
    environment = {
        "STACKCHAN_DEVICE_TOKEN": "runtime-device-token",  # pragma: allowlist secret
        "HERMES_API_KEY": "runtime-hermes-key",  # pragma: allowlist secret
        "STACKCHAN_STT_API_KEY": stt_key,  # pragma: allowlist secret
        "STACKCHAN_TTS_API_KEY": tts_key,  # pragma: allowlist secret
    }
    settings = load_settings(
        ROOT / "config.example.toml",
        environment=environment,
        cli_overrides={
            "captures": {"directory": str(tmp_path)},
            "stt": {
                "adapter": "http",
                "endpoint": "https://stt.example.test/v1/transcriptions",
            },
            "tts": {
                "adapter": "http",
                "endpoint": "https://tts.example.test/v1/speech",
            },
            "mdns": {"enabled": False},
        },
    )

    runtime = build_runtime(
        settings,
        environment=environment,
        stt_transport=httpx.MockTransport(lambda _request: httpx.Response(500)),
        tts_transport=httpx.MockTransport(lambda _request: httpx.Response(500)),
    )
    try:
        assert isinstance(runtime.stt_adapter, GenericHttpSttAdapter)
        assert runtime.stt_adapter.api_key is not None
        assert runtime.stt_adapter.api_key.get_secret_value() == stt_key
        assert isinstance(runtime.tts_adapter, GenericHttpWavTtsAdapter)
        assert runtime.tts_adapter.api_key is not None
        assert runtime.tts_adapter.api_key.get_secret_value() == tts_key
        assert runtime.tts_adapter.leading_silence_ms == 500
        assert runtime.tts_adapter.trailing_silence_ms == 100
        assert runtime.mdns_advertiser is None
        assert stt_key not in repr(runtime)
        assert tts_key not in repr(runtime)
    finally:
        await runtime.aclose()


@pytest.mark.asyncio
async def test_runtime_disables_metric_collection_and_the_metrics_endpoint(tmp_path: Path) -> None:
    environment = {
        "STACKCHAN_DEVICE_TOKEN": "runtime-device-token",  # pragma: allowlist secret
        "HERMES_API_KEY": "runtime-hermes-key",  # pragma: allowlist secret
    }
    settings = load_settings(
        ROOT / "config.example.toml",
        environment=environment,
        cli_overrides={
            "captures": {"directory": str(tmp_path)},
            "observability": {"metrics_enabled": False},
            "mdns": {"enabled": False},
        },
    )
    runtime = build_runtime(settings, environment=environment)
    try:
        await runtime.event_handler.handle("sim-001", touch_tap())
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=runtime.control),
            base_url="http://control",
        ) as client:
            response = await client.get("/metrics")
    finally:
        await runtime.aclose()

    assert response.status_code == 404
    assert generate_latest(runtime.metrics.registry) == b""


def test_runtime_requires_hermes_key_without_reflecting_other_secrets(tmp_path: Path) -> None:
    environment = {
        "STACKCHAN_DEVICE_TOKEN": "runtime-device-token",  # pragma: allowlist secret
    }
    settings = load_settings(
        ROOT / "config.example.toml",
        environment=environment,
        cli_overrides={"captures": {"directory": str(tmp_path)}},
    )

    with pytest.raises(ValueError, match="Hermes API key environment variable is required"):
        build_runtime(settings, environment=environment)


def test_mdns_uses_bound_local_interfaces_instead_of_resolving_its_advertised_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    environment = {
        "STACKCHAN_DEVICE_TOKEN": "runtime-device-token",  # pragma: allowlist secret
        "HERMES_API_KEY": "runtime-hermes-key",  # pragma: allowlist secret
    }
    settings = load_settings(
        ROOT / "config.example.toml",
        environment=environment,
        cli_overrides={"mdns": {"hostname": "bridge-host"}},
    )
    resolved_names: list[str] = []
    monkeypatch.setattr(
        "stackchan_bridge.runtime.getaddrinfo",
        lambda hostname, _port: resolved_names.append(hostname) or [],
    )
    monkeypatch.setattr(
        "stackchan_bridge.runtime.get_adapters",
        lambda: [
            SimpleNamespace(
                ips=[
                    SimpleNamespace(ip="192.168.10.8"),
                    SimpleNamespace(ip="127.0.0.1"),
                    SimpleNamespace(ip=("fe80::1", 0, 0)),
                ]
            )
        ],
        raising=False,
    )

    advertiser = _build_mdns_advertiser(settings)

    assert advertiser is not None
    assert advertiser.info.parsed_addresses() == ["192.168.10.8"]
    assert resolved_names == []


def test_mdns_interface_enumeration_failure_does_not_abort_bridge_startup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_to_enumerate() -> list[object]:
        raise OSError("interface enumeration unavailable")

    monkeypatch.setattr("stackchan_bridge.runtime.get_adapters", fail_to_enumerate)

    assert _local_addresses("0.0.0.0") == ()
