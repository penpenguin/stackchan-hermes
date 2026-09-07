from __future__ import annotations

from asyncio import CancelledError
from collections.abc import AsyncIterator
from hashlib import sha256
from pathlib import Path
from time import time
from typing import cast
from uuid import UUID, uuid4

import pytest
from fastapi import WebSocket
from stackchan_bridge.audio.types import PcmAudio
from stackchan_bridge.captures.coordinator import CaptureCoordinator
from stackchan_bridge.captures.store import CaptureRecord, CaptureStore
from stackchan_bridge.device_gateway.application import DeviceConnection, DeviceRegistry
from stackchan_bridge.hermes.client import HermesEvent
from stackchan_bridge.hermes.segmenter import SpeechSegmenterConfig
from stackchan_bridge.tts.adapters import MockTtsAdapter
from stackchan_bridge.tts.pipeline import SegmentPlaybackPipeline
from stackchan_bridge.turns.coordinator import TurnCoordinator, TurnState
from stackchan_bridge.turns.vision import VisionTurnService
from stackchan_simulator.fixtures import generate_synthetic_jpeg

from .test_capture_coordinator import UploadingCaptureWebSocket
from .test_control_api import simulator_hello


class FakeCaptureProvider:
    def __init__(self, record: CaptureRecord) -> None:
        self.record = record
        self.calls: list[tuple[str, int]] = []

    async def take_photo(self, device_id: str, *, quality: int = 80) -> CaptureRecord:
        self.calls.append((device_id, quality))
        return self.record

    def delete_capture(self, capture_id: UUID) -> bool:
        assert capture_id == self.record.capture_id
        self.record.path.unlink()
        return True


class RecordingVisionHermes:
    def __init__(self, expected_jpeg: bytes) -> None:
        self.expected_jpeg = expected_jpeg
        self.calls: list[tuple[str, str]] = []

    def stream_vision_response(
        self,
        *,
        device_id: str,
        question: str,
        jpeg: bytes,
    ) -> AsyncIterator[HermesEvent]:
        assert jpeg == self.expected_jpeg
        self.calls.append((device_id, question))

        async def events() -> AsyncIterator[HermesEvent]:
            yield HermesEvent(type="response.created", response_id="resp_vision_turn_1")
            yield HermesEvent(
                type="response.output_item.added",
                item={"type": "function_call", "name": "stackchan_get_status"},
            )
            yield HermesEvent(
                type="response.output_item.done",
                item={"type": "function_call", "name": "stackchan_get_status"},
            )
            yield HermesEvent(type="response.output_text.delta", delta="机の上にロボットがいます。")
            yield HermesEvent(type="response.completed", response_id="resp_vision_turn_1")

        return events()


class RecordingPlayer:
    def __init__(self) -> None:
        self.played: list[PcmAudio] = []

    async def play(self, device_id: str, *, turn_id: UUID, audio: PcmAudio) -> UUID:
        self.played.append(audio)
        return uuid4()


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


@pytest.mark.asyncio
async def test_vision_turn_captures_sends_inline_image_and_speaks_response(tmp_path: Path) -> None:
    jpeg = generate_synthetic_jpeg()
    capture_id = UUID("3d27c065-15a7-4f85-87ba-df14912a8098")
    path = tmp_path / f"{capture_id.hex}.jpg"
    path.write_bytes(jpeg)
    now = time()
    record = CaptureRecord(
        capture_id=capture_id,
        device_id="sim-001",
        content_type="image/jpeg",
        size_bytes=len(jpeg),
        sha256=sha256(jpeg).hexdigest(),
        width=320,
        height=240,
        path=path,
        created_at=now,
        expires_at=now + 600,
    )
    coordinator = TurnCoordinator()
    capture = FakeCaptureProvider(record)
    hermes = RecordingVisionHermes(jpeg)
    player = RecordingPlayer()
    progress = RecordingProgressNotifier()
    service = VisionTurnService(
        coordinator=coordinator,
        captures=capture,
        hermes=hermes,
        tts_pipeline=SegmentPlaybackPipeline(
            MockTtsAdapter(milliseconds_per_character=1, minimum_duration_ms=20),
            player,
            timeout_seconds=1,
        ),
        segmenter_config=SpeechSegmenterConfig(),
        progress_notifier=progress,
    )

    completed = await service.run(
        "sim-001",
        question="何が見えますか",
        quality=75,
    )

    assert completed.state is TurnState.COMPLETED
    assert completed.capture_id == capture_id
    assert completed.hermes_response_id == "resp_vision_turn_1"
    assert len(completed.output_stream_ids) == 1
    assert capture.calls == [("sim-001", 75)]
    assert hermes.calls == [("sim-001", "何が見えますか")]
    assert len(player.played) == 1
    assert progress.tools == [("sim-001", completed.turn_id, "stackchan_get_status")]
    assert progress.completed_tools == [("sim-001", completed.turn_id, "stackchan_get_status")]
    assert coordinator.current("sim-001") is None


