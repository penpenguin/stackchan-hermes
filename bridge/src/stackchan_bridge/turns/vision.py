"""Explicit camera-to-Hermes vision turn orchestration."""

from __future__ import annotations

from asyncio import CancelledError, current_task
from collections.abc import AsyncIterator
from time import monotonic
from typing import Protocol
from uuid import UUID

from stackchan_bridge.captures.store import CaptureRecord
from stackchan_bridge.hermes.client import HermesEvent
from stackchan_bridge.hermes.segmenter import SpeechSegmenter, SpeechSegmenterConfig
from stackchan_bridge.observability.metrics import BridgeMetrics
from stackchan_bridge.tts.pipeline import SegmentPlaybackPipeline
from stackchan_bridge.turns.coordinator import (
    StaleTurnError,
    Turn,
    TurnCoordinator,
    TurnState,
    TurnTrigger,
)
from stackchan_bridge.turns.service import (
    NullTurnProgressNotifier,
    TurnProgressNotifier,
    VoiceTurnError,
    notify_tool_progress_event,
)


class CaptureProvider(Protocol):
    async def take_photo(self, device_id: str, *, quality: int = 80) -> CaptureRecord: ...

    def delete_capture(self, capture_id: UUID) -> bool: ...


class HermesVisionStream(Protocol):
    def stream_vision_response(
        self,
        *,
        device_id: str,
        question: str,
        jpeg: bytes,
    ) -> AsyncIterator[HermesEvent]: ...


class VisionTurnService:
    """Capture one owned JPEG and speak a public Responses API vision answer."""

    def __init__(
        self,
        *,
        coordinator: TurnCoordinator,
        captures: CaptureProvider,
        hermes: HermesVisionStream,
        tts_pipeline: SegmentPlaybackPipeline,
        segmenter_config: SpeechSegmenterConfig,
        metrics: BridgeMetrics | None = None,
        progress_notifier: TurnProgressNotifier | None = None,
    ) -> None:
        self._coordinator = coordinator
        self._captures = captures
        self._hermes = hermes
        self._tts_pipeline = tts_pipeline
        self._segmenter_config = segmenter_config
        self._metrics = metrics or BridgeMetrics()
        self._progress_notifier = progress_notifier or NullTurnProgressNotifier()

    async def run(self, device_id: str, *, question: str, quality: int = 80) -> Turn:
        if not question.strip() or len(question) > 1_000:
            raise ValueError("vision question must contain 1 to 1000 characters")
        if not 10 <= quality <= 95:
            raise ValueError("capture quality must be between 10 and 95")
        turn = await self._coordinator.begin(device_id, trigger=TurnTrigger.CONTROL_API)
        task = current_task()
        if task is not None:
            self._coordinator.attach_task(turn.turn_id, task)
        try:
            capture = await self._captures.take_photo(device_id, quality=quality)
            try:
                self._require_owned(turn)
                turn.capture_id = capture.capture_id
                jpeg = capture.path.read_bytes()
            finally:
                self._captures.delete_capture(capture.capture_id)
            await self._coordinator.transition(turn.turn_id, TurnState.TRANSCRIBING)
            await self._coordinator.transition(turn.turn_id, TurnState.WAITING_HERMES)
            segmenter = SpeechSegmenter(self._segmenter_config)
            hermes_started = monotonic()
            first_delta_at: float | None = None
            playback_started = False

            async def speech_segments() -> AsyncIterator[str]:
                nonlocal first_delta_at, playback_started
                try:
                    async for event in self._hermes.stream_vision_response(
                        device_id=device_id,
                        question=question,
                        jpeg=jpeg,
                    ):
                        self._require_owned(turn)
                        if event.response_id is not None:
                            turn.hermes_response_id = event.response_id
                        await notify_tool_progress_event(
                            self._progress_notifier,
                            event,
                            device_id=device_id,
                            turn_id=turn.turn_id,
                        )
                        if event.type == "response.output_text.delta" and event.delta:
                            if first_delta_at is None:
                                first_delta_at = monotonic()
                                self._metrics.hermes_time_to_first_delta_seconds.observe(
                                    first_delta_at - hermes_started
                                )
                            for segment in segmenter.feed(event.delta):
                                if not playback_started:
                                    await self._start_playback(turn)
                                    playback_started = True
                                yield segment
                    for segment in segmenter.finish():
                        if not playback_started:
                            await self._start_playback(turn)
                            playback_started = True
                        yield segment
                    if not playback_started:
                        raise VoiceTurnError("EMPTY_RESPONSE", "Hermes returned no vision speech")
                finally:
                    self._metrics.hermes_total_duration_seconds.observe(
                        monotonic() - hermes_started
                    )

            stream_ids = await self._tts_pipeline.run_streaming(
                device_id,
                turn_id=turn.turn_id,
                segments=speech_segments(),
                turn_started_at=turn.started_at,
            )
            self._require_owned(turn)
            turn.output_stream_ids.extend(stream_ids)
            return await self._coordinator.complete(turn.turn_id)
        except CancelledError:
            raise
        except Exception:
            if self._coordinator.current(device_id) is turn:
                await self._coordinator.fail(turn.turn_id, reason="VISION_TURN_ERROR")
            raise

    async def _start_playback(self, turn: Turn) -> None:
        await self._coordinator.transition(turn.turn_id, TurnState.SYNTHESIZING)
        await self._coordinator.transition(turn.turn_id, TurnState.PLAYING)

    def _require_owned(self, turn: Turn) -> None:
        if self._coordinator.current(turn.device_id) is not turn or turn.cancellation.is_set():
            raise StaleTurnError(f"turn is no longer active: {turn.turn_id}")
