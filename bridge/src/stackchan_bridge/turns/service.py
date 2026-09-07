"""End-to-end voice turn orchestration over typed adapter boundaries."""

from __future__ import annotations

from asyncio import CancelledError, current_task
from collections.abc import AsyncIterator
from contextlib import suppress
from time import monotonic
from typing import Protocol
from uuid import UUID

from stackchan_bridge.audio.types import PcmAudio
from stackchan_bridge.hermes.client import HermesEvent
from stackchan_bridge.hermes.errors import HermesError
from stackchan_bridge.hermes.segmenter import SpeechSegmenter, SpeechSegmenterConfig
from stackchan_bridge.observability.metrics import BridgeMetrics
from stackchan_bridge.stt.adapters import SttAdapter, transcribe_with_timeout
from stackchan_bridge.stt.errors import SttError, SttTimeoutError
from stackchan_bridge.tts.errors import TtsError, TtsTimeoutError
from stackchan_bridge.tts.pipeline import SegmentPlaybackPipeline
from stackchan_bridge.turns.coordinator import (
    StaleTurnError,
    Turn,
    TurnCoordinator,
    TurnState,
    TurnTrigger,
)


class HermesTextStream(Protocol):
    def stream_text_response(
        self,
        *,
        device_id: str,
        transcript: str,
    ) -> AsyncIterator[HermesEvent]: ...


class TurnFailureNotifier(Protocol):
    async def notify_failure(self, device_id: str, *, error_code: str) -> None: ...


class TurnProgressNotifier(Protocol):
    async def notify_tool_started(
        self,
        device_id: str,
        *,
        turn_id: UUID,
        tool_name: str,
    ) -> None: ...

    async def notify_tool_completed(
        self,
        device_id: str,
        *,
        turn_id: UUID,
        tool_name: str,
    ) -> None: ...


class NullTurnFailureNotifier:
    async def notify_failure(self, device_id: str, *, error_code: str) -> None:
        return None


class NullTurnProgressNotifier:
    async def notify_tool_started(
        self,
        device_id: str,
        *,
        turn_id: UUID,
        tool_name: str,
    ) -> None:
        return None

    async def notify_tool_completed(
        self,
        device_id: str,
        *,
        turn_id: UUID,
        tool_name: str,
    ) -> None:
        return None


async def notify_tool_progress_event(
    notifier: TurnProgressNotifier,
    event: HermesEvent,
    *,
    device_id: str,
    turn_id: UUID,
) -> None:
    """Map Hermes tool lifecycle events to best-effort device presentation."""

    if event.type not in {"response.output_item.added", "response.output_item.done"}:
        return
    item = event.item
    if item is None or item.get("type") != "function_call":
        return
    tool_name = item.get("name")
    if not isinstance(tool_name, str) or not 1 <= len(tool_name) <= 128:
        return
    callback = (
        notifier.notify_tool_started
        if event.type == "response.output_item.added"
        else notifier.notify_tool_completed
    )
    with suppress(Exception):
        await callback(device_id, turn_id=turn_id, tool_name=tool_name)


