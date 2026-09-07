from __future__ import annotations

import re
import tomllib
from pathlib import Path

from stackchan_bridge.config import load_settings
from stackchan_bridge.protocol.models import MAX_AUDIO_PACKET_BYTES, MAX_JSON_BYTES

ROOT = Path(__file__).resolve().parents[2]


def test_toml_example_is_parseable_and_preserves_network_boundaries() -> None:
    with (ROOT / "config.example.toml").open("rb") as file:
        config = tomllib.load(file)

    assert config["device_gateway"]["host"] == "0.0.0.0"
    assert config["control_api"]["host"] == "127.0.0.1"
    assert config["hermes"]["base_url"] == "http://127.0.0.1:8642"
    assert config["hermes"]["api_key_env"] == "HERMES_API_KEY"  # pragma: allowlist secret
    assert "api_key" not in config["hermes"]
    assert config["device_gateway"]["max_json_bytes"] == MAX_JSON_BYTES
    assert config["device_gateway"]["max_audio_packet_bytes"] == MAX_AUDIO_PACKET_BYTES
    assert config["stt"]["api_key_env"] == "STACKCHAN_STT_API_KEY"  # pragma: allowlist secret
    assert config["stt"]["model_name"] == "small"
    assert config["stt"]["device"] == "auto"
    assert config["stt"]["compute_type"] == "default"
    assert config["tts"]["api_key_env"] == "STACKCHAN_TTS_API_KEY"  # pragma: allowlist secret
    assert config["tts"]["speaker"] == 1
    assert config["audio"]["debug_save_enabled"] is False
    assert config["audio"]["debug_directory"] == ".local/debug-audio"
    assert config["audio"]["debug_ttl_seconds"] == 3600
    assert config["security"]["authentication_rate_per_second"] == 5
    assert config["security"]["authentication_rate_burst"] == 10
    assert config["security"]["max_concurrent_authentications"] == 4
    assert config["security"]["request_rate_per_second"] == 100
    assert config["security"]["request_rate_burst"] == 200
    assert config["security"]["audio_packet_rate_per_second"] == 60
    assert config["security"]["audio_packet_rate_burst"] == 100
    assert config["security"]["capture_rate_burst"] == 2


def test_environment_example_contains_names_only_not_secret_values() -> None:
    environment = (ROOT / ".env.example").read_text(encoding="utf-8")

    assert "HERMES_API_KEY=" in environment
    assert "STACKCHAN_DEVICE_TOKEN=" in environment
    assert "STACKCHAN_STT_API_KEY=" in environment
    assert "STACKCHAN_TTS_API_KEY=" in environment
    assert "change-me" not in environment.lower()
    assert "bearer " not in environment.lower()


def test_readme_irodori_example_loads_as_openai_tts_configuration() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    examples = [
        tomllib.loads(block)
        for block in re.findall(r"```toml\n(.*?)```", readme, flags=re.DOTALL)
        if 'adapter = "openai"' in block
    ]
    assert len(examples) == 1
    settings = load_settings(environment={}, cli_overrides=examples[0])

    assert settings.tts.adapter == "openai"
    assert settings.tts.endpoint == "http://127.0.0.1:8088/v1/audio/speech"
    assert settings.tts.model == "irodori-tts"
    assert settings.tts.voice == "sample"
    assert settings.tts.speed == 1.0
    assert settings.tts.timeout_seconds == 120
    assert settings.tts.api_key is None


def test_hermes_example_uses_stdio_mcp_and_not_dashboard_websocket() -> None:
    example = (ROOT / "examples/hermes-config.yaml").read_text(encoding="utf-8")

    assert "stackchan-mcp" in example
    assert "http://127.0.0.1:8766" in example
    assert "/api/ws" not in example
