"""Protocol-faithful StackChan Device Simulator."""

from __future__ import annotations

from asyncio import sleep as async_sleep
from asyncio import timeout, wait_for
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from hashlib import sha256
from pathlib import Path
from time import monotonic, time_ns
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID, uuid4

import httpx
import soundfile  # type: ignore[import-untyped]
from stackchan_bridge.audio.codec import OpusCodec, OpusCodecConfig
from stackchan_bridge.audio.normalize import normalize_audio
from stackchan_bridge.audio.types import PcmAudio
from stackchan_bridge.audio.wav import pcm_to_wav
from stackchan_bridge.protocol.models import (
    MAX_JSON_BYTES,
    AudioInputEndMessage,
    AudioInputStartMessage,
    AudioOutputEndMessage,
    AudioOutputStartMessage,
    CameraCompletedAckMessage,
    CaptureCommand,
    CommandMessage,
    CommandResultMessage,
    EventMessage,
    HelloAckMessage,
    HelloMessage,
    ProtocolErrorCode,
    ProtocolMessageError,
    SetHeadAnglesCommand,
    parse_text_frame,
)
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

from stackchan_simulator.fixtures import generate_synthetic_jpeg
from stackchan_simulator.reconnect import ReconnectBackoff

_OUTPUT_SEGMENT_GRACE_SECONDS = 30.0
_MAX_INPUT_SAMPLE_VALUES = 15 * 192_000 * 2
_MAX_OUTPUT_PCM_BYTES = 120 * 16_000 * 2


class SimulatorFault(StrEnum):
    """Bounded transport failures selectable from the Simulator CLI."""

    MALFORMED_JSON = "malformed-json"
    MALFORMED_OPUS = "malformed-opus"
    DUPLICATE_MESSAGE = "duplicate-message"
    DISCONNECT = "disconnect"


@dataclass(frozen=True, slots=True)
class SimulatorConfig:
    """Connection identity and advertised Simulator properties."""

    bridge_url: str
    device_id: str
    token: str = field(repr=False)
    device_name: str = "StackChan Simulator"
    firmware_version: str = "0.1.0"
    hardware_model: str = "SIMULATOR"
    led_count: int = 12
    frame_ms: int = 60
    input_wav: Path | None = None
    output_wav: Path | None = None
    protocol_versions: tuple[int, ...] = (1,)
    command_delay_seconds: float = 0
    output_segment_grace_seconds: float = _OUTPUT_SEGMENT_GRACE_SECONDS
    fault: SimulatorFault | None = None

    def __post_init__(self) -> None:
        if (
            not self.protocol_versions
            or len(self.protocol_versions) > 8
            or len(set(self.protocol_versions)) != len(self.protocol_versions)
            or any(version <= 0 for version in self.protocol_versions)
        ):
            raise ValueError("simulator protocol versions must be 1 to 8 unique positive values")
        if not 0 <= self.command_delay_seconds <= 30:
            raise ValueError("simulator command delay must be between 0 and 30 seconds")
        if not 0 < self.output_segment_grace_seconds <= 300:
            raise ValueError("output segment grace must be between 0 and 300 seconds")


@dataclass(frozen=True, slots=True)
class SimulatorVoiceResult:
    turn_id: UUID
    input_packets: int
    output_packets: int
    output_streams: int


