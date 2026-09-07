from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError
from stackchan_bridge.config import load_settings

ROOT = Path(__file__).resolve().parents[2]


def test_config_priority_is_cli_then_environment_then_toml_then_defaults(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[device_gateway]
port = 7000

[control_api]
port = 7001

[hermes]
profile = "toml-profile"
""".strip(),
        encoding="utf-8",
    )
    environment = {
        "STACKCHAN_DEVICE_GATEWAY__PORT": "7100",
        "STACKCHAN_CONTROL_API__PORT": "7101",
        "HERMES_API_KEY": "runtime-only-key",  # pragma: allowlist secret
    }

    settings = load_settings(
        config_path,
        environment=environment,
        cli_overrides={"device_gateway": {"port": 7200}},
    )

    assert settings.device_gateway.port == 7200
    assert settings.control_api.port == 7101
    assert settings.hermes.profile == "toml-profile"
    assert settings.audio.sample_rate == 16_000
    assert settings.hermes.api_key is not None
    assert settings.hermes.api_key.get_secret_value() == "runtime-only-key"
    assert "runtime-only-key" not in repr(settings)


def test_config_example_is_a_complete_runtime_configuration() -> None:
    settings = load_settings(ROOT / "config.example.toml", environment={})

    assert settings.device_gateway.max_json_bytes == 16_384
    assert settings.device_gateway.max_connections == 8
    assert settings.control_api.host == "127.0.0.1"
    assert settings.hermes.responses_path == "/v1/responses"
    assert settings.audio.frame_ms == 60
    assert settings.audio.tts_preroll_ms == 500
    assert settings.audio.tts_postroll_ms == 100
    assert settings.audio.debug_save_enabled is False
    assert settings.audio.debug_directory == Path(".local/debug-audio")
    assert settings.audio.debug_ttl_seconds == 3_600
    assert settings.vad.end_silence_ms == 650
    assert settings.stt.adapter == "mock"
    assert settings.tts.response_max_characters == 160
    assert settings.tts.failure_policy == "abort"
    assert settings.captures.ttl_seconds == 600
    assert settings.observability.privacy_debug_transcripts is False
    assert settings.security.capture_rate_per_minute == 6
    assert settings.security.capture_rate_burst == 2
    assert settings.security.authentication_rate_per_second == 5
    assert settings.security.authentication_rate_burst == 10
    assert settings.security.max_concurrent_authentications == 4
    assert settings.security.request_rate_per_second == 100
    assert settings.security.request_rate_burst == 200
    assert settings.security.audio_packet_rate_per_second == 60
    assert settings.security.audio_packet_rate_burst == 100
    assert settings.automation.expression_enabled is True


def test_config_rejects_recording_duration_above_protocol_limit() -> None:
    with pytest.raises(ValidationError):
        load_settings(
            environment={},
            cli_overrides={"audio": {"max_recording_ms": 15_001}},
        )


@pytest.mark.parametrize(
    "cli_overrides",
    [
        {"control_api": {"host": "0.0.0.0"}},
        {"hermes": {"base_url": "http://192.0.2.10:8642"}},
    ],
)
def test_config_rejects_non_loopback_management_surfaces(
    cli_overrides: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        load_settings(
            environment={},
            cli_overrides=cli_overrides,
        )


def test_config_supports_named_secrets_for_http_stt_and_voicevox_tts() -> None:
    stt_key = "runtime-stt-key"  # pragma: allowlist secret
    settings = load_settings(
        environment={"LOCAL_STT_API_KEY": stt_key},
        cli_overrides={
            "stt": {
                "adapter": "http",
                "endpoint": "https://stt.example.test/v1/audio/transcriptions",
                "api_key_env": "LOCAL_STT_API_KEY",  # pragma: allowlist secret
            },
            "tts": {
                "adapter": "voicevox",
                "endpoint": "http://127.0.0.1:50021",
                "speaker": 3,
            },
        },
    )

    assert settings.stt.endpoint == "https://stt.example.test/v1/audio/transcriptions"
    assert settings.stt.api_key is not None
    assert settings.stt.api_key.get_secret_value() == stt_key
    assert settings.tts.endpoint == "http://127.0.0.1:50021"
    assert settings.tts.speaker == 3
    assert stt_key not in repr(settings)


def test_config_supports_faster_whisper_runtime_selection() -> None:
    settings = load_settings(
        environment={},
        cli_overrides={
            "stt": {
                "adapter": "faster-whisper",
                "model_name": "small",
                "device": "cpu",
                "compute_type": "int8",
            }
        },
    )

    assert settings.stt.model_name == "small"
    assert settings.stt.device == "cpu"
    assert settings.stt.compute_type == "int8"


def test_config_supports_openai_tts_with_named_secret_and_speed_default() -> None:
    api_key = "runtime-irodori-key"  # pragma: allowlist secret
    settings = load_settings(
        environment={"LOCAL_TTS_API_KEY": api_key},
        cli_overrides={
            "tts": {
                "adapter": "openai",
                "endpoint": "http://127.0.0.1:8088/v1/audio/speech",
                "model": "irodori-tts",
                "voice": "sample",
                "api_key_env": "LOCAL_TTS_API_KEY",  # pragma: allowlist secret
            }
        },
    )

    assert settings.tts.adapter == "openai"
    assert settings.tts.endpoint == "http://127.0.0.1:8088/v1/audio/speech"
    assert settings.tts.model == "irodori-tts"
    assert settings.tts.voice == "sample"
    assert settings.tts.speed == 1.0
    assert settings.tts.irodori.caption is None
    assert settings.tts.irodori.seed is None
    assert settings.tts.api_key is not None
    assert settings.tts.api_key.get_secret_value() == api_key
    assert api_key not in repr(settings)


@pytest.mark.parametrize(
    ("environment", "caption", "seed"),
    [
        ({}, "明るく親しみやすい声。", 1234),
        (
            {
                "STACKCHAN_TTS__IRODORI__CAPTION": "穏やかに話す。",
                "STACKCHAN_TTS__IRODORI__SEED": "0",
            },
            "穏やかに話す。",
            0,
        ),
    ],
)
def test_config_loads_irodori_options_with_environment_overrides(
    tmp_path: Path, environment: dict[str, str], caption: str, seed: int
) -> None:
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[tts]
adapter = "openai"
endpoint = "http://127.0.0.1:8088/v1/audio/speech"
model = "irodori-tts"
voice = "sample"

[tts.irodori]
caption = "明るく親しみやすい声。"
seed = 1234
""".strip(),
        encoding="utf-8",
    )

    settings = load_settings(config_path, environment=environment)

    assert settings.tts.irodori.caption == caption
    assert settings.tts.irodori.seed == seed


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("caption", 123),
        ("caption", True),
        ("caption", ["穏やかに話す。"]),
        ("seed", True),
        ("seed", 1.0),
        ("seed", 1.5),
        ("seed", "1234"),
        ("unknown_option", "value"),
    ],
)
def test_config_rejects_invalid_irodori_options(name: str, value: object) -> None:
    with pytest.raises(ValidationError) as raised:
        load_settings(
            environment={},
            cli_overrides={
                "tts": {
                    "adapter": "openai",
                    "endpoint": "http://127.0.0.1:8088/v1/audio/speech",
                    "model": "irodori-tts",
                    "voice": "sample",
                    "irodori": {name: value},
                }
            },
        )

    assert raised.value.errors()[0]["loc"] == ("tts", "irodori", name)