@pytest.mark.asyncio
@pytest.mark.parametrize("persist", [False, True])
@pytest.mark.parametrize(
    "outcome", ["success", "hermes_error", "playback_error", "cancel", "read_error"]
)
async def test_vision_deletes_only_its_owned_capture_before_remote_processing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, persist: bool, outcome: str
) -> None:
    jpeg = generate_synthetic_jpeg()
    store = CaptureStore(directory=tmp_path, ttl_seconds=600, max_bytes=2_097_152, persist=persist)
    unrelated = store.save(
        store.reserve("sim-002").capture_id,
        device_id="sim-002",
        content_type="image/jpeg",
        body=jpeg,
    )
    registry = DeviceRegistry(command_timeout_seconds=1)
    connection_id = uuid4()
    websocket = UploadingCaptureWebSocket(registry, connection_id, store)
    await registry.register(
        DeviceConnection(
            connection_id=connection_id,
            device_id="sim-001",
            hello=simulator_hello(),
            websocket=cast(WebSocket, websocket),
        )
    )

    class CheckingHermes(RecordingVisionHermes):
        def stream_vision_response(
            self, *, device_id: str, question: str, jpeg: bytes
        ) -> AsyncIterator[HermesEvent]:
            assert list(tmp_path.glob("*.jpg")) == [unrelated.path]
            if outcome == "hermes_error":
                raise RuntimeError("hermes_error")
            if outcome == "cancel":
                raise CancelledError
            return super().stream_vision_response(device_id=device_id, question=question, jpeg=jpeg)

    class CheckingPlayer(RecordingPlayer):
        async def play(self, device_id: str, *, turn_id: UUID, audio: PcmAudio) -> UUID:
            if outcome == "playback_error":
                raise RuntimeError("playback_error")
            return await super().play(device_id, turn_id=turn_id, audio=audio)

    if outcome == "read_error":

        def fail_read(path: Path) -> bytes:
            raise OSError("read_error")

        monkeypatch.setattr(Path, "read_bytes", fail_read)

    service = VisionTurnService(
        coordinator=TurnCoordinator(),
        captures=CaptureCoordinator(registry, store, timeout_seconds=1),
        hermes=CheckingHermes(jpeg),
        tts_pipeline=SegmentPlaybackPipeline(
            MockTtsAdapter(milliseconds_per_character=1, minimum_duration_ms=20),
            CheckingPlayer(),
            timeout_seconds=1,
        ),
        segmenter_config=SpeechSegmenterConfig(),
    )
    if outcome == "success":
        assert (
            await service.run("sim-001", question="何が見えますか")
        ).state is TurnState.COMPLETED
    else:
        error = (
            CancelledError
            if outcome == "cancel"
            else OSError
            if outcome == "read_error"
            else RuntimeError
        )
        with pytest.raises(error):
            await service.run("sim-001", question="何が見えますか")
    assert websocket.command is not None
    assert store.get(websocket.command.payload.args.capture_id) is None
    assert list(tmp_path.glob("*.jpg")) == [unrelated.path]
    assert store.get(unrelated.capture_id) is unrelated
