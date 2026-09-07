from __future__ import annotations

from asyncio import Event, create_task
from time import monotonic
from uuid import UUID, uuid4

import pytest
from prometheus_client import generate_latest
from stackchan_bridge.audio.types import PcmAudio
from stackchan_bridge.observability.metrics import BridgeMetrics
from stackchan_bridge.tts.adapters import MockTtsAdapter, TtsResult
from stackchan_bridge.tts.errors import TtsProviderError
from stackchan_bridge.tts.pipeline import SegmentPlaybackPipeline


class OutOfOrderTtsAdapter:
    def __init__(self) -> None:
        self.first_started = Event()
        self.release_first = Event()
        self.second_finished = Event()

    async def synthesize(self, text: str) -> TtsResult:
        if text == "first":
            self.first_started.set()
            await self.release_first.wait()
        else:
            self.second_finished.set()
        marker = 1 if text == "first" else 2
        return TtsResult(
            audio=PcmAudio(pcm=bytes([marker, 0]) * 320),
            provider_metadata={"text": text},
        )


class RecordingPlayer:
    def __init__(self) -> None:
        self.played_markers: list[int] = []

    async def play(self, device_id: str, *, turn_id: UUID, audio: PcmAudio) -> UUID:
        self.played_markers.append(audio.pcm[0])
        return uuid4()


@pytest.mark.asyncio
async def test_tts_pipeline_generates_concurrently_but_plays_in_segment_order() -> None:
    adapter = OutOfOrderTtsAdapter()
    player = RecordingPlayer()
    pipeline = SegmentPlaybackPipeline(adapter, player, timeout_seconds=1)
    turn_id = UUID("168b58ca-7c31-4744-b445-d2f20c9bdde0")

    task = create_task(
        pipeline.run(
            "sim-001",
            turn_id=turn_id,
            segments=["first", "second"],
        )
    )
    await adapter.first_started.wait()
    await adapter.second_finished.wait()
    assert player.played_markers == []

    adapter.release_first.set()
    stream_ids = await task

    assert player.played_markers == [1, 2]
    assert len(stream_ids) == 2


class FirstSegmentFailsTtsAdapter:
    async def synthesize(self, text: str) -> TtsResult:
        if text == "first":
            raise TtsProviderError("first segment failed")
        return TtsResult(
            audio=PcmAudio(pcm=b"\x02\x00" * 320),
            provider_metadata={"text": text},
        )


@pytest.mark.asyncio
async def test_tts_pipeline_can_play_completed_segments_before_returning_an_error() -> None:
    player = RecordingPlayer()
    pipeline = SegmentPlaybackPipeline(
        FirstSegmentFailsTtsAdapter(),
        player,
        timeout_seconds=1,
        failure_policy="play_completed",
    )

    with pytest.raises(TtsProviderError):
        await pipeline.run(
            "sim-001",
            turn_id=UUID("168b58ca-7c31-4744-b445-d2f20c9bdde0"),
            segments=["first", "second"],
        )

    assert player.played_markers == [2]


@pytest.mark.asyncio
async def test_tts_pipeline_records_provider_and_first_audio_timings() -> None:
    metrics = BridgeMetrics()
    pipeline = SegmentPlaybackPipeline(
        MockTtsAdapter(milliseconds_per_character=1, minimum_duration_ms=20),
        RecordingPlayer(),
        timeout_seconds=1,
        metrics=metrics,
    )

    await pipeline.run(
        "sim-001",
        turn_id=UUID("168b58ca-7c31-4744-b445-d2f20c9bdde0"),
        segments=["first", "second"],
        turn_started_at=monotonic() - 0.01,
    )

    output = generate_latest(metrics.registry)
    assert b"tts_duration_seconds_count 2.0" in output
    assert b"time_to_first_audio_seconds_count 1.0" in output
