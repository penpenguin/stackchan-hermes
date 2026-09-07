from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from typing import cast
from uuid import UUID, uuid4

import pytest
from fastapi import WebSocket
from prometheus_client import generate_latest
from stackchan_bridge.audio.input import VoiceAudioInputHandler
from stackchan_bridge.audio.output import AudioOutputStreamer
from stackchan_bridge.audio.types import PcmAudio
from stackchan_bridge.audio.vad import RmsVadConfig
from stackchan_bridge.device_gateway.application import DeviceConnection, DeviceRegistry
from stackchan_bridge.observability.metrics import BridgeMetrics
from stackchan_bridge.protocol.models import AudioInputEndMessage, EventMessage
from stackchan_bridge.turns.coordinator import TurnCoordinator, TurnState, TurnTrigger
from stackchan_bridge.turns.events import TurnEventHandler
from stackchan_bridge.turns.service import VoiceTurnService

from .test_audio_input import FailingTurnService, input_start
from .test_audio_output import RecordingOutputWebSocket
from .test_control_api import simulator_hello


class RecordingCommandSender:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, object], UUID | None]] = []

    async def send_command(
        self,
        device_id: str,
        name: str,
        args: Mapping[str, object],
        *,
        turn_id: UUID | None = None,
    ) -> object:
        self.calls.append((device_id, name, dict(args), turn_id))
        return object()


class BlockingCommandSender(RecordingCommandSender):
    def __init__(self) -> None:
        super().__init__()
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def send_command(
        self,
        device_id: str,
        name: str,
        args: Mapping[str, object],
        *,
        turn_id: UUID | None = None,
    ) -> object:
        self.calls.append((device_id, name, dict(args), turn_id))
        self.started.set()
        await self.release.wait()
        return object()


class RecordingCaptureFailureReporter:
    def __init__(self) -> None:
        self.calls: list[tuple[str, UUID]] = []

    def report_failure(self, device_id: str, capture_id: UUID) -> bool:
        self.calls.append((device_id, capture_id))
        return True


def touch_tap() -> EventMessage:
    return EventMessage.model_validate(
        {
            "v": 1,
            "type": "event",
            "message_id": "04c3b5d1-9477-433c-9675-2c22bdb698a7",
            "device_id": "sim-001",
            "sent_at_ms": 1,
            "payload": {"name": "touch.tap", "data": {"x": 120, "y": 80}},
        }
    )


