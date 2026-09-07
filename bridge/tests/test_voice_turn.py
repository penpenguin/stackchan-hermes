from __future__ import annotations

from asyncio import Event, create_task, wait_for
from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import pytest
from stackchan_bridge.audio.types import PcmAudio
from stackchan_bridge.hermes.client import HermesEvent
from stackchan_bridge.hermes.segmenter import SpeechSegmenterConfig
from stackchan_bridge.stt.adapters import MockSttAdapter
from stackchan_bridge.tts.adapters import MockTtsAdapter
from stackchan_bridge.tts.pipeline import SegmentPlaybackPipeline
from stackchan_bridge.turns.coordinator import TurnCoordinator, TurnState, TurnTrigger
from stackchan_bridge.turns.service import VoiceTurnError, VoiceTurnService


class SuccessfulHermes:
    def stream_text_response(
        self,
        *,
        device_id: str,
        transcript: str,
    ) -> AsyncIterator[HermesEvent]:
        async def events() -> AsyncIterator[HermesEvent]:
            yield HermesEvent(type="response.created", response_id="resp_voice_1")
            yield HermesEvent(type="response.output_text.delta", delta="はい。了解しました。")
            yield HermesEvent(type="response.completed", response_id="resp_voice_1")

        return events()


class RecordingPlayer:
    def __init__(self) -> None:
        self.durations: list[float] = []

    async def play(self, device_id: str, *, turn_id: UUID, audio: PcmAudio) -> UUID:
        self.durations.append(audio.duration_seconds)
        return uuid4()


class GatedHermes:
    def __init__(self) -> None:
        self.waiting_after_first_sentence = Event()
        self.release_response = Event()

    def stream_text_response(
        self,
        *,
        device_id: str,
        transcript: str,
    ) -> AsyncIterator[HermesEvent]:
        async def events() -> AsyncIterator[HermesEvent]:
            yield HermesEvent(type="response.created", response_id="resp_streaming_1")
            yield HermesEvent(type="response.output_text.delta", delta="最初の文です。")
            self.waiting_after_first_sentence.set()
            await self.release_response.wait()
            yield HermesEvent(type="response.output_text.delta", delta="次の文です。")
            yield HermesEvent(type="response.completed", response_id="resp_streaming_1")

        return events()


class NotifyingPlayer(RecordingPlayer):
    def __init__(self) -> None:
        super().__init__()
        self.first_playback_started = Event()

    async def play(self, device_id: str, *, turn_id: UUID, audio: PcmAudio) -> UUID:
        self.first_playback_started.set()
        return await super().play(device_id, turn_id=turn_id, audio=audio)


class RecordingFailureNotifier:
    def __init__(self) -> None:
        self.notifications: list[tuple[str, str]] = []

    async def notify_failure(self, device_id: str, *, error_code: str) -> None:
        self.notifications.append((device_id, error_code))


class RecordingProgressNotifier:
    def __init__(self) -> None:
        self.tools: list[tuple[str, UUID, str]] = []
        self.completed_tools: list[tuple[str, UUID, str]] = []

    async def notify_tool_started(
        self,
        device_id: str,
        *,
        turn_id: UUID,
        tool_name: str,
    ) -> None:
        self.tools.append((device_id, turn_id, tool_name))

    async def notify_tool_completed(
        self,
        device_id: str,
        *,
        turn_id: UUID,
        tool_name: str,
    ) -> None:
        self.completed_tools.append((device_id, turn_id, tool_name))


class ToolProgressHermes:
    def stream_text_response(
        self,
        *,
        device_id: str,
        transcript: str,
    ) -> AsyncIterator[HermesEvent]:
        async def events() -> AsyncIterator[HermesEvent]:
            yield HermesEvent(type="response.created", response_id="resp_tool_1")
            yield HermesEvent(
                type="response.output_item.added",
                item={"type": "function_call", "name": "stackchan_get_status"},
            )
            yield HermesEvent(
                type="response.output_item.done",
                item={"type": "function_call", "name": "stackchan_get_status"},
            )
            yield HermesEvent(type="response.output_text.delta", delta="確認しました。")
            yield HermesEvent(type="response.completed", response_id="resp_tool_1")

        return events()


