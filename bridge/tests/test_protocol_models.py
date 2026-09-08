from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from stackchan_bridge.protocol.models import (
    MAX_JSON_BYTES,
    AudioInputEndMessage,
    AudioInputStartMessage,
    AudioOutputEndMessage,
    AudioOutputStartMessage,
    CommandMessage,
    CommandResultMessage,
    ErrorMessage,
    EventMessage,
    HelloAckMessage,
    HelloMessage,
    ProtocolErrorCode,
    ProtocolMessageError,
    negotiate_protocol_version,
    parse_hello_frame,
    parse_text_frame,
)

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "protocol" / "examples" / "manifest.json"


def load_example(name: str) -> object:
    path = ROOT / "protocol" / "examples" / name
    return json.loads(path.read_text(encoding="utf-8"))


def manifest_entries() -> list[dict[str, object]]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert isinstance(manifest, dict)
    entries = manifest["examples"]
    assert isinstance(entries, list)
    assert all(isinstance(entry, dict) for entry in entries)
    return entries


def test_valid_hello_example_is_accepted() -> None:
    message = HelloMessage.model_validate(load_example("hello.valid.json"))

    assert message.v == 1
    assert message.payload.device_id == "stackchan-001"
    assert message.payload.audio.frame_ms == 60


@pytest.mark.parametrize(
    "name",
    ["hello.invalid-version.json", "hello.invalid-control-character.json"],
)
def test_invalid_hello_examples_are_rejected(name: str) -> None:
    with pytest.raises(ValidationError):
        HelloMessage.model_validate(load_example(name))


def test_oversized_hello_frame_is_rejected_before_validation() -> None:
    example = load_example("hello.valid.json")
    assert isinstance(example, dict)
    example["future_padding"] = "x" * MAX_JSON_BYTES
    frame = json.dumps(example).encode()

    with pytest.raises(ProtocolMessageError) as error:
        parse_hello_frame(frame)

    assert error.value.code is ProtocolErrorCode.INVALID_MESSAGE
    assert "16,384 bytes" in str(error.value)


def test_hello_frame_deeper_than_eight_levels_is_rejected() -> None:
    example = load_example("hello.valid.json")
    assert isinstance(example, dict)
    nested: object = "leaf"
    for _ in range(8):
        nested = {"next": nested}
    example["future_nested"] = nested

    with pytest.raises(ProtocolMessageError) as error:
        parse_hello_frame(json.dumps(example))

    assert error.value.code is ProtocolErrorCode.INVALID_MESSAGE
    assert "8 levels" in str(error.value)


def test_hello_device_id_must_match_authenticated_header() -> None:
    message = HelloMessage.model_validate(load_example("hello.valid.json"))

    with pytest.raises(ProtocolMessageError) as error:
        negotiate_protocol_version(message, authenticated_device_id="different-device")

    assert error.value.code is ProtocolErrorCode.UNKNOWN_DEVICE


def test_hello_requires_a_mutually_supported_protocol_version() -> None:
    example = load_example("hello.valid.json")
    assert isinstance(example, dict)
    payload = example["payload"]
    assert isinstance(payload, dict)
    payload["protocol_versions"] = [2]
    message = HelloMessage.model_validate(example)

    with pytest.raises(ProtocolMessageError) as error:
        negotiate_protocol_version(message, authenticated_device_id="stackchan-001")

    assert error.value.code is ProtocolErrorCode.UNSUPPORTED_VERSION


def test_valid_hello_ack_example_is_accepted() -> None:
    message = HelloAckMessage.model_validate(load_example("control-hello-ack.valid.json"))

    assert message.payload.selected_protocol_version == 1
    assert message.payload.heartbeat_interval_ms == 15_000
    assert message.payload.max_command_timeout_ms == 5_000


def test_valid_audio_control_examples_are_accepted() -> None:
    input_start = AudioInputStartMessage.model_validate(
        load_example("control-audio-input-start.valid.json")
    )
    input_end = AudioInputEndMessage.model_validate(
        load_example("control-audio-input-end.valid.json")
    )
    output_start = AudioOutputStartMessage.model_validate(
        load_example("control-audio-output-start.valid.json")
    )
    output_end = AudioOutputEndMessage.model_validate(
        load_example("control-audio-output-end.valid.json")
    )

    assert input_start.payload.trigger == "touch"
    assert input_end.payload.reason == "silence"
    assert output_start.payload.expected_duration_ms == 1_800
    assert output_end.payload.reason == "completed"


@pytest.mark.parametrize(
    ("name", "args"),
    [
        ("device.get_status", {}),
        ("device.get_info", {}),
        ("audio.set_volume", {"volume": 75}),
        ("display.set_brightness", {"brightness": 80}),
        (
            "display.show_text",
            {"text": "接続しました", "duration_ms": 2_000, "priority": 5},
        ),
        ("avatar.set_expression", {"expression": "happy"}),
        ("avatar.set_blink", {"enabled": True}),
        ("head.get_angles", {}),
        ("head.set_angles", {"yaw": 15, "pitch": 40, "speed": 30}),
        ("head.home", {"speed": 20}),
        ("led.set", {"index": 3, "r": 255, "g": 64, "b": 0}),
        ("led.set_all", {"r": 0, "g": 32, "b": 255}),
        ("led.clear", {}),
        (
            "camera.capture",
            {
                "timeout_ms": 10000,
                "capture_id": "db4d04eb-e319-47bb-896b-cd44bc71088d",
                "quality": 80,
            },
        ),
        ("speech.cancel", {}),
    ],
)
def test_all_v1_commands_accept_their_typed_arguments(name: str, args: dict[str, object]) -> None:
    command: dict[str, object] = {
        "v": 1,
        "type": "command",
        "message_id": "f3004cb2-d1be-4823-a0d9-730f6759763a",
        "request_id": "a2680ddb-b4a2-416a-8327-4ecbbab12f99",
        "sent_at_ms": 1,
        "payload": {"name": name, "args": args},
    }
    if name == "speech.cancel":
        command["turn_id"] = "0819e40d-71f3-4d44-9a31-928358122a83"

    message = CommandMessage.model_validate(command)

    assert message.payload.name == name


