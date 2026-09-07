"""Pydantic representations of StackChan protocol v1 messages."""

from __future__ import annotations

import json
from enum import StrEnum
from typing import Annotated, Literal, Never, Self
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StringConstraints,
    TypeAdapter,
    ValidationError,
    field_validator,
    model_validator,
)

MAX_JSON_BYTES = 16_384
MAX_JSON_DEPTH = 8
MAX_AUDIO_PACKET_BYTES = 1_275


class ProtocolErrorCode(StrEnum):
    """Stable protocol error codes shared with Firmware."""

    INVALID_MESSAGE = "INVALID_MESSAGE"
    UNKNOWN_DEVICE = "UNKNOWN_DEVICE"
    UNSUPPORTED_VERSION = "UNSUPPORTED_VERSION"
    UNAUTHORIZED = "UNAUTHORIZED"
    INVALID_ARGUMENT = "INVALID_ARGUMENT"
    INVALID_STATE = "INVALID_STATE"
    COMMAND_TIMEOUT = "COMMAND_TIMEOUT"
    DEVICE_BUSY = "DEVICE_BUSY"
    AUDIO_DECODE_ERROR = "AUDIO_DECODE_ERROR"
    AUDIO_ENCODE_ERROR = "AUDIO_ENCODE_ERROR"
    CAPTURE_FAILED = "CAPTURE_FAILED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ProtocolMessageError(ValueError):
    """A text frame that cannot be accepted as a protocol message."""

    def __init__(self, code: ProtocolErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code


DeviceId = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$",
    ),
]
ShortName = Annotated[
    str,
    StringConstraints(min_length=1, max_length=64, pattern=r"^[^\x00-\x1F\x7F]+$"),
]
VersionName = Annotated[
    str,
    StringConstraints(min_length=1, max_length=32, pattern=r"^[^\x00-\x1F\x7F]+$"),
]
TimestampMilliseconds = Annotated[int, Field(ge=0, le=9_223_372_036_854_775_807)]
PositiveProtocolVersion = Annotated[int, Field(ge=1)]
ProtocolUUID = Annotated[UUID, Field(strict=False)]


class ProtocolModel(BaseModel):
    """Base model with strict known fields and forward-compatible extras."""

    model_config = ConfigDict(extra="allow", strict=True)


class Envelope(ProtocolModel):
    """Fields shared by every JSON protocol message."""

    v: Literal[1]
    type: Annotated[str, StringConstraints(min_length=1, max_length=64)]
    message_id: ProtocolUUID
    sent_at_ms: TimestampMilliseconds
    request_id: ProtocolUUID | None = None
    turn_id: ProtocolUUID | None = None
    stream_id: ProtocolUUID | None = None
    device_id: DeviceId | None = None


class DeviceCapabilities(ProtocolModel):
    """Physical features advertised by a device."""

    microphone: bool
    speaker: bool
    camera: bool
    touch: bool
    head: bool
    display: bool
    avatar: bool
    led_count: Annotated[int, Field(ge=0, le=256)]


class AudioFormat(ProtocolModel):
    """Audio format negotiated for a connection."""

    codec: Literal["opus"]
    sample_rate: Literal[16000]
    channels: Literal[1]
    frame_ms: Literal[20, 40, 60]


class HelloPayload(ProtocolModel):
    """Identity, capability, and codec data sent during handshake."""

    device_id: DeviceId
    device_name: ShortName
    firmware_version: VersionName
    hardware_model: ShortName
    protocol_versions: Annotated[
        list[PositiveProtocolVersion],
        Field(min_length=1, max_length=8),
    ]
    capabilities: DeviceCapabilities
    audio: AudioFormat

    @field_validator("protocol_versions")
    @classmethod
    def require_unique_protocol_versions(cls, value: list[int]) -> list[int]:
        if len(value) != len(set(value)):
            raise ValueError("protocol_versions must contain unique values")
        return value


