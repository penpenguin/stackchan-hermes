"""Decode authenticated device Opus input and launch owned voice turns."""

from __future__ import annotations

from asyncio import Task, create_task, current_task, sleep
from collections import OrderedDict
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass, field
from uuid import UUID

from stackchan_bridge.audio.codec import AudioCodecError, OpusCodec, OpusCodecConfig
from stackchan_bridge.audio.debug_store import DebugAudioStore
from stackchan_bridge.audio.types import PcmAudio
from stackchan_bridge.audio.vad import RmsVad, RmsVadConfig, VadUtterance
from stackchan_bridge.observability.metrics import BridgeMetrics
from stackchan_bridge.protocol.models import (
    AudioInputEndMessage,
    AudioInputStartMessage,
    ProtocolErrorCode,
)
from stackchan_bridge.turns.coordinator import Turn, TurnCoordinator, TurnTrigger
from stackchan_bridge.turns.service import VoiceTurnService

_RECORDING_DEADLINE_GRACE_SECONDS = 1.0


@dataclass(slots=True)
class _InputCapture:
    turn: Turn
    start: AudioInputStartMessage
    codec: OpusCodec
    vad: RmsVad | None
    pcm: bytearray = field(default_factory=bytearray)
    completed: bool = False
    deadline_task: Task[None] | None = field(default=None, repr=False)