def test_checked_in_head_command_is_accepted() -> None:
    message = CommandMessage.model_validate(load_example("command-head-set-angles.valid.json"))

    assert message.payload.name == "head.set_angles"
    assert message.payload.args.pitch == 40


def test_valid_command_result_and_error_examples_are_accepted() -> None:
    success = CommandResultMessage.model_validate(
        load_example("control-command-result-success.valid.json")
    )
    failure = CommandResultMessage.model_validate(
        load_example("control-command-result-error.valid.json")
    )
    protocol_error = ErrorMessage.model_validate(load_example("control-error.valid.json"))

    assert success.payload.ok is True
    assert failure.payload.ok is False
    assert failure.payload.error.code is ProtocolErrorCode.INVALID_ARGUMENT
    assert protocol_error.payload.code is ProtocolErrorCode.INVALID_STATE


@pytest.mark.parametrize(
    ("name", "data"),
    [
        ("touch.tap", {"x": 160, "y": 120}),
        ("touch.long_press", {"x": 160, "y": 120, "duration_ms": 750}),
        (
            "touch.stroke",
            {
                "start_x": 20,
                "start_y": 30,
                "end_x": 200,
                "end_y": 180,
                "duration_ms": 500,
            },
        ),
        ("button.press", {"button": "side"}),
        ("wakeword.detected", {"confidence": 0.92}),
        ("battery.changed", {"percent": 85, "charging": False}),
        ("wifi.changed", {"connected": True, "rssi_dbm": -58}),
        (
            "audio.underrun",
            {"stream_id": "c0405bef-ed4c-457a-8286-1cba770b4b29", "dropped_packets": 2},
        ),
        (
            "audio.overflow",
            {"stream_id": "c0405bef-ed4c-457a-8286-1cba770b4b29", "dropped_packets": 1},
        ),
        (
            "camera.completed",
            {
                "sha256": "0000000000000000000000000000000000000000000000000000000000000000",
                "size_bytes": 128,
                "capture_id": "4936d914-cef8-443e-830a-d3c717ccc178",
                "ok": True,
            },
        ),
        ("servo.error", {"code": "SERVO_OFFLINE", "message": "servo is unavailable"}),
        ("device.error", {"code": "AUDIO_INIT", "message": "audio setup failed"}),
    ],
)
def test_all_v1_events_accept_their_typed_data(name: str, data: dict[str, object]) -> None:
    event = EventMessage.model_validate(
        {
            "v": 1,
            "type": "event",
            "message_id": "d7c54bc1-ec6b-48a7-a2d0-c2f01edb5dfb",
            "device_id": "stackchan-001",
            "sent_at_ms": 0,
            "payload": {"name": name, "data": data},
        }
    )

    assert event.payload.name == name


def test_checked_in_touch_event_is_accepted() -> None:
    event = EventMessage.model_validate(load_example("event-touch-tap.valid.json"))

    assert event.payload.name == "touch.tap"
    assert event.payload.data.x == 160


@pytest.mark.parametrize(
    ("fixture", "expected_type"),
    [
        ("hello.valid.json", HelloMessage),
        ("control-hello-ack.valid.json", HelloAckMessage),
        ("control-audio-input-start.valid.json", AudioInputStartMessage),
        ("control-audio-input-end.valid.json", AudioInputEndMessage),
        ("control-audio-output-start.valid.json", AudioOutputStartMessage),
        ("control-audio-output-end.valid.json", AudioOutputEndMessage),
        ("command-head-set-angles.valid.json", CommandMessage),
        ("control-command-result-success.valid.json", CommandResultMessage),
        ("control-command-result-error.valid.json", CommandResultMessage),
        ("event-touch-tap.valid.json", EventMessage),
        ("control-error.valid.json", ErrorMessage),
    ],
)
def test_generic_text_parser_dispatches_every_valid_example(
    fixture: str,
    expected_type: type[object],
) -> None:
    frame = json.dumps(load_example(fixture), ensure_ascii=False)

    assert isinstance(parse_text_frame(frame), expected_type)


@pytest.mark.parametrize("entry", manifest_entries(), ids=lambda entry: str(entry["path"]))
def test_checked_in_examples_have_pydantic_schema_parity(entry: dict[str, object]) -> None:
    frame = json.dumps(load_example(str(entry["path"])), ensure_ascii=False)

    if entry["valid"] is True:
        parse_text_frame(frame)
    else:
        with pytest.raises(ProtocolMessageError):
            parse_text_frame(frame)