class HelloMessage(Envelope):
    """First authenticated message sent by Firmware."""

    type: Literal["hello"]
    payload: HelloPayload


class HelloAckPayload(ProtocolModel):
    """Protocol and timing values selected by the Bridge."""

    connection_id: ProtocolUUID
    selected_protocol_version: Literal[1]
    heartbeat_interval_ms: Annotated[int, Field(ge=1_000, le=60_000)]
    max_command_timeout_ms: Annotated[int, Field(ge=100, le=30_000)]
    server_version: VersionName


class HelloAckMessage(Envelope):
    """Bridge acknowledgement completing a device handshake."""

    type: Literal["hello_ack"]
    payload: HelloAckPayload


class StreamEnvelope(Envelope):
    """Envelope fields required for an audio stream control message."""

    turn_id: ProtocolUUID
    stream_id: ProtocolUUID


class AudioInputStartPayload(AudioFormat):
    """Negotiated input format and local trigger."""

    trigger: Literal["touch", "button", "wakeword", "control_api", "simulator"]


class AudioInputStartMessage(StreamEnvelope):
    """Firmware starts one microphone stream."""

    type: Literal["audio.input.start"]
    payload: AudioInputStartPayload


class AudioInputEndPayload(ProtocolModel):
    """Reason Firmware ended microphone input."""

    reason: Literal["silence", "max_duration", "user_cancel", "device_error", "disconnect"]


class AudioInputEndMessage(StreamEnvelope):
    """Firmware ends the current microphone stream."""

    type: Literal["audio.input.end"]
    payload: AudioInputEndPayload


class AudioOutputStartPayload(AudioFormat):
    """Negotiated playback format and estimated duration."""

    expected_duration_ms: Annotated[int, Field(ge=0, le=120_000)]


class AudioOutputStartMessage(StreamEnvelope):
    """Bridge starts one playback stream."""

    type: Literal["audio.output.start"]
    payload: AudioOutputStartPayload


class AudioOutputEndPayload(ProtocolModel):
    """Reason Bridge ended playback output."""

    reason: Literal[
        "completed",
        "cancelled",
        "barge_in",
        "tts_error",
        "device_error",
        "disconnect",
    ]


class AudioOutputEndMessage(StreamEnvelope):
    """Bridge ends the current playback stream."""

    type: Literal["audio.output.end"]
    payload: AudioOutputEndPayload


class CommandArguments(ProtocolModel):
    """Command arguments reject fields not defined for that command."""

    model_config = ConfigDict(extra="forbid", strict=True)


class EmptyArguments(CommandArguments):
    """Explicitly empty command arguments."""


class SetVolumeArguments(CommandArguments):
    volume: Annotated[int, Field(ge=0, le=100)]


class SetBrightnessArguments(CommandArguments):
    brightness: Annotated[int, Field(ge=0, le=100)]


class ShowTextArguments(CommandArguments):
    text: Annotated[str, StringConstraints(min_length=1, max_length=256)]
    duration_ms: Annotated[int, Field(ge=100, le=30_000)]
    priority: Annotated[int, Field(ge=0, le=10)]


class SetExpressionArguments(CommandArguments):
    expression: Literal["idle", "happy", "thinking", "sad", "surprised", "embarrassed"]


class SetBlinkArguments(CommandArguments):
    enabled: bool


ProtocolAngle = Annotated[int | float, Field(ge=-90, le=90)]
MotionSpeed = Annotated[int, Field(ge=1, le=100)]


class SetHeadAnglesArguments(CommandArguments):
    yaw: ProtocolAngle
    pitch: ProtocolAngle
    speed: MotionSpeed | None = None


class HomeHeadArguments(CommandArguments):
    speed: MotionSpeed | None = None


RgbValue = Annotated[int, Field(ge=0, le=255)]


class SetLedArguments(CommandArguments):
    index: Annotated[int, Field(ge=0, le=255)]
    r: RgbValue
    g: RgbValue
    b: RgbValue


class SetAllLedsArguments(CommandArguments):
    r: RgbValue
    g: RgbValue
    b: RgbValue