@pytest.mark.asyncio
async def test_voice_turn_runs_public_hermes_and_ordered_tts_to_completion() -> None:
    coordinator = TurnCoordinator()
    player = RecordingPlayer()
    tts_pipeline = SegmentPlaybackPipeline(
        MockTtsAdapter(milliseconds_per_character=20, minimum_duration_ms=100),
        player,
        timeout_seconds=1,
    )
    service = VoiceTurnService(
        coordinator=coordinator,
        stt=MockSttAdapter(text="聞こえますか", language="ja", confidence=1.0),
        hermes=SuccessfulHermes(),
        tts_pipeline=tts_pipeline,
        segmenter_config=SpeechSegmenterConfig(
            max_segments=2,
            segment_max_characters=80,
            response_max_characters=160,
        ),
        stt_timeout_seconds=1,
    )
    turn_id = UUID("168b58ca-7c31-4744-b445-d2f20c9bdde0")

    completed = await service.run_audio_turn(
        "sim-001",
        turn_id=turn_id,
        trigger=TurnTrigger.TOUCH,
        audio=PcmAudio(pcm=b"\x00\x00" * 16_000),
    )

    assert completed.turn_id == turn_id
    assert completed.state is TurnState.COMPLETED
    assert completed.transcript == "聞こえますか"
    assert completed.hermes_response_id == "resp_voice_1"
    assert len(completed.output_stream_ids) == 2
    assert len(player.durations) == 2
    assert coordinator.current("sim-001") is None


@pytest.mark.asyncio
async def test_voice_turn_starts_first_sentence_before_hermes_response_completes() -> None:
    coordinator = TurnCoordinator()
    hermes = GatedHermes()
    player = NotifyingPlayer()
    service = VoiceTurnService(
        coordinator=coordinator,
        stt=MockSttAdapter(text="説明してください", language="ja", confidence=1.0),
        hermes=hermes,
        tts_pipeline=SegmentPlaybackPipeline(
            MockTtsAdapter(milliseconds_per_character=1, minimum_duration_ms=20),
            player,
            timeout_seconds=1,
        ),
        segmenter_config=SpeechSegmenterConfig(
            max_segments=2,
            segment_max_characters=80,
            response_max_characters=160,
        ),
        stt_timeout_seconds=1,
    )
    task = create_task(
        service.run_audio_turn(
            "sim-001",
            turn_id=UUID("59d12a9e-e06a-447b-952f-b06408d26523"),
            trigger=TurnTrigger.TOUCH,
            audio=PcmAudio(pcm=b"\x00\x00" * 16_000),
        )
    )

    await hermes.waiting_after_first_sentence.wait()
    try:
        await wait_for(player.first_playback_started.wait(), timeout=0.2)
    finally:
        hermes.release_response.set()
        completed = await task

    assert completed.state is TurnState.COMPLETED
    assert len(player.durations) == 2


@pytest.mark.asyncio
async def test_voice_turn_notifies_an_empty_transcript_and_releases_the_turn() -> None:
    coordinator = TurnCoordinator()
    notifier = RecordingFailureNotifier()
    service = VoiceTurnService(
        coordinator=coordinator,
        stt=MockSttAdapter(text="", language="ja", confidence=None),
        hermes=SuccessfulHermes(),
        tts_pipeline=SegmentPlaybackPipeline(
            MockTtsAdapter(),
            RecordingPlayer(),
            timeout_seconds=1,
        ),
        segmenter_config=SpeechSegmenterConfig(),
        stt_timeout_seconds=1,
        failure_notifier=notifier,
    )

    with pytest.raises(VoiceTurnError) as error:
        await service.run_audio_turn(
            "sim-001",
            turn_id=UUID("168b58ca-7c31-4744-b445-d2f20c9bdde0"),
            trigger=TurnTrigger.TOUCH,
            audio=PcmAudio(pcm=b"\x00\x00" * 16_000),
        )

    assert error.value.code == "EMPTY_TRANSCRIPT"
    assert notifier.notifications == [("sim-001", "EMPTY_TRANSCRIPT")]
    assert coordinator.current("sim-001") is None


@pytest.mark.asyncio
async def test_voice_turn_notifies_tool_progress_without_reexecuting_the_tool() -> None:
    coordinator = TurnCoordinator()
    notifier = RecordingProgressNotifier()
    turn_id = UUID("168b58ca-7c31-4744-b445-d2f20c9bdde0")
    service = VoiceTurnService(
        coordinator=coordinator,
        stt=MockSttAdapter(text="状態を確認して", language="ja", confidence=1.0),
        hermes=ToolProgressHermes(),
        tts_pipeline=SegmentPlaybackPipeline(
            MockTtsAdapter(),
            RecordingPlayer(),
            timeout_seconds=1,
        ),
        segmenter_config=SpeechSegmenterConfig(),
        stt_timeout_seconds=1,
        progress_notifier=notifier,
    )

    completed = await service.run_audio_turn(
        "sim-001",
        turn_id=turn_id,
        trigger=TurnTrigger.TOUCH,
        audio=PcmAudio(pcm=b"\x00\x00" * 16_000),
    )

    assert completed.state is TurnState.COMPLETED
    assert notifier.tools == [("sim-001", turn_id, "stackchan_get_status")]
    assert notifier.completed_tools == [("sim-001", turn_id, "stackchan_get_status")]
