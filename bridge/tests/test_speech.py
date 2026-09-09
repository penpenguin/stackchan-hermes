from __future__ import annotations

from asyncio import Event, gather, sleep, wait_for
from typing import cast
from uuid import UUID, uuid4

import pytest
from fastapi import WebSocket
from pydantic import ValidationError
from stackchan_bridge.audio.types import PcmAudio
from stackchan_bridge.device_gateway.application import (
    DeviceCapabilityError,
    DeviceConnection,
    DeviceNotConnectedError,
    DeviceRegistry,
)
from stackchan_bridge.tts.adapters import TtsResult
from stackchan_bridge.tts.errors import TtsProviderError, TtsTimeoutError
from stackchan_bridge.turns.coordinator import (
    TurnBusyError,
    TurnCoordinator,
    TurnState,
    TurnTrigger,
)
from stackchan_bridge.turns.speech import SpeechTurnService, split_speech_text

from .test_control_api import simulator_hello


class SpeechSocket:
    async def close(self, **kwargs: object) -> None:
        pass


class RecordingTts:
    def __init__(self) -> None:
        self.texts: list[str] = []
        self.started = Event()
        self.release = Event()
        self.release.set()
        self.error: Exception | None = None
        self.fail_at = 1

    async def synthesize(self, text: str) -> TtsResult:
        self.texts.append(text)
        self.started.set()
        await self.release.wait()
        if self.error is not None and len(self.texts) == self.fail_at:
            raise self.error
        return TtsResult(PcmAudio(pcm=b"\x01\x00" * 320), {})


class RecordingPlayer:
    def __init__(self) -> None:
        self.turns: list[UUID] = []
        self.started = Event()
        self.release = Event()
        self.release.set()

    async def play(self, device_id: str, *, turn_id: UUID, audio: PcmAudio) -> UUID:
        self.turns.append(turn_id)
        self.started.set()
        await self.release.wait()
        return uuid4()


async def make_service(**kwargs: object):
    registry = DeviceRegistry(command_timeout_seconds=1)
    connection = DeviceConnection(
        device_id="sim-001",
        connection_id=uuid4(),
        hello=simulator_hello(),
        websocket=cast(WebSocket, SpeechSocket()),
    )
    await registry.register(connection)
    coordinator = TurnCoordinator()
    adapter = RecordingTts()
    player = RecordingPlayer()
    options = {"timeout_seconds": 1, "segment_max_characters": 80, **kwargs}
    service = SpeechTurnService(
        registry=registry,
        coordinator=coordinator,
        adapter=adapter,
        player=player,
        **options,
    )
    return service, coordinator, registry, adapter, player


async def finished(service: SpeechTurnService, turn_id: UUID):
    async def poll():
        while True:
            status = service.get("sim-001", turn_id)
            if status.state in {"COMPLETED", "CANCELLED", "FAILED"}:
                return status
            await sleep(0)

    return await wait_for(poll(), 2)


@pytest.mark.parametrize(
    "text",
    ["あ" * 1000, "短い。文\uff01\n続き?", "**文章** [リンク](https://example.test) 🙂 " * 8],
)
def test_split_preserves_all_non_whitespace_and_bounds_segments(text: str) -> None:
    segments = split_speech_text(text, 80)
    assert all(0 < len(segment) <= 80 for segment in segments)
    assert "".join("".join(segments).split()) == "".join(text.split())


def test_split_prefers_sentence_boundaries() -> None:
    assert split_speech_text("最初。次の長い文章です。最後。", 8) == [
        "最初。",
        "次の長い文章です",
        "。最後。",
    ]


@pytest.mark.asyncio
async def test_speech_accepts_before_synthesis_and_reads_full_text_in_order() -> None:
    service, coordinator, _, adapter, player = await make_service()
    adapter.release.clear()
    text = "最初の文章。" + "あ" * 985 + "末尾の文章です。"
    accepted = await service.start("sim-001", text=text)
    assert accepted.state == "ACCEPTED"
    assert coordinator.current("sim-001").state is TurnState.SYNTHESIZING
    await wait_for(adapter.started.wait(), 1)
    assert service.get("sim-001", accepted.turn_id).state == "RUNNING"
    assert player.turns == []
    with pytest.raises(TurnBusyError):
        await service.start("sim-001", text="二重発話")
    adapter.release.set()
    assert (await finished(service, accepted.turn_id)).state == "COMPLETED"
    assert "".join(adapter.texts) == text
    assert player.turns == [accepted.turn_id] * len(adapter.texts)
    assert coordinator.current("sim-001") is None
    await service.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text", ["", " \n\t", "あ" * 1001, 123], ids=["empty", "blank", "too-long", "number"]
)
async def test_speech_rejects_invalid_text_before_reserving_or_synthesizing(text: object) -> None:
    service, coordinator, _, adapter, _ = await make_service()
    with pytest.raises(ValidationError):
        await service.start("sim-001", text=text)
    assert coordinator.current("sim-001") is None
    assert adapter.texts == []
    await service.aclose()


