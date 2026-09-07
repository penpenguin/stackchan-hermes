from __future__ import annotations

import asyncio
import gc
from collections.abc import AsyncIterator
from pathlib import Path
from typing import cast
from uuid import UUID, uuid4

import pytest
from stackchan_bridge.audio.codec import AudioCodecError, OpusCodec, OpusCodecConfig
from stackchan_bridge.audio.debug_store import DebugAudioStore
from stackchan_bridge.audio.input import VoiceAudioInputHandler
from stackchan_bridge.audio.types import PcmAudio
from stackchan_bridge.audio.vad import RmsVadConfig
from stackchan_bridge.hermes.client import HermesEvent
from stackchan_bridge.hermes.segmenter import SpeechSegmenterConfig
from stackchan_bridge.protocol.models import (
    AudioInputEndMessage,
    AudioInputStartMessage,
    ProtocolErrorCode,
)
from stackchan_bridge.stt.adapters import MockSttAdapter
from stackchan_bridge.tts.adapters import MockTtsAdapter
from stackchan_bridge.tts.pipeline import SegmentPlaybackPipeline
from stackchan_bridge.turns.coordinator import Turn, TurnCoordinator, TurnState
from stackchan_bridge.turns.service import VoiceTurnService

from .test_audio_codec import sine_pcm


class OneSentenceHermes:
    def stream_text_response(
        self,
        *,
        device_id: str,
        transcript: str,
    ) -> AsyncIterator[HermesEvent]:
        async def events() -> AsyncIterator[HermesEvent]:
            yield HermesEvent(type="response.created", response_id="resp_input_1")
            yield HermesEvent(type="response.output_text.delta", delta="聞こえました。")
            yield HermesEvent(type="response.completed", response_id="resp_input_1")

        return events()


class RecordingPlayer:
    def __init__(self) -> None:
        self.audio: list[PcmAudio] = []

    async def play(self, device_id: str, *, turn_id: UUID, audio: PcmAudio) -> UUID:
        self.audio.append(audio)
        return uuid4()


class FailingTurnService:
    def __init__(self) -> None:
        self.finished = asyncio.Event()

    async def run_existing_turn(self, turn: object, *, audio: PcmAudio) -> object:
        self.finished.set()
        raise RuntimeError("background turn failed")


class BlockingTurnService:
    def __init__(self, coordinator: TurnCoordinator) -> None:
        self.coordinator = coordinator
        self.started = asyncio.Event()
        self.cancelled = asyncio.Event()

    async def run_existing_turn(self, turn: Turn, *, audio: PcmAudio) -> Turn:
        task = asyncio.current_task()
        assert task is not None
        self.coordinator.attach_task(turn.turn_id, task)
        self.started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.cancelled.set()
            raise
        return turn


def input_start(
    *,
    turn_id: str = "168b58ca-7c31-4744-b445-d2f20c9bdde0",
    stream_id: str = "90c213a0-61a0-4564-9a12-124ddb855c04",
) -> AudioInputStartMessage:
    return AudioInputStartMessage.model_validate(
        {
            "v": 1,
            "type": "audio.input.start",
            "message_id": "4154f260-6354-4827-8b4d-30782c14fe4e",
            "turn_id": turn_id,
            "stream_id": stream_id,
            "sent_at_ms": 1,
            "payload": {
                "codec": "opus",
                "sample_rate": 16_000,
                "channels": 1,
                "frame_ms": 60,
                "trigger": "touch",
            },
        }
    )


def test_audio_input_handler_rejects_duration_above_protocol_limit() -> None:
    with pytest.raises(ValueError, match="15000"):
        VoiceAudioInputHandler(
            TurnCoordinator(),
            cast(VoiceTurnService, FailingTurnService()),
            max_recording_ms=15_001,
        )