@pytest.mark.parametrize(
    "overrides",
    [
        {"endpoint": None},
        {"model": None},
        {"model": ""},
        {"model": " \t"},
        {"voice": None},
        {"voice": ""},
        {"voice": " \t"},
        {"speed": 0.24},
        {"speed": 4.01},
        {"speed": float("nan")},
        {"speed": float("inf")},
        {"endpoint": "http://192.0.2.1:8088/v1/audio/speech"},
        {"endpoint": "https://tts.example.test/v1/audio/speech?token=private"},
    ],
)
def test_config_rejects_invalid_openai_tts_settings(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        load_settings(
            environment={},
            cli_overrides={
                "tts": {
                    "adapter": "openai",
                    "endpoint": "http://127.0.0.1:8088/v1/audio/speech",
                    "model": "irodori-tts",
                    "voice": "sample",
                    **overrides,
                }
            },
        )


@pytest.mark.parametrize("speed", [0.25, 1.25, 4.0])
def test_config_supports_openai_tts_environment_overrides(speed: float) -> None:
    settings = load_settings(
        environment={
            "STACKCHAN_TTS__ADAPTER": "openai",
            "STACKCHAN_TTS__ENDPOINT": "http://127.0.0.1:8088/v1/audio/speech",
            "STACKCHAN_TTS__MODEL": "irodori-tts",
            "STACKCHAN_TTS__VOICE": "sample",
            "STACKCHAN_TTS__SPEED": str(speed),
        }
    )

    assert settings.tts.speed == speed
    assert settings.tts.api_key is None


@pytest.mark.parametrize(
    "cli_overrides",
    [
        {"stt": {"adapter": "http"}},
        {"tts": {"adapter": "voicevox"}},
        {
            "stt": {
                "adapter": "http",
                "endpoint": "http://stt.example.test/v1/transcriptions",
            }
        },
        {
            "tts": {
                "adapter": "http",
                "endpoint": (
                    "https://user:password@tts.example.test/speech"  # pragma: allowlist secret
                ),
            }
        },
    ],
)
def test_config_rejects_missing_or_unsafe_provider_endpoints(
    cli_overrides: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        load_settings(environment={}, cli_overrides=cli_overrides)


def test_config_exposes_all_rms_vad_thresholds() -> None:
    settings = load_settings(
        environment={},
        cli_overrides={
            "vad": {
                "start_threshold": 900,
                "end_threshold": 400,
                "initial_noise_floor": 40,
                "noise_floor_alpha": 0.1,
                "noise_start_ratio": 3.5,
                "noise_end_ratio": 1.5,
            }
        },
    )

    assert settings.vad.start_threshold == 900
    assert settings.vad.end_threshold == 400
    assert settings.vad.initial_noise_floor == 40
    assert settings.vad.noise_floor_alpha == 0.1
    assert settings.vad.noise_start_ratio == 3.5
    assert settings.vad.noise_end_ratio == 1.5


def test_config_supports_bounded_mdns_advertisement() -> None:
    settings = load_settings(
        environment={},
        cli_overrides={
            "mdns": {
                "enabled": True,
                "service_name": "living-room-stackchan",
                "hostname": "bridge-host",
            }
        },
    )

    assert settings.mdns.enabled is True
    assert settings.mdns.service_name == "living-room-stackchan"
    assert settings.mdns.hostname == "bridge-host"


@pytest.mark.parametrize(
    "cli_overrides",
    [
        {"hermes": {"allow_chat_completions_fallback": True}},
        {"device_gateway": {"websocket_path": "/custom/device/ws"}},
        {
            "device_gateway": {
                "capture_upload_path": "/custom/captures/{capture_id}",
            }
        },
    ],
)
def test_config_rejects_options_that_the_runtime_cannot_honor(
    cli_overrides: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        load_settings(environment={}, cli_overrides=cli_overrides)