class CaptureArguments(CommandArguments):
    capture_id: ProtocolUUID
    quality: Annotated[int, Field(ge=10, le=95)]


class CommandPayloadModel(ProtocolModel):
    """Command payloads have exactly a name and typed arguments."""

    model_config = ConfigDict(extra="forbid", strict=True)


class GetStatusCommand(CommandPayloadModel):
    name: Literal["device.get_status"]
    args: EmptyArguments


class GetInfoCommand(CommandPayloadModel):
    name: Literal["device.get_info"]
    args: EmptyArguments


class SetVolumeCommand(CommandPayloadModel):
    name: Literal["audio.set_volume"]
    args: SetVolumeArguments


class SetBrightnessCommand(CommandPayloadModel):
    name: Literal["display.set_brightness"]
    args: SetBrightnessArguments


class ShowTextCommand(CommandPayloadModel):
    name: Literal["display.show_text"]
    args: ShowTextArguments


class SetExpressionCommand(CommandPayloadModel):
    name: Literal["avatar.set_expression"]
    args: SetExpressionArguments


class SetBlinkCommand(CommandPayloadModel):
    name: Literal["avatar.set_blink"]
    args: SetBlinkArguments


class GetHeadAnglesCommand(CommandPayloadModel):
    name: Literal["head.get_angles"]
    args: EmptyArguments


class SetHeadAnglesCommand(CommandPayloadModel):
    name: Literal["head.set_angles"]
    args: SetHeadAnglesArguments


class HomeHeadCommand(CommandPayloadModel):
    name: Literal["head.home"]
    args: HomeHeadArguments


class SetLedCommand(CommandPayloadModel):
    name: Literal["led.set"]
    args: SetLedArguments


class SetAllLedsCommand(CommandPayloadModel):
    name: Literal["led.set_all"]
    args: SetAllLedsArguments


class ClearLedsCommand(CommandPayloadModel):
    name: Literal["led.clear"]
    args: EmptyArguments


class CaptureCommand(CommandPayloadModel):
    name: Literal["camera.capture"]
    args: CaptureArguments


class CancelSpeechCommand(CommandPayloadModel):
    name: Literal["speech.cancel"]
    args: EmptyArguments


CommandPayload = Annotated[
    GetStatusCommand
    | GetInfoCommand
    | SetVolumeCommand
    | SetBrightnessCommand
    | ShowTextCommand
    | SetExpressionCommand
    | SetBlinkCommand
    | GetHeadAnglesCommand
    | SetHeadAnglesCommand
    | HomeHeadCommand
    | SetLedCommand
    | SetAllLedsCommand
    | ClearLedsCommand
    | CaptureCommand
    | CancelSpeechCommand,
    Field(discriminator="name"),
]


class CommandMessage(Envelope):
    """A bounded, typed command sent from Bridge to Firmware."""

    type: Literal["command"]
    request_id: ProtocolUUID
    payload: CommandPayload

    @model_validator(mode="after")
    def require_turn_for_speech_cancel(self) -> Self:
        if self.payload.name == "speech.cancel" and self.turn_id is None:
            raise ValueError("speech.cancel requires turn_id")
        return self


UserSafeMessage = Annotated[
    str,
    StringConstraints(min_length=1, max_length=160, pattern=r"^[^\x00-\x1F\x7F]+$"),
]
DiagnosticMessage = Annotated[
    str,
    StringConstraints(min_length=1, max_length=512, pattern=r"^[^\x00-\x1F\x7F]+$"),
]


class ErrorPayload(ProtocolModel):
    """Stable code plus separated user-safe and diagnostic text."""

    code: Annotated[ProtocolErrorCode, Field(strict=False)]
    message: UserSafeMessage
    detail: DiagnosticMessage | None = None


class SuccessfulCommandResult(ProtocolModel):
    """A successful command result with bounded JSON data."""

    model_config = ConfigDict(extra="forbid", strict=True)

    ok: Literal[True]
    result: Annotated[dict[str, JsonValue], Field(max_length=32)]