@pytest.mark.asyncio
async def test_audio_input_handler_decodes_an_owned_stream_into_a_voice_turn(
    tmp_path: Path,
) -> None:
    coordinator = TurnCoordinator()
    player = RecordingPlayer()
    service = VoiceTurnService(
        coordinator=coordinator,
        stt=MockSttAdapter(text="入力です", language="ja", confidence=1.0),
        hermes=OneSentenceHermes(),
        tts_pipeline=SegmentPlaybackPipeline(
            MockTtsAdapter(milliseconds_per_character=20, minimum_duration_ms=100),
            player,
            timeout_seconds=1,
        ),
        segmenter_config=SpeechSegmenterConfig(),
        stt_timeout_seconds=1,
    )
    handler = VoiceAudioInputHandler(
        coordinator,
        service,
        max_recording_ms=15_000,
        debug_audio_store=DebugAudioStore(
            directory=tmp_path,
            ttl_seconds=600,
            enabled=True,
        ),
    )
    start = input_start()
    codec = OpusCodec(OpusCodecConfig(frame_ms=60))

    await handler.start("sim-001", start)
    await handler.frame("sim-001", start, codec.encode(sine_pcm(60)))
    await handler.end(
        "sim-001",
        AudioInputEndMessage.model_validate(
            {
                "v": 1,
                "type": "audio.input.end",
                "message_id": "0581ece7-3baf-4277-9420-eeea9dfa35b6",
                "turn_id": start.turn_id,
                "stream_id": start.stream_id,
                "sent_at_ms": 2,
                "payload": {"reason": "silence"},
            }
        ),
    )
    completed = await handler.wait_for_turn(start.turn_id)

    assert completed.state is TurnState.COMPLETED
    assert completed.input_stream_id == start.stream_id
    assert completed.transcript == "入力です"
    assert len(player.audio) == 1
    assert (tmp_path / f"{start.turn_id.hex}.wav").read_bytes().startswith(b"RIFF")
    assert coordinator.current("sim-001") is None


@pytest.mark.asyncio
async def test_audio_input_handler_starts_a_turn_when_bridge_vad_detects_silence() -> None:
    coordinator = TurnCoordinator()
    player = RecordingPlayer()
    service = VoiceTurnService(
        coordinator=coordinator,
        stt=MockSttAdapter(text="VAD入力です", language="ja", confidence=1.0),
        hermes=OneSentenceHermes(),
        tts_pipeline=SegmentPlaybackPipeline(
            MockTtsAdapter(milliseconds_per_character=1, minimum_duration_ms=20),
            player,
            timeout_seconds=1,
        ),
        segmenter_config=SpeechSegmenterConfig(),
        stt_timeout_seconds=1,
    )
    handler = VoiceAudioInputHandler(
        coordinator,
        service,
        max_recording_ms=1_000,
        vad_config=RmsVadConfig(
            frame_ms=20,
            start_speech_ms=60,
            end_silence_ms=60,
            minimum_speech_ms=60,
            preroll_ms=0,
            maximum_recording_ms=1_000,
        ),
    )
    start = input_start()
    codec = OpusCodec(OpusCodecConfig(frame_ms=60))

    await handler.start("sim-001", start)
    await handler.frame("sim-001", start, codec.encode(sine_pcm(60)))
    await handler.frame("sim-001", start, codec.encode(b"\x00\x00" * 960))
    await handler.frame("sim-001", start, codec.encode(b"\x00\x00" * 960))
    completed = await handler.wait_for_turn(start.turn_id)

    assert completed.state is TurnState.COMPLETED
    assert completed.transcript == "VAD入力です"
    assert len(player.audio) == 1