class VoiceTurnError(RuntimeError):
    """A voice turn ended before device playback completed."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class VoiceTurnService:
    """Move one owned turn through STT, public Hermes SSE, and ordered TTS."""

    def __init__(
        self,
        *,
        coordinator: TurnCoordinator,
        stt: SttAdapter,
        hermes: HermesTextStream,
        tts_pipeline: SegmentPlaybackPipeline,
        segmenter_config: SpeechSegmenterConfig,
        stt_timeout_seconds: float,
        metrics: BridgeMetrics | None = None,
        failure_notifier: TurnFailureNotifier | None = None,
        progress_notifier: TurnProgressNotifier | None = None,
    ) -> None:
        self._coordinator = coordinator
        self._stt = stt
        self._hermes = hermes
        self._tts_pipeline = tts_pipeline
        self._segmenter_config = segmenter_config
        self._stt_timeout_seconds = stt_timeout_seconds
        self._metrics = metrics or BridgeMetrics()
        self._failure_notifier = failure_notifier or NullTurnFailureNotifier()
        self._progress_notifier = progress_notifier or NullTurnProgressNotifier()

    @property
    def failure_notifier(self) -> TurnFailureNotifier:
        return self._failure_notifier

    @property
    def progress_notifier(self) -> TurnProgressNotifier:
        return self._progress_notifier

    async def run_audio_turn(
        self,
        device_id: str,
        *,
        turn_id: UUID,
        trigger: TurnTrigger,
        audio: PcmAudio,
    ) -> Turn:
        turn = await self._coordinator.begin(
            device_id,
            trigger=trigger,
            turn_id=turn_id,
        )
        return await self.run_existing_turn(turn, audio=audio)

    async def run_existing_turn(self, turn: Turn, *, audio: PcmAudio) -> Turn:
        """Continue a CAPTURING turn already opened by the device input handler."""

        device_id = turn.device_id
        self._require_owned(turn)
        task = current_task()
        if task is not None:
            self._coordinator.attach_task(turn.turn_id, task)
        try:
            await self._coordinator.transition(turn.turn_id, TurnState.TRANSCRIBING)
            stt_started = monotonic()
            stt_result = await transcribe_with_timeout(
                self._stt,
                audio,
                timeout_seconds=self._stt_timeout_seconds,
            )
            self._metrics.stt_duration_seconds.observe(monotonic() - stt_started)
            self._require_owned(turn)
            if stt_result.is_empty:
                raise VoiceTurnError("EMPTY_TRANSCRIPT", "speech was not recognized")
            turn.transcript = stt_result.text

            await self._coordinator.transition(turn.turn_id, TurnState.WAITING_HERMES)
            segmenter = SpeechSegmenter(self._segmenter_config)
            hermes_started = monotonic()
            first_delta_at: float | None = None
            playback_started = False

            async def speech_segments() -> AsyncIterator[str]:
                nonlocal first_delta_at, playback_started
                try:
                    async for event in self._hermes.stream_text_response(
                        device_id=device_id,
                        transcript=stt_result.text,
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
                                    await self._coordinator.transition(
                                        turn.turn_id, TurnState.SYNTHESIZING
                                    )
                                    await self._coordinator.transition(
                                        turn.turn_id, TurnState.PLAYING
                                    )
                                    playback_started = True
                                yield segment
                    for segment in segmenter.finish():
                        if not playback_started:
                            await self._coordinator.transition(turn.turn_id, TurnState.SYNTHESIZING)
                            await self._coordinator.transition(turn.turn_id, TurnState.PLAYING)
                            playback_started = True
                        yield segment
                    if not playback_started:
                        raise VoiceTurnError("EMPTY_RESPONSE", "Hermes returned no speech text")
                finally:
                    self._metrics.hermes_total_duration_seconds.observe(
                        monotonic() - hermes_started
                    )

            output_stream_ids = await self._tts_pipeline.run_streaming(
                device_id,
                turn_id=turn.turn_id,
                segments=speech_segments(),
                turn_started_at=turn.started_at,
            )
            self._require_owned(turn)
            turn.output_stream_ids.extend(output_stream_ids)
            return await self._coordinator.complete(turn.turn_id)
        except CancelledError:
            raise
        except Exception as error:
            with suppress(Exception):
                await self._failure_notifier.notify_failure(
                    device_id,
                    error_code=_turn_error_code(error),
                )
            current = self._coordinator.current(device_id)
            if current is turn:
                await self._coordinator.fail(turn.turn_id, reason="VOICE_TURN_ERROR")
            raise

    def _require_owned(self, turn: Turn) -> None:
        if self._coordinator.current(turn.device_id) is not turn or turn.cancellation.is_set():
            raise StaleTurnError(f"turn is no longer active: {turn.turn_id}")


def _turn_error_code(error: Exception) -> str:
    if isinstance(error, VoiceTurnError):
        return error.code
    if isinstance(error, SttTimeoutError):
        return "STT_TIMEOUT"
    if isinstance(error, SttError):
        return "STT_FAILED"
    if isinstance(error, HermesError):
        return "HERMES_FAILED"
    if isinstance(error, TtsTimeoutError):
        return "TTS_TIMEOUT"
    if isinstance(error, TtsError):
        return "TTS_FAILED"
    return "TURN_FAILED"