@pytest.mark.asyncio
async def test_speech_cancellation_before_worker_starts_releases_turn() -> None:
    service, coordinator, _, adapter, _ = await make_service()
    accepted = await service.start("sim-001", text="即時停止")
    assert await coordinator.cancel_turn("sim-001", accepted.turn_id, reason="CONTROL_API_CANCEL")
    assert (await finished(service, accepted.turn_id)).state == "CANCELLED"
    assert adapter.texts == []
    assert coordinator.current("sim-001") is None
    await service.aclose()


@pytest.mark.parametrize("limit", [0, -1])
def test_split_rejects_nonpositive_limit(limit: int) -> None:
    with pytest.raises(ValueError):
        split_speech_text("文章", limit)


@pytest.mark.asyncio
async def test_speech_validates_device_and_speaker_before_work() -> None:
    service, coordinator, registry, adapter, _ = await make_service()
    with pytest.raises(ValidationError):
        await service.start("../invalid", text="文章")
    with pytest.raises(DeviceNotConnectedError):
        await service.start("offline", text="文章")
    registry.get_connection("sim-001").hello.payload.capabilities.speaker = False
    with pytest.raises(DeviceCapabilityError):
        await service.start("sim-001", text="文章")
    assert coordinator.current("sim-001") is None
    assert adapter.texts == []
    await service.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "state", [TurnState.CAPTURING, TurnState.WAITING_HERMES, TurnState.PLAYING]
)
async def test_speech_preserves_an_active_conversation(state: TurnState) -> None:
    service, coordinator, _, adapter, _ = await make_service()
    turn = await coordinator.begin("sim-001", trigger=TurnTrigger.TOUCH)
    for next_state in [
        TurnState.TRANSCRIBING,
        TurnState.WAITING_HERMES,
        TurnState.SYNTHESIZING,
        TurnState.PLAYING,
    ]:
        if turn.state == state:
            break
        await coordinator.transition(turn.turn_id, next_state)
    with pytest.raises(TurnBusyError):
        await service.start("sim-001", text="通知")
    assert coordinator.current("sim-001") is turn
    assert not turn.cancellation.is_set()
    assert adapter.texts == []
    await service.aclose()
    assert coordinator.current("sim-001") is turn
    await coordinator.cancel_turn("sim-001", turn.turn_id, reason="test_cleanup")


@pytest.mark.asyncio
async def test_concurrent_requests_reserve_only_one_turn() -> None:
    service, _, _, adapter, _ = await make_service()
    adapter.release.clear()
    results = await gather(
        service.start("sim-001", text="一つ目"),
        service.start("sim-001", text="二つ目"),
        return_exceptions=True,
    )
    assert sum(isinstance(result, TurnBusyError) for result in results) == 1
    await service.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "code"),
    [
        (TtsProviderError("private-provider-body"), "TTS_FAILED"),
        (TtsTimeoutError("private-provider-body"), "TTS_TIMEOUT"),
        (RuntimeError("private-provider-body"), "SPEECH_FAILED"),
    ],
)
async def test_speech_failure_is_safe_and_stops_remaining_segments(
    error: Exception, code: str, caplog
) -> None:
    service, coordinator, _, adapter, player = await make_service()
    adapter.error, adapter.fail_at = error, 2
    accepted = await service.start("sim-001", text="あ" * 200)
    status = await finished(service, accepted.turn_id)
    assert status.state == "FAILED"
    assert status.error_code == code
    assert "private-provider-body" not in status.model_dump_json() + caplog.text
    assert len(adapter.texts) == 2
    assert len(player.turns) == 1
    assert coordinator.current("sim-001") is None
    await service.aclose()


