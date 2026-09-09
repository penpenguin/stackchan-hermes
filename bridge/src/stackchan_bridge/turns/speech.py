"""Owned background speech without STT or Hermes requests."""

from __future__ import annotations

from asyncio import Task, create_task, gather
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from time import monotonic
from uuid import UUID

from pydantic import TypeAdapter

from stackchan_bridge.audio.types import PcmAudio
from stackchan_bridge.device_gateway.application import (
    DeviceCapabilityError,
    DeviceDisconnectedError,
    DeviceNotConnectedError,
    DeviceRegistry,
)
from stackchan_bridge.observability.metrics import BridgeMetrics
from stackchan_bridge.protocol.models import DeviceId
from stackchan_bridge.speech_models import SpeechRequest, SpeechStatus
from stackchan_bridge.tts.adapters import TtsAdapter
from stackchan_bridge.tts.errors import TtsError, TtsTimeoutError
from stackchan_bridge.tts.pipeline import AudioPlayer, SegmentPlaybackPipeline
from stackchan_bridge.turns.coordinator import (
    StaleTurnError,
    Turn,
    TurnCoordinator,
    TurnState,
    TurnTrigger,
)

_BOUNDARIES = frozenset("。\uff01\uff1f!?\n")
_DEVICE_ID = TypeAdapter(DeviceId)
_CANCELLATION_FAILURES = {
    "disconnect": "DEVICE_NOT_CONNECTED",
    "connection_replaced": "DEVICE_NOT_CONNECTED",
    "AUDIO_DECODE_ERROR": "AUDIO_DECODE_ERROR",
}


class SpeechUnavailableError(RuntimeError):
    """Speech service is shutting down or unavailable."""


class SpeechNotFoundError(LookupError):
    """No retained speech result belongs to this device and turn."""


def split_speech_text(text: str, limit: int) -> list[str]:
    """Split plain text without dropping content or applying conversation truncation."""
    if limit <= 0:
        raise ValueError("segment limit must be positive")
    segments = []
    remaining = text.strip()
    while remaining:
        end = min(len(remaining), limit)
        if len(remaining) > limit:
            boundaries = [
                i + 1 for i, character in enumerate(remaining[:limit]) if character in _BOUNDARIES
            ]
            if boundaries:
                end = boundaries[-1]
        segment = remaining[:end].strip()
        if segment:
            segments.append(segment)
        remaining = remaining[end:].lstrip()
    return segments


@dataclass(slots=True)
class _SpeechJob:
    turn: Turn
    status: SpeechStatus
    connection_id: UUID
    finished_at: float | None = None


@dataclass(slots=True)
class _OwnedSpeechPlayer:
    player: AudioPlayer
    before_playback: Callable[[], Awaitable[None]]

    async def play(self, device_id: str, *, turn_id: UUID, audio: PcmAudio) -> UUID:
        await self.before_playback()
        return await self.player.play(device_id, turn_id=turn_id, audio=audio)