@pytest.mark.asyncio
async def test_audio_input_handler_rejects_noise_only_when_device_ends_stream() -> None:
    coordinator = TurnCoordinator()
    service = VoiceTurnService(
        coordinator=coordinator,
        stt=MockSttAdapter(text="呼ばれてはいけません", language="ja", confidence=1.0),
        hermes=OneSentenceHermes(),
        tts_pipeline=SegmentPlaybackPipeline(
            MockTtsAdapter(),
            RecordingPlayer(),
            timeout_seconds=1,
        ),
        segmenter_config=SpeechSegmenterConfig(),
        stt_timeout_seconds=1,
    )
    handler = VoiceAudioInputHandler(
        coordinator,
        service,
        max_recording_ms=1_000,
        vad_config=RmsVadConfig(maximum_recording_ms=1_000),
    )
    start = input_start()
    codec = OpusCodec(OpusCodecConfig(frame_ms=60))

    await handler.start("sim-001", start)
    active = coordinator.current("sim-001")
    assert active is not None
    await handler.frame("sim-001", start, codec.encode(b"\x00\x00" * 960))
    await handler.end(
        "sim-001",
        AudioInputEndMessage.model_validate(
            {
                "v": 1,
                "type": "audio.input.end",
                "message_id": "fb9ab1d8-f3a8-4edf-8245-23518b235b50",
                "turn_id": start.turn_id,
                "stream_id": start.stream_id,
                "sent_at_ms": 2,
                "payload": {"reason": "silence"},
            }
        ),
    )

    assert active.state is TurnState.FAILED
    assert active.failure_reason == "NO_SPEECH"
    assert coordinator.current("sim-001") is None


@pytest.mark.asyncio
async def test_audio_input_handler_retrieves_unawaited_background_failure() -> None:
    loop = asyncio.get_running_loop()
    reported: list[dict[str, object]] = []
    previous_handler = loop.get_exception_handler()
    loop.set_exception_handler(lambda _loop, context: reported.append(context))
    try:
        coordinator = TurnCoordinator()
        service = FailingTurnService()
        handler = VoiceAudioInputHandler(
            coordinator,
            cast(VoiceTurnService, service),
            max_recording_ms=1_000,
        )
        start = input_start()
        codec = OpusCodec(OpusCodecConfig(frame_ms=60))

        await handler.start("sim-001", start)
        await handler.frame("sim-001", start, codec.encode(sine_pcm(60)))
        await handler.end(
            "sim-001",
            AudioInputEndMessage.model_validate(
                {
                    "v": 1,
                    "type": "audio.input.end",
                    "message_id": "4c49b84a-2b27-44a7-9797-dbbf138ddcad",
                    "turn_id": start.turn_id,
                    "stream_id": start.stream_id,
                    "sent_at_ms": 2,
                    "payload": {"reason": "silence"},
                }
            ),
        )
        await service.finished.wait()
        await asyncio.sleep(0)

        del handler
        gc.collect()
        await asyncio.sleep(0)
    finally:
        loop.set_exception_handler(previous_handler)

    assert not any(
        context.get("message") == "Task exception was never retrieved" for context in reported
    )


@pytest.mark.asyncio
async def test_new_audio_input_replaces_a_turn_that_is_processing_previous_audio() -> None:
    coordinator = TurnCoordinator()
    service = BlockingTurnService(coordinator)
    handler = VoiceAudioInputHandler(
        coordinator,
        cast(VoiceTurnService, service),
        max_recording_ms=15_000,
    )
    first = input_start()
    second = input_start(
        turn_id="fe97b185-15e2-4029-af93-dc3f44bb9745",
        stream_id="90e83c48-eec7-4221-a17e-a4847540157d",
    )
    codec = OpusCodec(OpusCodecConfig(frame_ms=60))

    await handler.start("sim-001", first)
    await handler.frame("sim-001", first, codec.encode(sine_pcm(60)))
    await handler.end(
        "sim-001",
        AudioInputEndMessage.model_validate(
            {
                "v": 1,
                "type": "audio.input.end",
                "message_id": "0581ece7-3baf-4277-9420-eeea9dfa35b6",
                "turn_id": first.turn_id,
                "stream_id": first.stream_id,
                "sent_at_ms": 2,
                "payload": {"reason": "silence"},
            }
        ),
    )
    await service.started.wait()

    await handler.start("sim-001", second)

    assert service.cancelled.is_set()
    assert coordinator.current("sim-001") is not None
    assert coordinator.current("sim-001").turn_id == second.turn_id
    await handler.disconnect("sim-001", second)