@pytest.mark.asyncio
async def test_speech_uses_configured_synthesis_deadline() -> None:
    service, coordinator, _, adapter, _ = await make_service(timeout_seconds=0.01)
    adapter.release.clear()
    accepted = await service.start("sim-001", text="通知")
    assert (await finished(service, accepted.turn_id)).error_code == "TTS_TIMEOUT"
    assert coordinator.current("sim-001") is None
    await service.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["accepted", "synthesizing", "playing"])
@pytest.mark.parametrize(
    ("reason", "state", "code"),
    [
        ("CONTROL_API_CANCEL", "CANCELLED", None),
        ("BARGE_IN", "CANCELLED", None),
        ("disconnect", "FAILED", "DEVICE_NOT_CONNECTED"),
        ("connection_replaced", "FAILED", "DEVICE_NOT_CONNECTED"),
        ("AUDIO_DECODE_ERROR", "FAILED", "AUDIO_DECODE_ERROR"),
    ],
)
async def test_cancel_settles_history_and_releases_work(
    phase: str, reason: str, state: str, code: str | None
) -> None:
    service, coordinator, registry, adapter, player = await make_service()
    adapter.release.clear()
    player.release.clear()
    accepted = await service.start("sim-001", text="あ" * 200)
    if phase != "accepted":
        await wait_for(adapter.started.wait(), 1)
    if phase == "playing":
        adapter.release.set()
        await wait_for(player.started.wait(), 1)
    await coordinator.cancel_turn("sim-001", accepted.turn_id, reason=reason)
    status = await finished(service, accepted.turn_id)
    assert (status.state, status.error_code) == (state, code)
    assert coordinator.current("sim-001") is None
    connection = registry.get_connection("sim-001")
    registry.unregister("sim-001", connection.connection_id)
    assert service.get("sim-001", accepted.turn_id) == status
    assert len(adapter.texts) <= 1
    await service.aclose()


@pytest.mark.asyncio
async def test_connection_replacement_during_synthesis_never_receives_old_audio() -> None:
    service, coordinator, registry, adapter, player = await make_service()
    adapter.release.clear()
    accepted = await service.start("sim-001", text="古い接続への文章")
    await wait_for(adapter.started.wait(), 1)
    await registry.register(
        DeviceConnection(
            device_id="sim-001",
            connection_id=uuid4(),
            hello=simulator_hello(),
            websocket=cast(WebSocket, SpeechSocket()),
        )
    )
    adapter.release.set()
    assert (await finished(service, accepted.turn_id)).error_code == "DEVICE_NOT_CONNECTED"
    assert player.turns == []
    assert coordinator.current("sim-001") is None
    await service.aclose()


@pytest.mark.asyncio
async def test_shutdown_settles_jobs_and_rejects_new_work() -> None:
    from stackchan_bridge.turns.speech import SpeechUnavailableError

    service, coordinator, _, adapter, _ = await make_service()
    adapter.release.clear()
    accepted = await service.start("sim-001", text="通知")
    await wait_for(adapter.started.wait(), 1)
    await service.aclose()
    assert service.get("sim-001", accepted.turn_id).state == "CANCELLED"
    assert coordinator.current("sim-001") is None
    with pytest.raises(SpeechUnavailableError):
        await service.start("sim-001", text="終了後")
    await service.aclose()


@pytest.mark.asyncio
async def test_history_is_scoped_bounded_and_expires_from_completion() -> None:
    from stackchan_bridge.turns.speech import SpeechNotFoundError

    now = [0.0]
    service, _, _, adapter, _ = await make_service(clock=lambda: now[0], max_history=2)
    accepted = await service.start("sim-001", text="最初")
    await finished(service, accepted.turn_id)
    with pytest.raises(SpeechNotFoundError):
        service.get("another-device", accepted.turn_id)
    with pytest.raises(SpeechNotFoundError):
        service.get("sim-001", uuid4())
    for _ in range(2):
        now[0] += 1
        last = await service.start("sim-001", text="次")
        await finished(service, last.turn_id)
    with pytest.raises(SpeechNotFoundError):
        service.get("sim-001", accepted.turn_id)
    adapter.release.clear()
    active = await service.start("sim-001", text="長い処理")
    now[0] = 602.0
    with pytest.raises(SpeechNotFoundError):
        service.get("sim-001", last.turn_id)
    assert service.get("sim-001", active.turn_id).state in {"ACCEPTED", "RUNNING"}
    adapter.release.set()
    await finished(service, active.turn_id)
    now[0] = 1201.0
    assert service.get("sim-001", active.turn_id).state == "COMPLETED"
    await service.aclose()
