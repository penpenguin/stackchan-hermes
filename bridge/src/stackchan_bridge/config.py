"""Validated Bridge configuration with explicit source precedence."""

from __future__ import annotations

import json
import tomllib
from collections.abc import Mapping
from ipaddress import ip_address
from pathlib import Path
from typing import Annotated, Any, Literal
from urllib.parse import urlsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    StringConstraints,
    field_validator,
    model_validator,
)

from stackchan_bridge.protocol.models import MAX_AUDIO_PACKET_BYTES, MAX_JSON_BYTES

AbsolutePath = Annotated[str, StringConstraints(pattern=r"^/", max_length=128)]
DnsLabel = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=63,
        pattern=r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$",
    ),
]


class DeviceGatewaySettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    host: str = "0.0.0.0"
    port: int = Field(default=8765, ge=1, le=65_535)
    websocket_path: Literal["/v1/device/ws"] = "/v1/device/ws"
    capture_upload_path: Literal["/v1/device/captures/{capture_id}"] = (
        "/v1/device/captures/{capture_id}"
    )
    handshake_timeout_ms: int = Field(default=5_000, ge=100, le=60_000)
    heartbeat_interval_ms: int = Field(default=15_000, ge=1_000, le=60_000)
    max_connections: int = Field(default=8, ge=1, le=128)
    max_json_bytes: int = Field(default=MAX_JSON_BYTES, ge=1_024, le=MAX_JSON_BYTES)
    max_audio_packet_bytes: int = Field(
        default=MAX_AUDIO_PACKET_BYTES,
        ge=1,
        le=MAX_AUDIO_PACKET_BYTES,
    )


class ControlApiSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    host: str = "127.0.0.1"
    port: int = Field(default=8766, ge=1, le=65_535)

    @field_validator("host")
    @classmethod
    def require_loopback_host(cls, value: str) -> str:
        if not _is_loopback_host(value):
            raise ValueError("Control API host must be loopback")
        return value


class HermesSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_url: str = "http://127.0.0.1:8642"
    api_key_env: str = "HERMES_API_KEY"  # pragma: allowlist secret
    api_key: SecretStr | None = Field(default=None, repr=False)
    profile: str = "default"
    model: str = ""
    responses_path: AbsolutePath = "/v1/responses"
    health_path: AbsolutePath = "/health"
    capabilities_path: AbsolutePath = "/v1/capabilities"
    session_key_prefix: str = Field(default="agent:default:stackchan", min_length=1, max_length=192)
    timeout_seconds: float = Field(default=120, gt=0, le=300)
    allow_chat_completions_fallback: Literal[False] = False

    @field_validator("base_url")
    @classmethod
    def require_loopback_http_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or parsed.hostname is None
            or not _is_loopback_host(parsed.hostname)
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Hermes base URL must be an uncredentialed loopback HTTP URL")
        return value.rstrip("/")


class AudioSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    codec: Literal["opus"] = "opus"
    sample_rate: Literal[16000] = 16_000
    channels: Literal[1] = 1
    frame_ms: Literal[20, 40, 60] = 60
    max_recording_ms: int = Field(default=15_000, ge=1_000, le=15_000)
    tts_preroll_ms: int = Field(default=500, ge=0, le=5_000)
    tts_postroll_ms: int = Field(default=100, ge=0, le=5_000)
    tts_gain: float = Field(default=1.0, ge=0, le=2)
    debug_save_enabled: bool = False
    debug_directory: Path = Path(".local/debug-audio")
    debug_ttl_seconds: int = Field(default=3_600, ge=60, le=86_400)


class VadSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    adapter: Literal["rms"] = "rms"
    start_speech_ms: int = Field(default=60, ge=20, le=5_000)
    end_silence_ms: int = Field(default=650, ge=20, le=10_000)
    minimum_speech_ms: int = Field(default=240, ge=20, le=10_000)
    preroll_ms: int = Field(default=360, ge=0, le=5_000)
    start_threshold: float = Field(default=1_000, gt=0, le=32_767)
    end_threshold: float = Field(default=500, ge=0, le=32_767)
    initial_noise_floor: float = Field(default=50, ge=0, le=32_767)
    noise_floor_alpha: float = Field(default=0.05, gt=0, le=1)
    noise_start_ratio: float = Field(default=3.0, gt=0, le=100)
    noise_end_ratio: float = Field(default=1.8, gt=0, le=100)

    @model_validator(mode="after")
    def thresholds_have_hysteresis(self) -> VadSettings:
        if self.end_threshold >= self.start_threshold:
            raise ValueError("VAD end threshold must be below start threshold")
        if self.noise_end_ratio >= self.noise_start_ratio:
            raise ValueError("VAD end noise ratio must be below start noise ratio")
        return self


class SttSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    adapter: Literal["mock", "faster-whisper", "http"] = "mock"
    language: str = Field(default="ja", min_length=2, max_length=16)
    timeout_seconds: float = Field(default=60, gt=0, le=300)
    endpoint: str | None = None
    api_key_env: str = Field(default="STACKCHAN_STT_API_KEY", min_length=1, max_length=128)
    api_key: SecretStr | None = Field(default=None, repr=False)
    model_name: str = Field(default="small", min_length=1, max_length=128)
    device: Literal["auto", "cpu", "cuda"] = "auto"
    compute_type: str = Field(default="default", min_length=1, max_length=64)

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, value: str | None) -> str | None:
        return _provider_endpoint(value)

    @model_validator(mode="after")
    def http_requires_endpoint(self) -> SttSettings:
        if self.adapter == "http" and self.endpoint is None:
            raise ValueError("HTTP STT requires an endpoint")
        return self


class IrodoriTtsSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    caption: str | None = None
    seed: int | None = None


class TtsSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    adapter: Literal["mock", "http", "voicevox", "openai"] = "mock"
    timeout_seconds: float = Field(default=30, gt=0, le=300)
    endpoint: str | None = None
    api_key_env: str = Field(default="STACKCHAN_TTS_API_KEY", min_length=1, max_length=128)
    api_key: SecretStr | None = Field(default=None, repr=False)
    speaker: int = Field(default=1, ge=0, le=1_000)
    model: str | None = None
    voice: str | None = None
    speed: float = Field(default=1.0, ge=0.25, le=4.0)
    irodori: IrodoriTtsSettings = Field(default_factory=IrodoriTtsSettings)
    max_segments: int = Field(default=2, ge=1, le=10)
    segment_max_characters: int = Field(default=80, ge=1, le=500)
    response_max_characters: int = Field(default=160, ge=1, le=2_000)
    failure_policy: Literal["abort", "play_completed"] = "abort"

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, value: str | None) -> str | None:
        return _provider_endpoint(value)

    @model_validator(mode="after")
    def response_limit_covers_one_segment(self) -> TtsSettings:
        if self.adapter in {"http", "voicevox", "openai"} and self.endpoint is None:
            raise ValueError("HTTP TTS requires an endpoint")
        if self.adapter == "openai":
            if self.model is None or not self.model.strip():
                raise ValueError("OpenAI-compatible TTS requires a non-empty model")
            if self.voice is None or not self.voice.strip():
                raise ValueError("OpenAI-compatible TTS requires a non-empty voice")
        if self.response_max_characters < self.segment_max_characters:
            raise ValueError("response character limit must cover at least one segment")
        return self


class CaptureSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    directory: Path = Path(".local/captures")
    ttl_seconds: int = Field(default=600, ge=1, le=86_400)
    max_bytes: int = Field(default=2_097_152, ge=1_024, le=16_777_216)
    timeout_seconds: float = Field(default=10, gt=0, le=120)
    persist: bool = False


class ObservabilitySettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    json_logs: bool = False
    privacy_debug_transcripts: bool = False
    metrics_enabled: bool = True


class SecuritySettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allowed_devices: list[str] = Field(default_factory=list, max_length=128)
    device_token_env: str = "STACKCHAN_DEVICE_TOKEN"
    device_token_hashes: dict[str, str] = Field(default_factory=dict)
    authentication_rate_per_second: float = Field(default=5, gt=0, le=1_000)
    authentication_rate_burst: int = Field(default=10, ge=1, le=1_000)
    max_concurrent_authentications: int = Field(default=4, ge=1, le=32)
    request_rate_per_second: float = Field(default=100, gt=0, le=10_000)
    request_rate_burst: int = Field(default=200, ge=1, le=10_000)
    audio_packet_rate_per_second: float = Field(default=60, gt=0, le=1_000)
    audio_packet_rate_burst: int = Field(default=100, ge=1, le=10_000)
    capture_rate_per_minute: int = Field(default=6, ge=1, le=600)
    capture_rate_burst: int = Field(default=2, ge=1, le=100)
    command_timeout_ms: int = Field(default=5_000, ge=100, le=30_000)


class AutomationSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expression_enabled: bool = True
    led_enabled: bool = True


class MdnsSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    service_name: DnsLabel = "stackchan-bridge"
    hostname: DnsLabel | None = None


class BridgeSettings(BaseModel):
    """Top-level settings validated after all sources have been merged."""

    model_config = ConfigDict(extra="forbid")

    device_gateway: DeviceGatewaySettings = Field(default_factory=DeviceGatewaySettings)
    control_api: ControlApiSettings = Field(default_factory=ControlApiSettings)
    hermes: HermesSettings = Field(default_factory=HermesSettings)
    audio: AudioSettings = Field(default_factory=AudioSettings)
    vad: VadSettings = Field(default_factory=VadSettings)
    stt: SttSettings = Field(default_factory=SttSettings)
    tts: TtsSettings = Field(default_factory=TtsSettings)
    captures: CaptureSettings = Field(default_factory=CaptureSettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    automation: AutomationSettings = Field(default_factory=AutomationSettings)
    mdns: MdnsSettings = Field(default_factory=MdnsSettings)


def load_settings(
    config_path: Path | None = None,
    *,
    environment: Mapping[str, str],
    cli_overrides: Mapping[str, object] | None = None,
) -> BridgeSettings:
    """Load CLI > environment > TOML > defaults without retaining raw keys."""

    selected_path = config_path
    if selected_path is None and environment.get("STACKCHAN_CONFIG"):
        selected_path = Path(environment["STACKCHAN_CONFIG"])
    merged: dict[str, Any] = {}
    if selected_path is not None:
        with selected_path.open("rb") as config_file:
            toml_data = tomllib.load(config_file)
        _deep_merge(merged, toml_data)
    _deep_merge(merged, _nested_environment(environment))
    if cli_overrides is not None:
        _deep_merge(merged, cli_overrides)

    for section_name in ("hermes", "stt", "tts"):
        section = merged.get(section_name, {})
        if isinstance(section, Mapping) and "api_key" in section:
            raise ValueError(
                f"{section_name} API key must come from the named environment variable"
            )

    settings = BridgeSettings.model_validate(merged)
    secret_updates: dict[str, BaseModel] = {}
    for section_name in ("hermes", "stt", "tts"):
        section = getattr(settings, section_name)
        secret = environment.get(section.api_key_env)
        if secret:
            secret_updates[section_name] = section.model_copy(update={"api_key": SecretStr(secret)})
    if secret_updates:
        settings = settings.model_copy(update=secret_updates)
    return settings


def _nested_environment(environment: Mapping[str, str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, raw_value in environment.items():
        if not name.startswith("STACKCHAN_") or "__" not in name:
            continue
        path = name.removeprefix("STACKCHAN_").lower().split("__")
        target = result
        for component in path[:-1]:
            child = target.setdefault(component, {})
            if not isinstance(child, dict):
                raise ValueError(f"configuration path conflicts at {component}")
            target = child
        target[path[-1]] = _parse_environment_value(raw_value)
    return result


def _parse_environment_value(value: str) -> object:
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _deep_merge(target: dict[str, Any], source: Mapping[str, object]) -> None:
    for key, value in source.items():
        existing = target.get(key)
        if isinstance(existing, dict) and isinstance(value, Mapping):
            _deep_merge(existing, value)
        else:
            target[key] = value


def _is_loopback_host(host: str) -> bool:
    if host.lower() == "localhost":
        return True
    try:
        return ip_address(host).is_loopback
    except ValueError:
        return False


def _provider_endpoint(value: str | None) -> str | None:
    if value is None:
        return None
    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or (parsed.scheme == "http" and not _is_loopback_host(parsed.hostname))
    ):
        raise ValueError("provider endpoint must be HTTPS or loopback HTTP without credentials")
    return value
