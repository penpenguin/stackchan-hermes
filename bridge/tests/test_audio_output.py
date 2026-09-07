from __future__ import annotations

import json
from typing import cast
from uuid import UUID

import pytest
from fastapi import WebSocket
from stackchan_bridge.audio.codec import OpusCodec, OpusCodecConfig
from stackchan_bridge.audio.output import AudioOutputStreamer
from stackchan_bridge.audio.types import PcmAudio
from stackchan_bridge.device_gateway.application import (
    DeviceConnection,
    DeviceDisconnectedError,
    DeviceRegistry,
)
from stackchan_bridge.protocol.models import AudioOutputEndMessage, AudioOutputStartMessage
from starlette.websockets import WebSocketDisconnect

from .test_control_api import simulator_hello


class RecordingOutputWebSocket:
    def __init__(self) -> None:
        self.frames: list[tuple[str, str | bytes]] = []

    async def send_text(self, data: str) -> None:
        self.frames.append(("text", data))

    async def send_bytes(self, data: bytes) -> None:
        self.frames.append(("bytes", data))


class RecordingSleeper:
    def __init__(self) -> None:
        self.delays: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.delays.append(seconds)


class ManualClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class DelayedOutputWebSocket(RecordingOutputWebSocket):
    def __init__(self, clock: ManualClock, *, send_delay: float) -> None:
        super().__init__()
        self._clock = clock
        self._send_delay = send_delay

    async def send_bytes(self, data: bytes) -> None:
        await super().send_bytes(data)
        self._clock.advance(self._send_delay)


class AdvancingSleeper(RecordingSleeper):
    def __init__(self, clock: ManualClock) -> None:
        super().__init__()
        self._clock = clock

    async def __call__(self, seconds: float) -> None:
        await super().__call__(seconds)
        self._clock.advance(seconds)


@pytest.mark.asyncio
@pytest.mark.parametrize("frame_kind", ["text", "bytes"])
@pytest.mark.parametrize("failure", ["runtime", "websocket", "ownership"])
async def test_audio_output_maps_send_failures_to_device_disconnected(
    frame_kind: str,
    failure: str,
) -> None:
    registry = DeviceRegistry(command_timeout_seconds=5)
    connection_id = UUID("79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc")

    class DisconnectingSocket(RecordingOutputWebSocket):
        def fail_send(self) -> None:
            if failure == "runtime":
                raise RuntimeError("peer disconnected during send")
            if failure == "websocket":
                raise WebSocketDisconnect()
            registry.unregister("sim-001", connection_id)

        async def send_text(self, data: str) -> None:
            await super().send_text(data)
            if frame_kind == "text":
                self.fail_send()

        async def send_bytes(self, data: bytes) -> None:
            await super().send_bytes(data)
            if frame_kind == "bytes":
                self.fail_send()

    websocket = DisconnectingSocket()
    await registry.register(
        DeviceConnection(
            connection_id=connection_id,
            device_id="sim-001",
            hello=simulator_hello(),
            websocket=cast(WebSocket, websocket),
        )
    )
    sleeper = RecordingSleeper()
    streamer = AudioOutputStreamer(registry, sleeper=sleeper)
    with pytest.raises(DeviceDisconnectedError):
        await streamer.play(
            "sim-001",
            turn_id=UUID("168b58ca-7c31-4744-b445-d2f20c9bdde0"),
            audio=PcmAudio(pcm=b"\x00\x01" * (960 * 2)),
        )
    assert [kind for kind, _ in websocket.frames] == (
        ["text"] if frame_kind == "text" else ["text", "bytes"]
    )
    assert sleeper.delays == []


@pytest.mark.asyncio
async def test_audio_output_streamer_orders_controls_and_padded_opus_packets() -> None:
    registry = DeviceRegistry(command_timeout_seconds=5)
    websocket = RecordingOutputWebSocket()
    await registry.register(
        DeviceConnection(
            connection_id=UUID("79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc"),
            device_id="sim-001",
            hello=simulator_hello(),
            websocket=cast(WebSocket, websocket),
        )
    )
    clock = ManualClock()
    sleeper = AdvancingSleeper(clock)
    streamer = AudioOutputStreamer(
        registry,
        frame_ms=60,
        playback_preroll_ms=500,
        sleeper=sleeper,
        clock=clock,
    )
    frame_count = 40
    audio = PcmAudio(pcm=b"\x00\x01" * (960 * frame_count))
    turn_id = UUID("168b58ca-7c31-4744-b445-d2f20c9bdde0")

    stream_id = await streamer.play("sim-001", turn_id=turn_id, audio=audio)

    assert [kind for kind, _ in websocket.frames] == [
        "text",
        *["bytes"] * frame_count,
        "text",
    ]
    start = AudioOutputStartMessage.model_validate(json.loads(cast(str, websocket.frames[0][1])))
    end = AudioOutputEndMessage.model_validate(json.loads(cast(str, websocket.frames[-1][1])))
    assert start.stream_id == stream_id
    assert start.turn_id == turn_id
    assert start.payload.expected_duration_ms == 2_400
    assert end.stream_id == stream_id
    assert end.payload.reason == "completed"
    assert sleeper.delays == pytest.approx([*[0.06] * (frame_count - 1), 0.56])

    decoder = OpusCodec(OpusCodecConfig(frame_ms=60))
    decoded = b"".join(
        decoder.decode(cast(bytes, frame)) for kind, frame in websocket.frames if kind == "bytes"
    )
    assert len(decoded) == frame_count * decoder.config.pcm_bytes


@pytest.mark.asyncio
async def test_audio_output_streamer_paces_against_deadline_without_send_delay_drift() -> None:
    registry = DeviceRegistry(command_timeout_seconds=5)
    clock = ManualClock()
    websocket = DelayedOutputWebSocket(clock, send_delay=0.02)
    await registry.register(
        DeviceConnection(
            connection_id=UUID("79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc"),
            device_id="sim-001",
            hello=simulator_hello(),
            websocket=cast(WebSocket, websocket),
        )
    )
    sleeper = AdvancingSleeper(clock)
    streamer = AudioOutputStreamer(
        registry,
        frame_ms=60,
        playback_preroll_ms=500,
        sleeper=sleeper,
        clock=clock,
    )
    audio = PcmAudio(pcm=b"\x00\x01" * (960 * 4))

    await streamer.play(
        "sim-001",
        turn_id=UUID("168b58ca-7c31-4744-b445-d2f20c9bdde0"),
        audio=audio,
    )

    assert sleeper.delays[:-1] == pytest.approx([0.04, 0.04, 0.04])
    assert sleeper.delays[-1] == pytest.approx(0.56)
