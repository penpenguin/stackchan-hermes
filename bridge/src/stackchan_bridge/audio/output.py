"""Ordered PCM-to-Opus playback streaming over an authenticated device socket."""

from __future__ import annotations

from asyncio import CancelledError, sleep
from collections.abc import Awaitable, Callable
from time import monotonic, time_ns
from uuid import UUID, uuid4

from starlette.websockets import WebSocketDisconnect

from stackchan_bridge.audio.codec import AudioCodecError, OpusCodec, OpusCodecConfig
from stackchan_bridge.audio.types import PcmAudio
from stackchan_bridge.device_gateway.application import (
    DeviceConnection,
    DeviceDisconnectedError,
    DeviceNotConnectedError,
    DeviceRegistry,
)
from stackchan_bridge.protocol.models import AudioOutputEndMessage, AudioOutputStartMessage


class AudioOutputStreamer:
    """Send one bounded output stream while preserving control/frame ordering."""

    def __init__(
        self,
        registry: DeviceRegistry,
        *,
        frame_ms: int = 60,
        playback_preroll_ms: int = 500,
        sleeper: Callable[[float], Awaitable[None]] = sleep,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self._registry = registry
        self._codec_config = OpusCodecConfig(frame_ms=frame_ms)
        self._playback_preroll_ms = playback_preroll_ms
        self._sleep = sleeper
        self._clock = clock

    async def play(self, device_id: str, *, turn_id: UUID, audio: PcmAudio) -> UUID:
        if not audio.pcm:
            raise ValueError("playback audio cannot be empty")
        connection = self._registry.get_connection(device_id)
        if connection is None:
            raise DeviceNotConnectedError(f"device is not connected: {device_id}")
        stream_id = uuid4()
        expected_duration_ms = round(audio.duration_seconds * 1_000)
        start = AudioOutputStartMessage.model_validate(
            {
                "v": 1,
                "type": "audio.output.start",
                "message_id": str(uuid4()),
                "turn_id": str(turn_id),
                "stream_id": str(stream_id),
                "sent_at_ms": time_ns() // 1_000_000,
                "payload": {
                    "codec": "opus",
                    "sample_rate": 16_000,
                    "channels": 1,
                    "frame_ms": self._codec_config.frame_ms,
                    "expected_duration_ms": expected_duration_ms,
                },
            }
        )
        await self._send_text(connection, start.model_dump_json())
        codec = OpusCodec(self._codec_config)
        next_frame_at = self._clock()
        try:
            for position in range(0, len(audio.pcm), self._codec_config.pcm_bytes):
                pcm_frame = audio.pcm[position : position + self._codec_config.pcm_bytes]
                padded = pcm_frame.ljust(self._codec_config.pcm_bytes, b"\x00")
                await self._send_bytes(connection, codec.encode(padded))
                self._registry.metrics.audio_output_frames_total.inc()
                if position + self._codec_config.pcm_bytes < len(audio.pcm):
                    next_frame_at += self._codec_config.frame_ms / 1_000
                    await self._sleep(max(0.0, next_frame_at - self._clock()))
        except CancelledError:
            await self._send_end(connection, turn_id, stream_id, reason="cancelled")
            raise
        except AudioCodecError:
            await self._send_end(connection, turn_id, stream_id, reason="tts_error")
            raise
        await self._send_end(connection, turn_id, stream_id, reason="completed")
        await self._sleep((self._playback_preroll_ms + self._codec_config.frame_ms) / 1_000)
        self._require_owned_connection(connection)
        return stream_id

    async def _send_end(
        self,
        connection: DeviceConnection,
        turn_id: UUID,
        stream_id: UUID,
        *,
        reason: str,
    ) -> None:
        end = AudioOutputEndMessage.model_validate(
            {
                "v": 1,
                "type": "audio.output.end",
                "message_id": str(uuid4()),
                "turn_id": str(turn_id),
                "stream_id": str(stream_id),
                "sent_at_ms": time_ns() // 1_000_000,
                "payload": {"reason": reason},
            }
        )
        await self._send_text(connection, end.model_dump_json())

    async def _send_text(self, connection: DeviceConnection, frame: str) -> None:
        self._require_owned_connection(connection)
        try:
            await connection.websocket.send_text(frame)
        except (RuntimeError, WebSocketDisconnect) as error:
            raise DeviceDisconnectedError("playback device disconnected during send") from error
        self._require_owned_connection(connection)

    async def _send_bytes(self, connection: DeviceConnection, frame: bytes) -> None:
        self._require_owned_connection(connection)
        try:
            await connection.websocket.send_bytes(frame)
        except (RuntimeError, WebSocketDisconnect) as error:
            raise DeviceDisconnectedError("playback device disconnected during send") from error
        self._require_owned_connection(connection)

    def _require_owned_connection(self, connection: DeviceConnection) -> None:
        current = self._registry.get_connection(connection.device_id)
        if current is None or current.connection_id != connection.connection_id:
            raise DeviceDisconnectedError("playback connection was replaced or disconnected")