class SpeechTurnService:
    def __init__(
        self,
        *,
        registry: DeviceRegistry,
        coordinator: TurnCoordinator,
        adapter: TtsAdapter,
        player: AudioPlayer,
        timeout_seconds: float,
        segment_max_characters: int,
        clock: Callable[[], float] = monotonic,
        max_history: int = 128,
        history_ttl_seconds: float = 600,
        metrics: BridgeMetrics | None = None,
    ) -> None:
        if min(timeout_seconds, segment_max_characters, max_history, history_ttl_seconds) <= 0:
            raise ValueError("speech limits must be positive")
        self._registry = registry
        self._coordinator = coordinator
        self._adapter = adapter
        self._player = player
        self._timeout_seconds = timeout_seconds
        self._segment_limit = segment_max_characters
        self._clock = clock
        self._max_history = max_history
        self._history_ttl_seconds = history_ttl_seconds
        self._closed = False
        self._metrics = metrics or registry.metrics
        self._jobs: dict[UUID, _SpeechJob] = {}
        self._tasks: dict[UUID, Task[SpeechStatus]] = {}

    async def start(self, device_id: str, *, text: str) -> SpeechStatus:
        request = SpeechRequest(text=text)
        device_id = _DEVICE_ID.validate_python(device_id)
        if self._closed:
            raise SpeechUnavailableError("speech service is closed")
        connection = self._registry.get_connection(device_id)
        if connection is None:
            raise DeviceNotConnectedError("speech device is not connected")
        if not connection.hello.payload.capabilities.speaker:
            raise DeviceCapabilityError("speaker")
        turn = await self._coordinator.begin(
            device_id, trigger=TurnTrigger.CONTROL_API, initial_state=TurnState.SYNTHESIZING
        )
        accepted = SpeechStatus(turn_id=turn.turn_id, state="ACCEPTED")
        job = _SpeechJob(turn, accepted, connection.connection_id)
        try:
            if self._closed:
                raise SpeechUnavailableError("speech service is closed")
            self._require_owned(job)
        except Exception:
            await self._coordinator.fail(turn.turn_id, reason="SPEECH_UNAVAILABLE")
            raise
        self._prune()
        self._jobs[turn.turn_id] = job
        task = create_task(self._run(job, request.text))
        self._tasks[turn.turn_id] = task
        self._coordinator.attach_task(turn.turn_id, task)
        task.add_done_callback(lambda completed: self._done(job, completed))
        return accepted

    def get(self, device_id: str, turn_id: UUID) -> SpeechStatus:
        self._prune()
        job = self._jobs.get(turn_id)
        if job is None or job.turn.device_id != device_id:
            raise SpeechNotFoundError("speech result is not retained")
        return job.status

    async def _run(self, job: _SpeechJob, text: str) -> SpeechStatus:
        turn = job.turn
        job.status = SpeechStatus(turn_id=turn.turn_id, state="RUNNING")
        pipeline = SegmentPlaybackPipeline(
            self._adapter,
            _OwnedSpeechPlayer(self._player, lambda: self._before_playback(job)),
            timeout_seconds=self._timeout_seconds,
            metrics=self._metrics,
        )
        try:
            for segment in split_speech_text(text, self._segment_limit):
                self._require_owned(job)
                turn.output_stream_ids.extend(
                    await pipeline.run(
                        turn.device_id,
                        turn_id=turn.turn_id,
                        segments=[segment],
                        turn_started_at=turn.started_at if not turn.output_stream_ids else None,
                    )
                )
            self._require_owned(job)
            await self._coordinator.complete(turn.turn_id)
            return SpeechStatus(turn_id=turn.turn_id, state="COMPLETED")
        except Exception as error:
            code = _speech_error_code(error)
            if self._coordinator.current(turn.device_id) is turn and not turn.cancellation.is_set():
                await self._coordinator.fail(turn.turn_id, reason=code)
            return SpeechStatus(turn_id=turn.turn_id, state="FAILED", error_code=code)

    async def _before_playback(self, job: _SpeechJob) -> None:
        self._require_owned(job)
        if job.turn.state is TurnState.SYNTHESIZING:
            await self._coordinator.transition(job.turn.turn_id, TurnState.PLAYING)
        self._require_owned(job)

    def _require_owned(self, job: _SpeechJob) -> None:
        turn = job.turn
        if self._coordinator.current(turn.device_id) is not turn or turn.cancellation.is_set():
            raise StaleTurnError("speech turn is no longer active")
        connection = self._registry.get_connection(turn.device_id)
        if connection is None or connection.connection_id != job.connection_id:
            raise DeviceDisconnectedError("speech connection is no longer active")

    def _done(self, job: _SpeechJob, task: Task[SpeechStatus]) -> None:
        self._tasks.pop(job.turn.turn_id, None)
        # Retrieve exceptions even when a concurrent cancellation owns the result.
        error = None if task.cancelled() else task.exception()
        if task.cancelled() or job.turn.cancellation.is_set():
            code = _CANCELLATION_FAILURES.get(job.turn.failure_reason or "")
            job.status = SpeechStatus(
                turn_id=job.turn.turn_id,
                state="FAILED" if code else "CANCELLED",
                error_code=code,
            )
        elif error is not None:
            job.status = SpeechStatus(
                turn_id=job.turn.turn_id, state="FAILED", error_code="SPEECH_FAILED"
            )
        else:
            job.status = task.result()
        job.finished_at = self._clock()
        self._prune()

    def _prune(self) -> None:
        now = self._clock()
        finished = sorted(
            (job.finished_at, turn_id)
            for turn_id, job in self._jobs.items()
            if job.finished_at is not None
        )
        excess = len(finished) - self._max_history
        for index, (ended_at, turn_id) in enumerate(finished):
            if index < excess or now - ended_at >= self._history_ttl_seconds:
                del self._jobs[turn_id]

    async def aclose(self) -> None:
        self._closed = True
        tasks = tuple(self._tasks.values())
        await gather(
            *(
                self._coordinator.cancel_turn(
                    self._jobs[turn_id].turn.device_id, turn_id, reason="SHUTDOWN"
                )
                for turn_id in tuple(self._tasks)
            )
        )
        await gather(*tasks, return_exceptions=True)


def _speech_error_code(error: Exception) -> str:
    if isinstance(error, TtsTimeoutError):
        return "TTS_TIMEOUT"
    if isinstance(error, TtsError):
        return "TTS_FAILED"
    if isinstance(error, DeviceNotConnectedError | DeviceDisconnectedError):
        return "DEVICE_NOT_CONNECTED"
    return "SPEECH_FAILED"