@pytest.mark.asyncio
async def test_audio_input_deadline_allows_a_wire_grace_for_max_duration_end() -> None:
    coordinator = TurnCoordinator()
    handler = VoiceAudioInputHandler(
        coordinator,
        cast(VoiceTurnService, FailingTurnService()),
        max_recording_ms=10,
    )
    start = input_start()

    await handler.start("sim-001", start)
    turn = coordinator.current("sim-001")
    assert turn is not None
    await asyncio.sleep(0.03)

    await handler.end(
        "sim-001",
        AudioInputEndMessage.model_validate(
            {
                "v": 1,
                "type": "audio.input.end",
                "message_id": "ce7ffb5e-2bd6-47e2-a60a-75feb5929971",
                "turn_id": start.turn_id,
                "stream_id": start.stream_id,
                "sent_at_ms": 11,
                "payload": {"reason": "max_duration"},
            }
        ),
    )

    assert turn.state is TurnState.FAILED
    assert turn.failure_reason == "EMPTY_AUDIO"


@pytest.mark.asyncio
async def test_audio_input_deadline_cancels_a_stream_without_packets_or_end(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "stackchan_bridge.audio.input._RECORDING_DEADLINE_GRACE_SECONDS",
        0.01,
    )
    coordinator = TurnCoordinator()
    handler = VoiceAudioInputHandler(
        coordinator,
        cast(VoiceTurnService, FailingTurnService()),
        max_recording_ms=10,
    )
    start = input_start()
    timed_out: list[tuple[str, AudioInputStartMessage]] = []
    handler.set_stream_timeout_handler(
        lambda device_id, stream: timed_out.append((device_id, stream))
    )

    await handler.start("sim-001", start)
    turn = coordinator.current("sim-001")
    assert turn is not None
    await asyncio.sleep(0.03)

    assert coordinator.current("sim-001") is None
    assert turn.state is TurnState.CANCELLING
    assert turn.failure_reason == "MAX_RECORDING_EXCEEDED"
    assert timed_out == [("sim-001", start)]


@pytest.mark.asyncio
@pytest.mark.parametrize("accepted", [True, False])
async def test_vad_completion_keeps_wire_deadline_without_cancelling_processing(
    monkeypatch: pytest.MonkeyPatch,
    accepted: bool,
) -> None:
    monkeypatch.setattr("stackchan_bridge.audio.input._RECORDING_DEADLINE_GRACE_SECONDS", 0.01)
    coordinator = TurnCoordinator()
    service = BlockingTurnService(coordinator)
    handler = VoiceAudioInputHandler(
        coordinator,
        cast(VoiceTurnService, service),
        max_recording_ms=240,
        vad_config=RmsVadConfig(
            frame_ms=20,
            start_speech_ms=60,
            end_silence_ms=60,
            minimum_speech_ms=60 if accepted else 240,
            preroll_ms=0,
            maximum_recording_ms=240,
        ),
    )
    expired = asyncio.Event()
    expired_streams: list[AudioInputStartMessage] = []

    def on_expired(device_id: str, stream: AudioInputStartMessage) -> None:
        assert device_id == "sim-001"
        expired_streams.append(stream)
        expired.set()

    handler.set_stream_timeout_handler(on_expired)
    first = input_start()
    second = input_start(turn_id=str(uuid4()), stream_id=str(uuid4()))
    codec = OpusCodec(OpusCodecConfig(frame_ms=60))
    try:
        await handler.start("sim-001", first)
        await handler.frame("sim-001", first, codec.encode(sine_pcm(60)))
        for _ in range(2):
            await handler.frame("sim-001", first, codec.encode(b"\x00\x00" * 960))
        if accepted:
            await asyncio.wait_for(service.started.wait(), timeout=1)
        else:
            assert coordinator.current("sim-001") is None
        await asyncio.wait_for(expired.wait(), timeout=0.5)

        assert expired_streams == [first]
        assert not service.cancelled.is_set()
        if accepted:
            assert coordinator.current("sim-001").turn_id == first.turn_id
        await handler.start("sim-001", second)
        assert coordinator.current("sim-001").turn_id == second.turn_id
        assert service.cancelled.is_set() is accepted
    finally:
        await handler.disconnect("sim-001", first)
        await handler.disconnect("sim-001", second)
        await coordinator.cancel_device("sim-001", reason="test_cleanup")


