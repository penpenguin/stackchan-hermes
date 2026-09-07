"""Concurrent segment synthesis with strictly ordered playback."""

from __future__ import annotations

from asyncio import Queue, Task, create_task, gather
from collections.abc import AsyncIterator, Callable
from time import monotonic
from typing import Literal, Protocol
from uuid import UUID

from stackchan_bridge.audio.types import PcmAudio
from stackchan_bridge.observability.metrics import BridgeMetrics
from stackchan_bridge.tts.adapters import (
    TtsAdapter,
    TtsResult,
    synthesize_with_timeout,
)
from stackchan_bridge.tts.errors import TtsError


class AudioPlayer(Protocol):
    async def play(self, device_id: str, *, turn_id: UUID, audio: PcmAudio) -> UUID: ...


class SegmentPlaybackPipeline:
    """Overlap provider work without allowing out-of-order device playback."""

    def __init__(
        self,
        adapter: TtsAdapter,
        player: AudioPlayer,
        *,
        timeout_seconds: float,
        failure_policy: Literal["abort", "play_completed"] = "abort",
        metrics: BridgeMetrics | None = None,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("TTS timeout must be positive")
        self._adapter = adapter
        self._player = player
        self._timeout_seconds = timeout_seconds
        self._failure_policy = failure_policy
        self._metrics = metrics or BridgeMetrics()
        self._clock = clock

    async def run(
        self,
        device_id: str,
        *,
        turn_id: UUID,
        segments: list[str],
        turn_started_at: float | None = None,
    ) -> list[UUID]:
        if not segments or any(not segment.strip() for segment in segments):
            raise ValueError("TTS pipeline requires non-empty speech segments")

        async def source() -> AsyncIterator[str]:
            for segment in segments:
                yield segment

        return await self.run_streaming(
            device_id,
            turn_id=turn_id,
            segments=source(),
            turn_started_at=turn_started_at,
        )

    async def run_streaming(
        self,
        device_id: str,
        *,
        turn_id: UUID,
        segments: AsyncIterator[str],
        turn_started_at: float | None = None,
    ) -> list[UUID]:
        """Synthesize arriving segments concurrently and play them in source order."""

        synthesis_tasks: list[Task[TtsResult]] = []
        ready: Queue[Task[TtsResult] | None] = Queue()

        async def produce() -> None:
            try:
                async for segment in segments:
                    if not segment.strip():
                        raise ValueError("TTS pipeline requires non-empty speech segments")
                    synthesis = create_task(self._synthesize(segment))
                    synthesis_tasks.append(synthesis)
                    await ready.put(synthesis)
            finally:
                await ready.put(None)

        producer = create_task(produce())
        stream_ids: list[UUID] = []
        first_synthesis_error: TtsError | None = None
        first_playback_recorded = False
        try:
            while (synthesis := await ready.get()) is not None:
                try:
                    result = await synthesis
                except TtsError as error:
                    if self._failure_policy == "abort":
                        raise
                    if first_synthesis_error is None:
                        first_synthesis_error = error
                    continue
                if not first_playback_recorded and turn_started_at is not None:
                    self._metrics.time_to_first_audio_seconds.observe(
                        max(0, self._clock() - turn_started_at)
                    )
                    first_playback_recorded = True
                stream_ids.append(
                    await self._player.play(
                        device_id,
                        turn_id=turn_id,
                        audio=result.audio,
                    )
                )
            await producer
            if not synthesis_tasks:
                raise ValueError("TTS pipeline requires non-empty speech segments")
            if first_synthesis_error is not None:
                raise first_synthesis_error
            return stream_ids
        finally:
            if not producer.done():
                producer.cancel()
            for synthesis in synthesis_tasks:
                if not synthesis.done():
                    synthesis.cancel()
            await gather(producer, *synthesis_tasks, return_exceptions=True)

    async def _synthesize(self, segment: str) -> TtsResult:
        started_at = self._clock()
        try:
            return await synthesize_with_timeout(
                self._adapter,
                segment,
                timeout_seconds=self._timeout_seconds,
            )
        finally:
            self._metrics.tts_duration_seconds.observe(max(0, self._clock() - started_at))