def camera_completed(*, ok: bool) -> EventMessage:
    return EventMessage.model_validate(
        {
            "v": 1,
            "type": "event",
            "message_id": "6cf29039-ce46-4585-b2a4-86c9e9e4d2d0",
            "device_id": "sim-001",
            "sent_at_ms": 2,
            "payload": {
                "name": "camera.completed",
                "data": {
                    "capture_id": "4936d914-cef8-443e-830a-d3c717ccc178",
                    "ok": ok,
                    **({} if ok else {"error_code": "CAPTURE_FAILED"}),
                },
            },
        }
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("event_name", ["touch.tap", "touch.long_press"])
async def test_touch_while_capturing_preserves_input_until_its_normal_end(event_name: str) -> None:
    coordinator = TurnCoordinator()
    sender = RecordingCommandSender()
    metrics = BridgeMetrics()
    events = TurnEventHandler(coordinator, sender, metrics=metrics)
    audio_input = VoiceAudioInputHandler(
        coordinator,
        cast(VoiceTurnService, FailingTurnService()),
        max_recording_ms=15_000,
        vad_config=RmsVadConfig(),
    )
    start = input_start()
    await audio_input.start("sim-001", start)
    turn = coordinator.current("sim-001")
    assert turn is not None
    event = EventMessage.model_validate(
        {
            **touch_tap().model_dump(mode="json"),
            "payload": {
                "name": event_name,
                "data": {
                    "x": 120,
                    "y": 80,
                    **({"duration_ms": 500} if event_name == "touch.long_press" else {}),
                },
            },
        }
    )
    try:
        await events.handle("sim-001", event)
        await asyncio.sleep(0)
        assert coordinator.current("sim-001") is turn
        assert turn.state is TurnState.CAPTURING
        assert not turn.cancellation.is_set()
        assert sender.calls == []
        assert events.last_touch("sim-001") is event.payload
        assert b"touch_events_total 1.0" in generate_latest(metrics.registry)
        await audio_input.end(
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
        assert turn.failure_reason == "NO_SPEECH"
        assert coordinator.current("sim-001") is None
        await audio_input.start("sim-001", start)
        assert coordinator.current("sim-001") is not None
    finally:
        await audio_input.disconnect("sim-001", start)


@pytest.mark.asyncio
async def test_touch_during_playback_cancels_owned_turn_and_firmware_speech() -> None:
    coordinator = TurnCoordinator()
    sender = RecordingCommandSender()
    metrics = BridgeMetrics()
    handler = TurnEventHandler(coordinator, sender, metrics=metrics)
    turn = await coordinator.begin("sim-001", trigger=TurnTrigger.TOUCH)
    for state in (
        TurnState.TRANSCRIBING,
        TurnState.WAITING_HERMES,
        TurnState.SYNTHESIZING,
        TurnState.PLAYING,
    ):
        await coordinator.transition(turn.turn_id, state)

    event = touch_tap()
    await handler.handle("sim-001", event)
    await asyncio.sleep(0)

    assert coordinator.current("sim-001") is None
    assert sender.calls == [("sim-001", "speech.cancel", {}, turn.turn_id)]
    assert handler.last_touch("sim-001") is event.payload
    assert b"touch_events_total 1.0" in generate_latest(metrics.registry)


@pytest.mark.asyncio
async def test_touch_does_not_block_the_receiver_while_command_result_is_pending() -> None:
    coordinator = TurnCoordinator()
    sender = BlockingCommandSender()
    handler = TurnEventHandler(coordinator, sender)
    turn = await coordinator.begin("sim-001", trigger=TurnTrigger.TOUCH)
    await coordinator.transition(turn.turn_id, TurnState.TRANSCRIBING)

    await asyncio.wait_for(handler.handle("sim-001", touch_tap()), timeout=0.05)
    await asyncio.wait_for(sender.started.wait(), timeout=0.05)

    assert coordinator.current("sim-001") is None
    assert sender.calls == [("sim-001", "speech.cancel", {}, turn.turn_id)]
    sender.release.set()
    await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_idle_touch_is_observed_without_sending_a_command() -> None:
    coordinator = TurnCoordinator()
    sender = RecordingCommandSender()
    metrics = BridgeMetrics()
    handler = TurnEventHandler(coordinator, sender, metrics=metrics)

    event = touch_tap()
    await handler.handle("sim-001", event)

    assert handler.last_touch("sim-001") is event.payload
    assert sender.calls == []
    assert b"touch_events_total 1.0" in generate_latest(metrics.registry)


@pytest.mark.asyncio
async def test_failed_camera_completion_is_routed_to_its_capture_waiter() -> None:
    coordinator = TurnCoordinator()
    sender = RecordingCommandSender()
    reporter = RecordingCaptureFailureReporter()
    handler = TurnEventHandler(coordinator, sender, capture_failures=reporter)

    await handler.handle("sim-001", camera_completed(ok=False))

    assert reporter.calls == [("sim-001", UUID("4936d914-cef8-443e-830a-d3c717ccc178"))]


@pytest.mark.asyncio
async def test_successful_camera_completion_does_not_fail_the_upload_waiter() -> None:
    coordinator = TurnCoordinator()
    sender = RecordingCommandSender()
    reporter = RecordingCaptureFailureReporter()
    handler = TurnEventHandler(coordinator, sender, capture_failures=reporter)

    await handler.handle("sim-001", camera_completed(ok=True))

    assert reporter.calls == []


def playback_decode_error(**routing: object) -> EventMessage:
    return EventMessage.model_validate(
        {
            "v": 1,
            "type": "event",
            "message_id": str(uuid4()),
            "device_id": "sim-001",
            "sent_at_ms": 1,
            **routing,
            "payload": {
                "name": "device.error",
                "data": {
                    "code": "AUDIO_DECODE_ERROR",
                    "message": "Audio playback could not be decoded",
                },
            },
        }
    )


@pytest.mark.asyncio
async def test_playback_decode_error_stops_output_without_disconnect_or_speech_command() -> None:
    coordinator = TurnCoordinator()
    sender = RecordingCommandSender()
    handler = TurnEventHandler(coordinator, sender)
    turn = await coordinator.begin("sim-001", trigger=TurnTrigger.TOUCH)
    for state in (
        TurnState.TRANSCRIBING,
        TurnState.WAITING_HERMES,
        TurnState.SYNTHESIZING,
        TurnState.PLAYING,
    ):
        await coordinator.transition(turn.turn_id, state)
    registry = DeviceRegistry(command_timeout_seconds=1)
    websocket = RecordingOutputWebSocket()
    connection = DeviceConnection(
        connection_id=uuid4(),
        device_id="sim-001",
        hello=simulator_hello(),
        websocket=cast(WebSocket, websocket),
    )
    await registry.register(connection)
    frame_sent = asyncio.Event()

    async def pause_after_frame(seconds: float) -> None:
        frame_sent.set()
        await asyncio.Event().wait()

    player = AudioOutputStreamer(registry, sleeper=pause_after_frame)
    task = asyncio.create_task(
        player.play(
            "sim-001",
            turn_id=turn.turn_id,
            audio=PcmAudio(pcm=b"\0" * 32_000),
        )
    )
    coordinator.attach_task(turn.turn_id, task)
    try:
        await asyncio.wait_for(frame_sent.wait(), timeout=1)
        await handler.handle("sim-001", playback_decode_error())
        assert task.cancelled()
        assert coordinator.current("sim-001") is None
        assert turn.failure_reason == "AUDIO_DECODE_ERROR"
        assert sum(kind == "bytes" for kind, _ in websocket.frames) == 1
        end = json.loads(websocket.frames[-1][1])
        assert end["type"] == "audio.output.end"
        assert end["payload"]["reason"] == "cancelled"
        assert registry.get_connection("sim-001") is connection
        assert sender.calls == []
        assert await coordinator.begin("sim-001", trigger=TurnTrigger.TOUCH)
    finally:
        await coordinator.cancel_device("sim-001", reason="TEST_CLEANUP")


@pytest.mark.asyncio
@pytest.mark.parametrize("unrelated", ["capturing", "other_device", "other_turn"])
async def test_playback_decode_error_does_not_cancel_unrelated_work(unrelated: str) -> None:
    coordinator = TurnCoordinator()
    handler = TurnEventHandler(coordinator, RecordingCommandSender())
    turn = await coordinator.begin("sim-001", trigger=TurnTrigger.TOUCH)
    if unrelated != "capturing":
        for state in (
            TurnState.TRANSCRIBING,
            TurnState.WAITING_HERMES,
            TurnState.SYNTHESIZING,
            TurnState.PLAYING,
        ):
            await coordinator.transition(turn.turn_id, state)
    event = playback_decode_error(
        **({"turn_id": str(uuid4())} if unrelated == "other_turn" else {})
    )
    await handler.handle("sim-002" if unrelated == "other_device" else "sim-001", event)
    assert coordinator.current("sim-001") is turn
    assert not turn.cancellation.is_set()