@pytest.mark.asyncio
async def test_audio_input_handler_isolates_one_opus_decode_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    coordinator = TurnCoordinator()
    handler = VoiceAudioInputHandler(
        coordinator,
        cast(VoiceTurnService, FailingTurnService()),
        max_recording_ms=1_000,
        max_decode_errors=3,
    )
    start = input_start()
    original_decode = OpusCodec.decode
    failed_once = False

    def fail_first_decode(codec: OpusCodec, packet: bytes) -> bytes:
        nonlocal failed_once
        if not failed_once:
            failed_once = True
            codec._recover_decoder()
            raise AudioCodecError("isolated malformed packet")
        return original_decode(codec, packet)

    monkeypatch.setattr(OpusCodec, "decode", fail_first_decode)
    encoder = OpusCodec(OpusCodecConfig(frame_ms=60))

    await handler.start("sim-001", start)
    await handler.frame("sim-001", start, b"malformed")
    await handler.frame("sim-001", start, encoder.encode(sine_pcm(60)))

    active = coordinator.current("sim-001")
    assert active is not None
    assert active.turn_id == start.turn_id
    await handler.disconnect("sim-001", start)


@pytest.mark.asyncio
async def test_empty_opus_packets_end_only_the_failed_input_stream() -> None:
    coordinator = TurnCoordinator()
    handler = VoiceAudioInputHandler(
        coordinator,
        cast(VoiceTurnService, FailingTurnService()),
        max_recording_ms=1_000,
    )
    first = input_start()
    second = input_start(turn_id=str(uuid4()), stream_id=str(uuid4()))
    try:
        await handler.start("sim-001", first)
        assert [await handler.frame("sim-001", first, b"") for _ in range(3)] == [
            None,
            None,
            ProtocolErrorCode.AUDIO_DECODE_ERROR,
        ]
        assert coordinator.current("sim-001") is None
        await handler.start("sim-001", second)
        assert coordinator.current("sim-001").turn_id == second.turn_id
    finally:
        await handler.disconnect("sim-001", first)
        await handler.disconnect("sim-001", second)


@pytest.mark.asyncio
async def test_audio_input_handler_ends_only_the_stream_at_the_decode_error_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    coordinator = TurnCoordinator()
    handler = VoiceAudioInputHandler(
        coordinator,
        cast(VoiceTurnService, FailingTurnService()),
        max_recording_ms=1_000,
        max_decode_errors=3,
    )
    first = input_start()

    def fail_decode(codec: OpusCodec, _packet: bytes) -> bytes:
        codec._recover_decoder()
        raise AudioCodecError("malformed packet")

    monkeypatch.setattr(OpusCodec, "decode", fail_decode)

    await handler.start("sim-001", first)
    outcomes = [await handler.frame("sim-001", first, b"malformed") for _ in range(3)]

    assert outcomes == [None, None, ProtocolErrorCode.AUDIO_DECODE_ERROR]
    assert coordinator.current("sim-001") is None

    second = input_start(
        turn_id="268b58ca-7c31-4744-b445-d2f20c9bdde0",
        stream_id="a0c213a0-61a0-4564-9a12-124ddb855c04",
    )
    await handler.start("sim-001", second)
    assert coordinator.current("sim-001") is not None
    await handler.disconnect("sim-001", second)