class DeviceSimulator:
    """A deterministic device peer used by host integration tests."""

    def __init__(self, config: SimulatorConfig) -> None:
        self._config = config
        self._head_angles: tuple[int | float, int | float] = (0, 0)

    @property
    def head_angles(self) -> tuple[int | float, int | float]:
        """Current simulated yaw and pitch."""

        return self._head_angles

    def hello_message(self) -> HelloMessage:
        """Build the authenticated device's v1 hello message."""

        return HelloMessage.model_validate(
            {
                "v": 1,
                "type": "hello",
                "message_id": str(uuid4()),
                "sent_at_ms": time_ns() // 1_000_000,
                "payload": {
                    "device_id": self._config.device_id,
                    "device_name": self._config.device_name,
                    "capture_protocol_version": 2,
                    "firmware_version": self._config.firmware_version,
                    "hardware_model": self._config.hardware_model,
                    "protocol_versions": list(self._config.protocol_versions),
                    "capabilities": {
                        "microphone": True,
                        "speaker": True,
                        "camera": True,
                        "touch": True,
                        "head": True,
                        "display": True,
                        "avatar": True,
                        "led_count": self._config.led_count,
                    },
                    "audio": {
                        "codec": "opus",
                        "sample_rate": 16_000,
                        "channels": 1,
                        "frame_ms": self._config.frame_ms,
                    },
                },
            }
        )

    async def handshake(self) -> HelloAckMessage:
        """Connect, exchange hello/ack, and close the test connection."""

        headers = {
            "Authorization": f"Bearer {self._config.token}",
            "X-StackChan-Device-Id": self._config.device_id,
        }
        async with connect(
            self._config.bridge_url,
            additional_headers=headers,
            max_size=MAX_JSON_BYTES,
        ) as websocket:
            await websocket.send(self.hello_message().model_dump_json())
            response = parse_text_frame(await websocket.recv())
        if not isinstance(response, HelloAckMessage):
            raise ProtocolMessageError(
                ProtocolErrorCode.INVALID_MESSAGE,
                "Bridge did not return hello_ack",
            )
        return response

    async def handshake_with_reconnect(
        self,
        *,
        max_attempts: int,
        sleep: Callable[[float], Awaitable[None]] = async_sleep,
    ) -> HelloAckMessage:
        """Retry transient transport failures using the bounded Protocol v1 schedule."""

        if not 1 <= max_attempts <= 100:
            raise ValueError("reconnect attempts must be between 1 and 100")
        backoff = ReconnectBackoff()
        for attempt in range(max_attempts):
            try:
                return await self.handshake()
            except (OSError, ConnectionClosed):
                if attempt + 1 == max_attempts:
                    raise
                await sleep(backoff.next_delay_seconds())
        raise AssertionError("bounded reconnect loop did not return or raise")

    async def run_one_command(self) -> CommandMessage:
        """Handshake, apply one command, return its result, and disconnect."""

        headers = {
            "Authorization": f"Bearer {self._config.token}",
            "X-StackChan-Device-Id": self._config.device_id,
        }
        async with connect(
            self._config.bridge_url,
            additional_headers=headers,
            max_size=MAX_JSON_BYTES,
        ) as websocket:
            await websocket.send(self.hello_message().model_dump_json())
            acknowledgement = parse_text_frame(await websocket.recv())
            if not isinstance(acknowledgement, HelloAckMessage):
                raise ProtocolMessageError(
                    ProtocolErrorCode.INVALID_MESSAGE,
                    "Bridge did not return hello_ack",
                )
            message = parse_text_frame(await websocket.recv())
            if not isinstance(message, CommandMessage):
                raise ProtocolMessageError(
                    ProtocolErrorCode.INVALID_MESSAGE,
                    "Bridge did not send a command",
                )
            if self._config.command_delay_seconds:
                await async_sleep(self._config.command_delay_seconds)
            result = self._apply_command(message)
            await websocket.send(result.model_dump_json())
        return message

    def event_message(self, name: str, data: dict[str, object]) -> EventMessage:
        """Build one typed device event for deterministic Simulator scenarios."""

        return EventMessage.model_validate(
            {
                "v": 1,
                "type": "event",
                "message_id": str(uuid4()),
                "device_id": self._config.device_id,
                "sent_at_ms": time_ns() // 1_000_000,
                "payload": {"name": name, "data": data},
            }
        )

    async def send_events(self, events: tuple[EventMessage, ...]) -> None:
        """Handshake and send a finite event sequence before a clean disconnect."""

        if not events or len(events) > 128:
            raise ValueError("simulator event sequence must contain 1 to 128 events")
        if any(event.device_id != self._config.device_id for event in events):
            raise ValueError("simulator event belongs to a different device")
        headers = {
            "Authorization": f"Bearer {self._config.token}",
            "X-StackChan-Device-Id": self._config.device_id,
        }
        async with connect(
            self._config.bridge_url,
            additional_headers=headers,
            max_size=MAX_JSON_BYTES,
        ) as websocket:
            await websocket.send(self.hello_message().model_dump_json())
            acknowledgement = parse_text_frame(await websocket.recv())
            if not isinstance(acknowledgement, HelloAckMessage):
                raise ProtocolMessageError(
                    ProtocolErrorCode.INVALID_MESSAGE,
                    "Bridge did not return hello_ack",
                )
            for event in events:
                await websocket.send(event.model_dump_json())

    def fault_frames(self, fault: SimulatorFault) -> tuple[str | bytes, ...]:
        """Build a finite malformed/duplicate sequence without opening a connection."""

        if fault is SimulatorFault.MALFORMED_JSON:
            return ("{",)
        if fault is SimulatorFault.MALFORMED_OPUS:
            turn_id = uuid4()
            stream_id = uuid4()
            start = AudioInputStartMessage.model_validate(
                {
                    "v": 1,
                    "type": "audio.input.start",
                    "message_id": str(uuid4()),
                    "turn_id": str(turn_id),
                    "stream_id": str(stream_id),
                    "sent_at_ms": time_ns() // 1_000_000,
                    "payload": {
                        "codec": "opus",
                        "sample_rate": 16_000,
                        "channels": 1,
                        "frame_ms": self._config.frame_ms,
                        "trigger": "simulator",
                    },
                }
            )
            return (start.model_dump_json(), b"malformed-opus")
        if fault is SimulatorFault.DUPLICATE_MESSAGE:
            event = self.event_message("touch.tap", {"x": 100, "y": 120}).model_dump_json()
            return (event, event)
        if fault is SimulatorFault.DISCONNECT:
            return ()
        raise ValueError("unknown Simulator fault")

    async def run_fault(self, fault: SimulatorFault) -> None:
        """Handshake, inject one bounded fault sequence, then disconnect."""

        frames = self.fault_frames(fault)
        headers = {
            "Authorization": f"Bearer {self._config.token}",
            "X-StackChan-Device-Id": self._config.device_id,
        }
        async with connect(
            self._config.bridge_url,
            additional_headers=headers,
            max_size=MAX_JSON_BYTES,
        ) as websocket:
            await websocket.send(self.hello_message().model_dump_json())
            acknowledgement = parse_text_frame(await websocket.recv())
            if not isinstance(acknowledgement, HelloAckMessage):
                raise ProtocolMessageError(
                    ProtocolErrorCode.INVALID_MESSAGE,
                    "Bridge did not return hello_ack",
                )
            for frame in frames:
                await websocket.send(frame)

    async def run_voice_turn(self) -> SimulatorVoiceResult:
        """Send one WAV microphone turn and record one Bridge playback stream."""

        input_path = self._config.input_wav
        output_path = self._config.output_wav
        if input_path is None or output_path is None:
            raise ValueError("voice simulation requires input_wav and output_wav")
        if not input_path.is_file() or not output_path.parent.is_dir():
            raise ValueError("simulator WAV paths are unavailable")
        try:
            info = soundfile.info(input_path)
            if (
                info.samplerate <= 0
                or info.frames <= 0
                or info.frames > 15 * info.samplerate
                or round(info.frames * 16_000 / info.samplerate) > 15 * 16_000
            ):
                raise ValueError("simulator input WAV duration is outside the limit")
            if info.channels <= 0 or info.frames * info.channels > _MAX_INPUT_SAMPLE_VALUES:
                raise ValueError("simulator input WAV exceeds the decoded sample limit")
            samples, sample_rate = soundfile.read(
                input_path,
                dtype="float64",
                always_2d=True,
                frames=info.frames,
            )
        except (OSError, RuntimeError) as error:
            raise ValueError("simulator input WAV is invalid") from error
        audio = normalize_audio(samples, sample_rate=sample_rate, gain=1)
        if not audio.pcm or audio.duration_seconds > 15:
            raise ValueError("simulator input WAV duration is outside the limit")

        turn_id = uuid4()
        input_stream_id = uuid4()
        codec_config = OpusCodecConfig(frame_ms=self._config.frame_ms)
        input_start = AudioInputStartMessage.model_validate(
            {
                "v": 1,
                "type": "audio.input.start",
                "message_id": str(uuid4()),
                "turn_id": str(turn_id),
                "stream_id": str(input_stream_id),
                "sent_at_ms": time_ns() // 1_000_000,
                "payload": {
                    "codec": "opus",
                    "sample_rate": 16_000,
                    "channels": 1,
                    "frame_ms": self._config.frame_ms,
                    "trigger": "simulator",
                },
            }
        )
        input_end = AudioInputEndMessage.model_validate(
            {
                "v": 1,
                "type": "audio.input.end",
                "message_id": str(uuid4()),
                "turn_id": str(turn_id),
                "stream_id": str(input_stream_id),
                "sent_at_ms": time_ns() // 1_000_000,
                "payload": {"reason": "silence"},
            }
        )
        headers = {
            "Authorization": f"Bearer {self._config.token}",
            "X-StackChan-Device-Id": self._config.device_id,
        }
        input_packets = 0
        output_packets = 0
        output_streams = 0
        output_pcm = bytearray()
        async with connect(
            self._config.bridge_url,
            additional_headers=headers,
            max_size=MAX_JSON_BYTES,
        ) as websocket:
            await websocket.send(self.hello_message().model_dump_json())
            acknowledgement = parse_text_frame(await websocket.recv())
            if not isinstance(acknowledgement, HelloAckMessage):
                raise ProtocolMessageError(
                    ProtocolErrorCode.INVALID_MESSAGE,
                    "Bridge did not return hello_ack",
                )
            await websocket.send(input_start.model_dump_json())
            input_codec = OpusCodec(codec_config)
            for position in range(0, len(audio.pcm), codec_config.pcm_bytes):
                if position:
                    await async_sleep(codec_config.frame_ms / 1_000)
                frame = audio.pcm[position : position + codec_config.pcm_bytes]
                await websocket.send(
                    input_codec.encode(frame.ljust(codec_config.pcm_bytes, b"\x00"))
                )
                input_packets += 1
            await websocket.send(input_end.model_dump_json())

            output_start: AudioOutputStartMessage | None = None
            output_codec: OpusCodec | None = None
            output_deadline = monotonic() + self._config.output_segment_grace_seconds
            while True:
                try:
                    remaining = output_deadline - monotonic()
                    if remaining <= 0:
                        raise TimeoutError
                    incoming = await wait_for(websocket.recv(), timeout=remaining)
                except TimeoutError as error:
                    if output_streams and output_start is None:
                        break
                    raise ProtocolMessageError(
                        ProtocolErrorCode.INVALID_STATE,
                        "Bridge output stream timed out before audio.output.end",
                    ) from error
                if isinstance(incoming, bytes):
                    if output_start is None or output_codec is None:
                        raise ProtocolMessageError(
                            ProtocolErrorCode.INVALID_STATE,
                            "Bridge sent audio before audio.output.start",
                        )
                    decoded = output_codec.decode(incoming)
                    if len(output_pcm) + len(decoded) > _MAX_OUTPUT_PCM_BYTES:
                        raise ProtocolMessageError(
                            ProtocolErrorCode.INVALID_STATE,
                            "Bridge output PCM exceeds the duration limit",
                        )
                    output_pcm.extend(decoded)
                    output_packets += 1
                    continue
                message = parse_text_frame(incoming)
                if isinstance(message, AudioOutputStartMessage):
                    if output_start is not None or message.turn_id != turn_id:
                        raise ProtocolMessageError(
                            ProtocolErrorCode.INVALID_STATE,
                            "Bridge output stream ownership is invalid",
                        )
                    output_start = message
                    output_deadline = (
                        monotonic()
                        + message.payload.expected_duration_ms / 1_000
                        + self._config.output_segment_grace_seconds
                    )
                    output_codec = OpusCodec(
                        OpusCodecConfig(
                            sample_rate=message.payload.sample_rate,
                            channels=message.payload.channels,
                            frame_ms=message.payload.frame_ms,
                        )
                    )
                    continue
                if isinstance(message, AudioOutputEndMessage):
                    if (
                        output_start is None
                        or message.turn_id != turn_id
                        or message.stream_id != output_start.stream_id
                    ):
                        raise ProtocolMessageError(
                            ProtocolErrorCode.INVALID_STATE,
                            "Bridge output end ownership is invalid",
                        )
                    if message.payload.reason != "completed":
                        raise ProtocolMessageError(
                            ProtocolErrorCode.INVALID_STATE,
                            f"Bridge output stream ended with {message.payload.reason}",
                        )
                    output_streams += 1
                    output_start = None
                    output_codec = None
                    output_deadline = monotonic() + self._config.output_segment_grace_seconds
                    continue
                raise ProtocolMessageError(
                    ProtocolErrorCode.INVALID_MESSAGE,
                    "Bridge sent an unexpected voice-turn message",
                )
        if not output_pcm:
            raise ProtocolMessageError(
                ProtocolErrorCode.INVALID_MESSAGE,
                "Bridge returned no playback audio",
            )
        output_path.write_bytes(pcm_to_wav(PcmAudio(pcm=bytes(output_pcm))))
        return SimulatorVoiceResult(
            turn_id=turn_id,
            input_packets=input_packets,
            output_packets=output_packets,
            output_streams=output_streams,
        )

    async def run_capture_command(self) -> CommandMessage:
        """Upload one synthetic JPEG for a Bridge-owned camera command."""

        headers = {
            "Authorization": f"Bearer {self._config.token}",
            "X-StackChan-Device-Id": self._config.device_id,
        }
        async with connect(
            self._config.bridge_url,
            additional_headers=headers,
            max_size=MAX_JSON_BYTES,
        ) as websocket:
            await websocket.send(self.hello_message().model_dump_json())
            acknowledgement = parse_text_frame(await websocket.recv())
            if not isinstance(acknowledgement, HelloAckMessage):
                raise ProtocolMessageError(
                    ProtocolErrorCode.INVALID_MESSAGE,
                    "Bridge did not return hello_ack",
                )
            command = parse_text_frame(await websocket.recv())
            if not isinstance(command, CommandMessage) or not isinstance(
                command.payload, CaptureCommand
            ):
                raise ProtocolMessageError(
                    ProtocolErrorCode.INVALID_MESSAGE,
                    "Bridge did not send camera.capture",
                )
            capture_id = command.payload.args.capture_id
            upload_url = self._capture_upload_url(capture_id)
            result = CommandResultMessage.model_validate(
                {
                    "v": 1,
                    "type": "command_result",
                    "message_id": str(uuid4()),
                    "request_id": command.request_id,
                    "sent_at_ms": time_ns() // 1_000_000,
                    "payload": {
                        "ok": True,
                        "result": {"capture_id": str(capture_id)},
                    },
                }
            )
            await websocket.send(result.model_dump_json())
            jpeg = generate_synthetic_jpeg()
            async with timeout(command.payload.args.timeout_ms / 1000):
                async with httpx.AsyncClient(timeout=3, trust_env=False) as client:
                    query_started = monotonic()
                    receipt = await client.get(upload_url + "/status", headers=headers)
                    receipt.raise_for_status()
                    if receipt.json()["state"] != "reserved":
                        raise ValueError("capture reservation is not accepting uploads")
                    remaining = receipt.json()["remaining_ms"] / 1000 - (
                        monotonic() - query_started
                    )
                    async with timeout(max(0, remaining)):
                        response = await client.post(
                            upload_url,
                            headers=headers,
                            files={"file": ("capture.jpg", jpeg, "image/jpeg")},
                        )
                        response.raise_for_status()
                # The HTTP client and JPEG upload resources are released before completion.
                completed = self.event_message(
                    "camera.completed",
                    {
                        "capture_id": str(capture_id),
                        "ok": True,
                        "sha256": sha256(jpeg).hexdigest(),
                        "size_bytes": len(jpeg),
                    },
                )
                await websocket.send(completed.model_dump_json())
                receipt_ack = parse_text_frame(await websocket.recv())
                if (
                    not isinstance(receipt_ack, CameraCompletedAckMessage)
                    or receipt_ack.payload.capture_id != capture_id
                    or not receipt_ack.payload.accepted
                ):
                    raise ValueError("Bridge did not acknowledge camera completion")

        return command

    def _capture_upload_url(self, capture_id: UUID) -> str:
        parsed = urlsplit(self._config.bridge_url)
        if parsed.scheme not in {"ws", "wss"} or not parsed.netloc:
            raise ValueError("simulator Bridge URL must use ws or wss")
        scheme = "http" if parsed.scheme == "ws" else "https"
        return urlunsplit(
            (
                scheme,
                parsed.netloc,
                f"/v1/device/captures/{capture_id}",
                "",
                "",
            )
        )

    def _apply_command(self, command: CommandMessage) -> CommandResultMessage:
        if not isinstance(command.payload, SetHeadAnglesCommand):
            raise ProtocolMessageError(
                ProtocolErrorCode.INVALID_MESSAGE,
                "Simulator command handler is not implemented",
            )
        self._head_angles = (command.payload.args.yaw, command.payload.args.pitch)
        return CommandResultMessage.model_validate(
            {
                "v": 1,
                "type": "command_result",
                "message_id": str(uuid4()),
                "request_id": command.request_id,
                "sent_at_ms": time_ns() // 1_000_000,
                "payload": {
                    "ok": True,
                    "result": {
                        "yaw": command.payload.args.yaw,
                        "pitch": command.payload.args.pitch,
                    },
                },
            }
        )