class FailedCommandResult(ProtocolModel):
    """A rejected or failed command result."""

    model_config = ConfigDict(extra="forbid", strict=True)

    ok: Literal[False]
    error: ErrorPayload


CommandResultPayload = Annotated[
    SuccessfulCommandResult | FailedCommandResult,
    Field(discriminator="ok"),
]


class CommandResultMessage(Envelope):
    """Firmware response correlated to one Bridge command."""

    type: Literal["command_result"]
    request_id: ProtocolUUID
    payload: CommandResultPayload


class ErrorMessage(Envelope):
    """A protocol error not represented as a command result."""

    type: Literal["error"]
    payload: ErrorPayload


DisplayX = Annotated[int, Field(ge=0, le=319)]
DisplayY = Annotated[int, Field(ge=0, le=239)]
StableDeviceCode = Annotated[
    str,
    StringConstraints(min_length=1, max_length=64, pattern=r"^[A-Z0-9][A-Z0-9._-]*$"),
]


class EventData(ProtocolModel):
    """Base for forward-compatible, bounded event-specific data."""


class TouchTapData(EventData):
    x: DisplayX
    y: DisplayY


class TouchLongPressData(TouchTapData):
    duration_ms: Annotated[int, Field(ge=500, le=30_000)]


class TouchStrokeData(EventData):
    start_x: DisplayX
    start_y: DisplayY
    end_x: DisplayX
    end_y: DisplayY
    duration_ms: Annotated[int, Field(ge=1, le=30_000)]


class ButtonPressData(EventData):
    button: Annotated[
        str,
        StringConstraints(min_length=1, max_length=32, pattern=r"^[^\x00-\x1F\x7F]+$"),
    ]


class WakewordData(EventData):
    confidence: Annotated[int | float, Field(ge=0, le=1)] | None = None


class BatteryData(EventData):
    percent: Annotated[int, Field(ge=0, le=100)]
    charging: bool


class WifiData(EventData):
    connected: bool
    rssi_dbm: Annotated[int, Field(ge=-127, le=0)] | None = None


class AudioBufferData(EventData):
    stream_id: ProtocolUUID
    dropped_packets: Annotated[int, Field(ge=1, le=65_535)]


class CameraCompletedData(EventData):
    capture_id: ProtocolUUID
    ok: bool
    error_code: Annotated[ProtocolErrorCode, Field(strict=False)] | None = None


class DeviceFaultData(EventData):
    code: StableDeviceCode
    message: UserSafeMessage


class EventPayloadModel(ProtocolModel):
    """Event name discriminates its typed data object."""


class TouchTapEvent(EventPayloadModel):
    name: Literal["touch.tap"]
    data: TouchTapData


class TouchLongPressEvent(EventPayloadModel):
    name: Literal["touch.long_press"]
    data: TouchLongPressData


class TouchStrokeEvent(EventPayloadModel):
    name: Literal["touch.stroke"]
    data: TouchStrokeData


class ButtonPressEvent(EventPayloadModel):
    name: Literal["button.press"]
    data: ButtonPressData


class WakewordEvent(EventPayloadModel):
    name: Literal["wakeword.detected"]
    data: WakewordData


class BatteryEvent(EventPayloadModel):
    name: Literal["battery.changed"]
    data: BatteryData


class WifiEvent(EventPayloadModel):
    name: Literal["wifi.changed"]
    data: WifiData


class AudioUnderrunEvent(EventPayloadModel):
    name: Literal["audio.underrun"]
    data: AudioBufferData


class AudioOverflowEvent(EventPayloadModel):
    name: Literal["audio.overflow"]
    data: AudioBufferData


class CameraCompletedEvent(EventPayloadModel):
    name: Literal["camera.completed"]
    data: CameraCompletedData


class ServoErrorEvent(EventPayloadModel):
    name: Literal["servo.error"]
    data: DeviceFaultData