class VoiceAudioInputHandler:
    """Gateway handler with bounded per-device decode and background turn processing."""

    def __init__(
        self,
        coordinator: TurnCoordinator,
        service: VoiceTurnService,
        *,
        max_recording_ms: int,
        max_decode_errors: int = 3,
        vad_config: RmsVadConfig | None = None,
        metrics: BridgeMetrics | None = None,
        debug_audio_store: DebugAudioStore | None = None,
    ) -> None:
        if not 0 < max_recording_ms <= 15_000:
            raise ValueError("maximum recording duration must be between 1 and 15000 ms")
        if max_decode_errors <= 0:
            raise ValueError("decode error limit must be positive")
        self._coordinator = coordinator
        self._service = service
        self._max_recording_seconds = max_recording_ms / 1_000
        self._max_recording_bytes = 16_000 * 2 * max_recording_ms // 1_000
        self._max_decode_errors = max_decode_errors
        self._vad_config = vad_config
        self._metrics = metrics or BridgeMetrics()
        self._debug_audio_store = debug_audio_store
        self._captures: dict[str, _InputCapture] = {}
        self._turn_tasks: OrderedDict[UUID, Task[Turn]] = OrderedDict()
        self._stream_timeout_handler: Callable[[str, AudioInputStartMessage], None] | None = None

    def set_stream_timeout_handler(
        self,
        handler: Callable[[str, AudioInputStartMessage], None],
    ) -> None:
        self._stream_timeout_handler = handler

    async def start(self, device_id: str, message: AudioInputStartMessage) -> None:
        if device_id in self._captures:
            raise RuntimeError("device already has an active microphone stream")
        await self._coordinator.cancel_device(device_id, reason="NEW_INPUT")
        turn = await self._coordinator.begin(
            device_id,
            trigger=TurnTrigger(message.payload.trigger),
            turn_id=message.turn_id,
        )
        turn.input_stream_id = message.stream_id
        capture = _InputCapture(
            turn=turn,
            start=message,
            codec=OpusCodec(
                OpusCodecConfig(
                    sample_rate=message.payload.sample_rate,
                    channels=message.payload.channels,
                    frame_ms=message.payload.frame_ms,
                )
            ),
            vad=RmsVad(self._vad_config) if self._vad_config is not None else None,
        )
        self._captures[device_id] = capture
        capture.deadline_task = create_task(
            self._enforce_recording_deadline(device_id, message.stream_id)
        )
        capture.deadline_task.add_done_callback(_retrieve_deadline_failure)

    async def frame(
        self,
        device_id: str,
        stream: AudioInputStartMessage,
        packet: bytes,
    ) -> ProtocolErrorCode | None:
        capture = self._owned_capture(device_id, stream.stream_id)
        if capture.completed:
            return None
        try:
            decoded = capture.codec.decode(packet)
        except AudioCodecError:
            self._metrics.audio_decode_error_total.inc()
            if capture.codec.consecutive_decode_errors >= self._max_decode_errors:
                await self._coordinator.cancel_device(device_id, reason="AUDIO_DECODE_ERROR")
                self._remove_capture(device_id)
                return ProtocolErrorCode.AUDIO_DECODE_ERROR
            return None
        if len(capture.pcm) + len(decoded) > self._max_recording_bytes:
            await self._coordinator.cancel_device(device_id, reason="MAX_RECORDING_EXCEEDED")
            self._remove_capture(device_id)
            raise RuntimeError("microphone stream exceeded the recording limit")
        capture.pcm.extend(decoded)
        if capture.vad is not None:
            frame_bytes = capture.vad.config.frame_bytes
            if len(decoded) % frame_bytes:
                raise RuntimeError("decoded audio does not align to VAD frames")
            for position in range(0, len(decoded), frame_bytes):
                utterance = capture.vad.process(decoded[position : position + frame_bytes])
                if utterance is not None:
                    await self._complete_vad_utterance(capture, utterance)
                    break
        return None

    async def end(self, device_id: str, message: AudioInputEndMessage) -> None:
        capture = self._owned_capture(device_id, message.stream_id)
        self._remove_capture(device_id)
        if message.payload.reason in {"user_cancel", "device_error", "disconnect"}:
            await self._coordinator.cancel_device(device_id, reason=message.payload.reason)
            return
        if capture.completed:
            return
        if capture.vad is not None:
            utterance = capture.vad.finish()
            if utterance is None:
                capture.completed = True
                await self._coordinator.fail(capture.turn.turn_id, reason="NO_SPEECH")
                return
            await self._complete_vad_utterance(capture, utterance)
            return
        if not capture.pcm:
            await self._coordinator.fail(capture.turn.turn_id, reason="EMPTY_AUDIO")
            return
        self._start_turn_task(capture, bytes(capture.pcm))

    async def _complete_vad_utterance(
        self,
        capture: _InputCapture,
        utterance: VadUtterance,
    ) -> None:
        capture.completed = True
        if not utterance.accepted:
            await self._coordinator.fail(capture.turn.turn_id, reason="SPEECH_TOO_SHORT")
            return
        self._start_turn_task(capture, utterance.pcm)

    def _start_turn_task(self, capture: _InputCapture, pcm: bytes) -> None:
        audio = PcmAudio(pcm=pcm)
        if self._debug_audio_store is not None:
            with suppress(OSError):
                self._debug_audio_store.save(capture.turn.turn_id, audio)
        task = create_task(
            self._service.run_existing_turn(
                capture.turn,
                audio=audio,
            )
        )
        task.add_done_callback(_retrieve_background_failure)
        self._turn_tasks[capture.turn.turn_id] = task
        while len(self._turn_tasks) > 128:
            _, expired = self._turn_tasks.popitem(last=False)
            if not expired.done():
                expired.cancel()
            else:
                expired.exception()

    async def disconnect(self, device_id: str, stream: AudioInputStartMessage) -> None:
        capture = self._captures.get(device_id)
        if capture is not None and capture.start.stream_id == stream.stream_id:
            self._remove_capture(device_id)
            await self._coordinator.cancel_device(device_id, reason="disconnect")

    async def wait_for_turn(self, turn_id: UUID) -> Turn:
        task = self._turn_tasks.pop(turn_id)
        return await task

    def _owned_capture(self, device_id: str, stream_id: UUID) -> _InputCapture:
        capture = self._captures.get(device_id)
        if capture is None or capture.start.stream_id != stream_id:
            raise RuntimeError("audio input stream is not owned by this device")
        return capture

    async def _enforce_recording_deadline(self, device_id: str, stream_id: UUID) -> None:
        await sleep(self._max_recording_seconds + _RECORDING_DEADLINE_GRACE_SECONDS)
        capture = self._captures.get(device_id)
        if capture is None or capture.start.stream_id != stream_id:
            return
        self._remove_capture(device_id)
        if self._stream_timeout_handler is not None:
            self._stream_timeout_handler(device_id, capture.start)
        if not capture.completed:
            await self._coordinator.cancel_turn(
                device_id,
                capture.turn.turn_id,
                reason="MAX_RECORDING_EXCEEDED",
            )

    def _remove_capture(self, device_id: str) -> _InputCapture | None:
        capture = self._captures.pop(device_id, None)
        if capture is not None:
            self._cancel_deadline(capture)
        return capture

    @staticmethod
    def _cancel_deadline(capture: _InputCapture) -> None:
        task = capture.deadline_task
        if task is not None and task is not current_task() and not task.done():
            task.cancel()


def _retrieve_background_failure(task: Task[Turn]) -> None:
    if not task.cancelled():
        task.exception()


def _retrieve_deadline_failure(task: Task[None]) -> None:
    if not task.cancelled():
        task.exception()