class DeviceErrorEvent(EventPayloadModel):
    name: Literal["device.error"]
    data: DeviceFaultData


EventPayload = Annotated[
    TouchTapEvent
    | TouchLongPressEvent
    | TouchStrokeEvent
    | ButtonPressEvent
    | WakewordEvent
    | BatteryEvent
    | WifiEvent
    | AudioUnderrunEvent
    | AudioOverflowEvent
    | CameraCompletedEvent
    | ServoErrorEvent
    | DeviceErrorEvent,
    Field(discriminator="name"),
]


class EventMessage(Envelope):
    """A bounded physical or device-health event from Firmware."""

    type: Literal["event"]
    device_id: DeviceId
    payload: EventPayload


ProtocolMessage = Annotated[
    HelloMessage
    | HelloAckMessage
    | AudioInputStartMessage
    | AudioInputEndMessage
    | AudioOutputStartMessage
    | AudioOutputEndMessage
    | CommandMessage
    | CommandResultMessage
    | EventMessage
    | ErrorMessage,
    Field(discriminator="type"),
]
_PROTOCOL_MESSAGE_ADAPTER: TypeAdapter[ProtocolMessage] = TypeAdapter(ProtocolMessage)


def parse_text_frame(frame: str | bytes) -> ProtocolMessage:
    """Validate and dispatch one bounded protocol JSON frame."""

    encoded = frame.encode("utf-8") if isinstance(frame, str) else frame
    if len(encoded) > MAX_JSON_BYTES:
        raise ProtocolMessageError(
            ProtocolErrorCode.INVALID_MESSAGE,
            f"JSON frame exceeds {MAX_JSON_BYTES:,} bytes",
        )
    try:
        document: object = json.loads(encoded, parse_constant=_reject_json_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise ProtocolMessageError(
            ProtocolErrorCode.INVALID_MESSAGE,
            "JSON frame is not a valid protocol message",
        ) from error
    if _json_depth(document) > MAX_JSON_DEPTH:
        raise ProtocolMessageError(
            ProtocolErrorCode.INVALID_MESSAGE,
            f"JSON frame exceeds {MAX_JSON_DEPTH} levels of nesting",
        )
    try:
        return _PROTOCOL_MESSAGE_ADAPTER.validate_python(document)
    except ValidationError as error:
        raise ProtocolMessageError(
            ProtocolErrorCode.INVALID_MESSAGE,
            "JSON frame is not a valid protocol message",
        ) from error


def parse_hello_frame(frame: str | bytes) -> HelloMessage:
    """Validate one bounded JSON text frame as the handshake hello."""

    message = parse_text_frame(frame)
    if not isinstance(message, HelloMessage):
        raise ProtocolMessageError(
            ProtocolErrorCode.INVALID_MESSAGE,
            "first protocol message must be hello",
        )
    return message


def negotiate_protocol_version(
    message: HelloMessage,
    *,
    authenticated_device_id: str,
    supported_versions: tuple[int, ...] = (1,),
) -> int:
    """Verify handshake identity and select the current protocol version."""

    if message.payload.device_id != authenticated_device_id:
        raise ProtocolMessageError(
            ProtocolErrorCode.UNKNOWN_DEVICE,
            "hello device_id does not match the authenticated device",
        )
    mutual_versions = set(message.payload.protocol_versions).intersection(supported_versions)
    if not mutual_versions:
        raise ProtocolMessageError(
            ProtocolErrorCode.UNSUPPORTED_VERSION,
            "device and Bridge do not share a protocol version",
        )
    return max(mutual_versions)


def _reject_json_constant(value: str) -> Never:
    raise ValueError(f"non-standard JSON constant is not allowed: {value}")


def _json_depth(value: object) -> int:
    if isinstance(value, dict):
        return 1 + max((_json_depth(item) for item in value.values()), default=0)
    if isinstance(value, list):
        return 1 + max((_json_depth(item) for item in value), default=0)
    return 0
