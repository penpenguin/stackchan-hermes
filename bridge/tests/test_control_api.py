from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import cast
from uuid import UUID

import httpx
import pytest
from fastapi import WebSocket
from stackchan_bridge.audio.input import VoiceAudioInputHandler
from stackchan_bridge.audio.vad import RmsVadConfig
from stackchan_bridge.captures.coordinator import (
    CaptureCommandFailedError,
    CaptureCoordinator,
    CaptureTimedOutError,
)
from stackchan_bridge.captures.store import CaptureStore
from stackchan_bridge.config import load_settings
from stackchan_bridge.control.application import create_control_app
from stackchan_bridge.device_gateway.application import (
    CommandQueueFullError,
    CommandTimedOutError,
    DeviceConnection,
    DeviceDisconnectedError,
    DeviceNotConnectedError,
    DeviceRegistry,
)
from stackchan_bridge.hermes.errors import HermesError
from stackchan_bridge.observability.metrics import BridgeMetrics
from stackchan_bridge.protocol.models import (
    AudioInputEndMessage,
    CommandMessage,
    CommandResultMessage,
    EventMessage,
    EventPayload,
    HelloMessage,
)
from stackchan_bridge.runtime import build_runtime
from stackchan_bridge.tts.errors import TtsError
from stackchan_bridge.turns.coordinator import (
    StaleTurnError,
    Turn,
    TurnBusyError,
    TurnCoordinator,
    TurnState,
    TurnTrigger,
)
from stackchan_bridge.turns.service import VoiceTurnError, VoiceTurnService
from stackchan_simulator.fixtures import generate_synthetic_jpeg

from .test_audio_input import FailingTurnService, input_start


class LoopbackCommandWebSocket:
    def __init__(self, registry: DeviceRegistry, connection_id: UUID) -> None:
        self.registry = registry
        self.connection_id = connection_id
        self.commands: list[CommandMessage] = []

    async def send_text(self, data: str) -> None:
        command = CommandMessage.model_validate(json.loads(data))
        self.commands.append(command)
        args = command.payload.args.model_dump(exclude_none=True)
        result = CommandResultMessage.model_validate(
            {
                "v": 1,
                "type": "command_result",
                "message_id": "2d93497d-b2f5-453c-923a-bbd19aa93dcc",
                "request_id": command.request_id,
                "sent_at_ms": 1,
                "payload": {"ok": True, "result": args},
            }
        )
        self.registry.route_result("sim-001", self.connection_id, result)


class SilentWebSocket:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send_text(self, data: str) -> None:
        self.sent.append(data)


class UploadingCaptureWebSocket:
    def __init__(
        self,
        registry: DeviceRegistry,
        connection_id: UUID,
        store: CaptureStore,
    ) -> None:
        self.registry = registry
        self.connection_id = connection_id
        self.store = store
        self.command: CommandMessage | None = None

    async def send_text(self, data: str) -> None:
        command = CommandMessage.model_validate(json.loads(data))
        self.command = command
        args = command.payload.args.model_dump()
        self.store.save(
            UUID(str(args["capture_id"])),
            device_id="sim-001",
            content_type="image/jpeg",
            body=generate_synthetic_jpeg(),
        )
        result = CommandResultMessage.model_validate(
            {
                "v": 1,
                "type": "command_result",
                "message_id": "2d93497d-b2f5-453c-923a-bbd19aa93dcc",
                "request_id": command.request_id,
                "sent_at_ms": 1,
                "payload": {"ok": True, "result": {}},
            }
        )
        self.registry.route_result("sim-001", self.connection_id, result)


class CompletedVisionService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, int]] = []

    async def run(self, device_id: str, *, question: str, quality: int = 80) -> Turn:
        self.calls.append((device_id, question, quality))
        return Turn(
            turn_id=UUID("a74e6e0a-dc71-4828-a274-a9b6b21682d4"),
            device_id=device_id,
            started_at=1,
            trigger=TurnTrigger.CONTROL_API,
            state=TurnState.COMPLETED,
            capture_id=UUID("3d27c065-15a7-4f85-87ba-df14912a8098"),
            hermes_response_id="resp_vision_control_1",
            output_stream_ids=[UUID("f567a137-bc86-43d7-acb0-7196500a2a3b")],
        )


class BusyVisionService:
    async def run(self, device_id: str, *, question: str, quality: int = 80) -> Turn:
        raise TurnBusyError(f"private busy detail for {device_id}: {question}: {quality}")


class DisconnectedVisionService:
    async def run(self, device_id: str, *, question: str, quality: int = 80) -> Turn:
        raise DeviceNotConnectedError(f"private connection detail for {device_id}")


class FailingVisionService:
    def __init__(self, error: Exception) -> None:
        self.error = error

    async def run(self, device_id: str, *, question: str, quality: int = 80) -> Turn:
        raise self.error


class RecordingConversationResetter:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def reset_conversation(self, device_id: str) -> str:
        self.calls.append(device_id)
        return f"stackchan:{device_id}:reset-1"


class RecordingTouchState:
    def last_touch(self, device_id: str) -> EventPayload | None:
        assert device_id == "sim-001"
        return EventMessage.model_validate(
            {
                "v": 1,
                "type": "event",
                "message_id": "669f5c66-9582-413b-bb2d-a94315a3a8a8",
                "device_id": device_id,
                "sent_at_ms": 10,
                "payload": {"name": "touch.tap", "data": {"x": 120, "y": 80}},
            }
        ).payload


def simulator_hello() -> HelloMessage:
    return HelloMessage.model_validate(
        {
            "v": 1,
            "type": "hello",
            "message_id": "d5dd9e57-e4f7-4f07-9dc4-b939d0b6a947",
            "sent_at_ms": 0,
            "payload": {
                "device_id": "sim-001",
                "device_name": "StackChan Simulator",
                "firmware_version": "0.1.0",
                "hardware_model": "SIMULATOR",
                "protocol_versions": [1],
                "capabilities": {
                    "microphone": True,
                    "speaker": True,
                    "camera": True,
                    "touch": True,
                    "head": True,
                    "display": True,
                    "avatar": True,
                    "led_count": 12,
                },
                "audio": {
                    "codec": "opus",
                    "sample_rate": 16_000,
                    "channels": 1,
                    "frame_ms": 60,
                },
            },
        }
    )


@pytest.mark.asyncio
async def test_control_api_lists_only_safe_live_device_metadata() -> None:
    registry = DeviceRegistry(command_timeout_seconds=5)
    app = create_control_app(registry)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://control") as client:
        empty = await client.get("/v1/control/devices")
        await registry.register(
            DeviceConnection(
                connection_id=UUID("79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc"),
                device_id="sim-001",
                hello=simulator_hello(),
                websocket=cast(WebSocket, object()),
            )
        )
        connected = await client.get("/v1/control/devices")
        detail = await client.get("/v1/control/devices/sim-001")
        missing = await client.get("/v1/control/devices/not-connected")

    assert empty.json() == {"devices": []}
    assert connected.json() == {
        "devices": [
            {
                "device_id": "sim-001",
                "connected": True,
                "device_name": "StackChan Simulator",
                "firmware_version": "0.1.0",
                "hardware_model": "SIMULATOR",
                "protocol_version": 1,
                "capabilities": {
                    "microphone": True,
                    "speaker": True,
                    "camera": True,
                    "touch": True,
                    "head": True,
                    "display": True,
                    "avatar": True,
                    "led_count": 12,
                },
            }
        ]
    }
    assert detail.json()["device_id"] == "sim-001"
    assert detail.json()["capabilities"]["camera"] is True
    assert missing.status_code == 404
    assert missing.json() == {
        "error": {
            "code": "DEVICE_NOT_CONNECTED",
            "message": "device is not connected: not-connected",
        }
    }
    assert "token" not in connected.text.lower()


@pytest.mark.asyncio
async def test_control_api_exposes_the_most_recent_physical_touch() -> None:
    registry = DeviceRegistry(command_timeout_seconds=5)
    await registry.register(
        DeviceConnection(
            connection_id=UUID("79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc"),
            device_id="sim-001",
            hello=simulator_hello(),
            websocket=cast(WebSocket, object()),
        )
    )
    app = create_control_app(registry, touch_state=RecordingTouchState())
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://control") as client:
        response = await client.get("/v1/control/devices/sim-001/touch")

    assert response.status_code == 200
    assert response.json() == {"touch": {"name": "touch.tap", "data": {"x": 120, "y": 80}}}


@pytest.mark.asyncio
async def test_control_api_sends_a_typed_command_and_maps_disconnected_error() -> None:
    registry = DeviceRegistry(command_timeout_seconds=5)
    connection_id = UUID("79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc")
    websocket = LoopbackCommandWebSocket(registry, connection_id)
    await registry.register(
        DeviceConnection(
            connection_id=connection_id,
            device_id="sim-001",
            hello=simulator_hello(),
            websocket=cast(WebSocket, websocket),
        )
    )
    app = create_control_app(registry)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://control") as client:
        response = await client.post(
            "/v1/control/devices/sim-001/commands",
            json={
                "name": "head.set_angles",
                "args": {"yaw": 15, "pitch": 40, "speed": 30},
            },
        )
        missing = await client.post(
            "/v1/control/devices/not-connected/commands",
            json={"name": "head.home", "args": {}},
        )

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["result"] == {"yaw": 15, "pitch": 40, "speed": 30}
    assert websocket.commands[0].payload.name == "head.set_angles"
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "DEVICE_NOT_CONNECTED"


@pytest.mark.asyncio
@pytest.mark.parametrize("route", ["commands", "captures", "vision"])
async def test_control_api_reports_command_queue_overload_and_recovers(
    tmp_path: Path,
    route: str,
) -> None:
    environment = {
        "STACKCHAN_DEVICE_TOKEN": "overload-device-token",  # pragma: allowlist secret
        "HERMES_API_KEY": "overload-hermes-key",  # pragma: allowlist secret
    }
    settings = load_settings(
        Path(__file__).resolve().parents[2] / "config.example.toml",
        environment=environment,
        cli_overrides={"captures": {"directory": str(tmp_path)}, "mdns": {"enabled": False}},
    )
    runtime = build_runtime(settings, environment=environment)
    connection_id = UUID("79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc")

    class HoldingCommandWebSocket(LoopbackCommandWebSocket):
        hold = True

        async def send_text(self, data: str) -> None:
            if self.hold:
                self.commands.append(CommandMessage.model_validate_json(data))
            else:
                await super().send_text(data)

    websocket = HoldingCommandWebSocket(runtime.registry, connection_id)
    connection = DeviceConnection(
        connection_id=connection_id,
        device_id="sim-001",
        hello=simulator_hello(),
        websocket=cast(WebSocket, websocket),
    )
    await runtime.registry.register(connection)
    pending = [
        asyncio.create_task(runtime.registry.send_command("sim-001", "device.get_status", {}))
        for _ in range(16)
    ]
    try:
        await asyncio.sleep(0)
        assert len(connection.pending_commands) == 16
        payload = {
            "commands": {"name": "device.get_status", "args": {}},
            "captures": {"quality": 80},
            "vision": {"question": "何が見えますか"},
        }[route]
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=runtime.control, raise_app_exceptions=False),
            base_url="http://control",
        ) as client:
            overloaded = await client.post(f"/v1/control/devices/sim-001/{route}", json=payload)
            assert overloaded.status_code == 429
            assert overloaded.json()["error"]["code"] == "COMMAND_QUEUE_FULL"
            assert len(connection.pending_commands) == 16
            assert len(websocket.commands) == 16
            assert runtime.turn_coordinator.current("sim-001") is None
            assert runtime.capture_store._reservations == {}
            with pytest.raises(CommandQueueFullError):
                await runtime.registry.send_command("sim-001", "device.get_status", {})

            pending[0].cancel()
            await asyncio.gather(pending[0], return_exceptions=True)
            websocket.hold = False
            recovered = await client.post(
                "/v1/control/devices/sim-001/commands",
                json={"name": "device.get_status", "args": {}},
            )
            assert recovered.status_code == 200
            assert recovered.json()["ok"] is True
            assert len(connection.pending_commands) == 15
    finally:
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        await runtime.aclose()
    assert connection.pending_commands == {}


@pytest.mark.asyncio
async def test_control_api_maps_k151_motion_safety_rejection_without_sending() -> None:
    registry = DeviceRegistry(command_timeout_seconds=5)
    connection_id = UUID("79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc")
    websocket = LoopbackCommandWebSocket(registry, connection_id)
    hello_data = simulator_hello().model_dump(mode="json")
    hello_data["payload"]["hardware_model"] = "M5STACK-K151"
    await registry.register(
        DeviceConnection(
            connection_id=connection_id,
            device_id="sim-001",
            hello=HelloMessage.model_validate(hello_data),
            websocket=cast(WebSocket, websocket),
        )
    )
    app = create_control_app(registry)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://control") as client:
        response = await client.post(
            "/v1/control/devices/sim-001/commands",
            json={
                "name": "head.set_angles",
                "args": {"yaw": 46, "pitch": 45, "speed": 15},
            },
        )

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "INVALID_ARGUMENT",
            "message": "command exceeds the device motion safety profile",
        }
    }
    assert websocket.commands == []


@pytest.mark.asyncio
async def test_control_api_maps_invalid_arguments_and_command_timeout_without_reflection() -> None:
    registry = DeviceRegistry(command_timeout_seconds=0.001)
    websocket = SilentWebSocket()
    await registry.register(
        DeviceConnection(
            connection_id=UUID("79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc"),
            device_id="sim-001",
            hello=simulator_hello(),
            websocket=cast(WebSocket, websocket),
        )
    )
    app = create_control_app(registry)
    transport = httpx.ASGITransport(app=app)
    private_marker = "private-marker-" * 30
    async with httpx.AsyncClient(transport=transport, base_url="http://control") as client:
        invalid = await client.post(
            "/v1/control/devices/sim-001/commands",
            json={
                "name": "display.show_text",
                "args": {"text": private_marker, "duration_ms": 1_000, "priority": 1},
            },
        )
        timed_out = await client.post(
            "/v1/control/devices/sim-001/commands",
            json={"name": "head.home", "args": {}},
        )

    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "INVALID_ARGUMENT"
    assert "private-marker" not in invalid.text
    assert timed_out.status_code == 504
    assert timed_out.json()["error"]["code"] == "COMMAND_TIMEOUT"
    assert len(websocket.sent) == 1


@pytest.mark.asyncio
async def test_control_api_cancel_speech_sends_turn_owned_command() -> None:
    registry = DeviceRegistry(command_timeout_seconds=5)
    connection_id = UUID("79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc")
    websocket = LoopbackCommandWebSocket(registry, connection_id)
    await registry.register(
        DeviceConnection(
            connection_id=connection_id,
            device_id="sim-001",
            hello=simulator_hello(),
            websocket=cast(WebSocket, websocket),
        )
    )
    app = create_control_app(registry)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://control") as client:
        response = await client.post(
            "/v1/control/devices/sim-001/speech/cancel",
            json={"turn_id": "0819e40d-71f3-4d44-9a31-928358122a83"},
        )

    assert response.status_code == 200
    assert websocket.commands[0].payload.name == "speech.cancel"
    assert websocket.commands[0].turn_id == UUID("0819e40d-71f3-4d44-9a31-928358122a83")


@pytest.mark.asyncio
async def test_control_api_cancel_speech_stops_the_owned_local_turn() -> None:
    registry = DeviceRegistry(command_timeout_seconds=5)
    connection_id = UUID("79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc")
    websocket = LoopbackCommandWebSocket(registry, connection_id)
    await registry.register(
        DeviceConnection(
            connection_id=connection_id,
            device_id="sim-001",
            hello=simulator_hello(),
            websocket=cast(WebSocket, websocket),
        )
    )
    coordinator = TurnCoordinator()
    turn_id = UUID("0819e40d-71f3-4d44-9a31-928358122a83")
    await coordinator.begin("sim-001", trigger=TurnTrigger.CONTROL_API, turn_id=turn_id)
    await coordinator.transition(turn_id, TurnState.TRANSCRIBING)
    app = create_control_app(registry, turn_coordinator=coordinator)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://control") as client:
        response = await client.post(
            "/v1/control/devices/sim-001/speech/cancel",
            json={"turn_id": str(turn_id)},
        )

    assert response.status_code == 200
    assert coordinator.current("sim-001") is None
    assert websocket.commands[0].payload.name == "speech.cancel"
    assert websocket.commands[0].turn_id == turn_id


@pytest.mark.asyncio
@pytest.mark.parametrize("target_active_turn", [True, False])
async def test_control_api_rejects_cancellation_while_audio_input_is_capturing(
    target_active_turn: bool,
) -> None:
    registry = DeviceRegistry(command_timeout_seconds=0.01)
    connection_id = UUID("79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc")
    websocket = LoopbackCommandWebSocket(registry, connection_id)
    await registry.register(
        DeviceConnection(
            connection_id=connection_id,
            device_id="sim-001",
            hello=simulator_hello(),
            websocket=cast(WebSocket, websocket),
        )
    )
    coordinator = TurnCoordinator()
    handler = VoiceAudioInputHandler(
        coordinator,
        cast(VoiceTurnService, FailingTurnService()),
        max_recording_ms=15_000,
        vad_config=RmsVadConfig(),
    )
    start = input_start()
    await handler.start("sim-001", start)
    turn = coordinator.current("sim-001")
    assert turn is not None
    app = create_control_app(registry, turn_coordinator=coordinator)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://control"
        ) as client:
            response = await client.post(
                "/v1/control/devices/sim-001/speech/cancel",
                json={
                    "turn_id": str(start.turn_id)
                    if target_active_turn
                    else "0819e40d-71f3-4d44-9a31-928358122a83"
                },
            )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == (
            "TURN_CAPTURING" if target_active_turn else "TURN_NOT_ACTIVE"
        )
        assert coordinator.current("sim-001") is turn
        assert turn.state is TurnState.CAPTURING
        assert not turn.cancellation.is_set()
        assert not websocket.commands
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
        assert turn.failure_reason == "NO_SPEECH"
        assert coordinator.current("sim-001") is None
        await handler.start("sim-001", start)
        assert coordinator.current("sim-001") is not None
    finally:
        await handler.disconnect("sim-001", start)


@pytest.mark.asyncio
async def test_control_api_starts_an_explicit_vision_turn() -> None:
    registry = DeviceRegistry(command_timeout_seconds=5)
    vision = CompletedVisionService()
    app = create_control_app(registry, vision_turn_service=vision)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://control") as client:
        response = await client.post(
            "/v1/control/devices/sim-001/vision",
            json={"question": "何が見えますか", "quality": 75},
        )

    assert response.status_code == 200
    assert response.json() == {
        "turn_id": "a74e6e0a-dc71-4828-a274-a9b6b21682d4",
        "state": "COMPLETED",
        "capture_id": "3d27c065-15a7-4f85-87ba-df14912a8098",
        "hermes_response_id": "resp_vision_control_1",
        "output_stream_ids": ["f567a137-bc86-43d7-acb0-7196500a2a3b"],
    }
    assert vision.calls == [("sim-001", "何が見えますか", 75)]


@pytest.mark.asyncio
async def test_control_api_reports_a_busy_vision_turn_without_internal_details() -> None:
    app = create_control_app(
        DeviceRegistry(command_timeout_seconds=5),
        vision_turn_service=BusyVisionService(),
    )
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://control") as client:
        response = await client.post(
            "/v1/control/devices/sim-001/vision",
            json={"question": "何が見えますか"},
        )

    assert response.status_code == 409
    assert response.json() == {
        "error": {"code": "TURN_BUSY", "message": "device already has an active turn"}
    }
    assert "private busy detail" not in response.text


@pytest.mark.asyncio
async def test_control_api_reports_a_disconnected_vision_device() -> None:
    app = create_control_app(
        DeviceRegistry(command_timeout_seconds=5),
        vision_turn_service=DisconnectedVisionService(),
    )
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://control") as client:
        response = await client.post(
            "/v1/control/devices/sim-001/vision",
            json={"question": "何が見えますか"},
        )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "DEVICE_NOT_CONNECTED"
    assert "private connection detail" not in response.text


@pytest.mark.asyncio
async def test_control_api_rejects_a_blank_vision_question_before_capture() -> None:
    vision = CompletedVisionService()
    app = create_control_app(
        DeviceRegistry(command_timeout_seconds=5),
        vision_turn_service=vision,
    )
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://control") as client:
        response = await client.post(
            "/v1/control/devices/sim-001/vision",
            json={"question": "   "},
        )

    assert response.status_code == 422
    assert vision.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "status_code", "code"),
    [
        (CommandQueueFullError("private-marker"), 429, "COMMAND_QUEUE_FULL"),
        (DeviceDisconnectedError("private-marker"), 409, "CAPTURE_FAILED"),
        (CaptureCommandFailedError("private-marker"), 409, "CAPTURE_FAILED"),
        (CommandTimedOutError("private-marker"), 504, "COMMAND_TIMEOUT"),
        (CaptureTimedOutError("private-marker"), 504, "CAPTURE_TIMEOUT"),
        (HermesError("private-marker"), 502, "HERMES_FAILED"),
        (TtsError("private-marker"), 502, "TTS_FAILED"),
        (VoiceTurnError("EMPTY_RESPONSE", "private-marker"), 502, "VISION_RESPONSE_FAILED"),
        (StaleTurnError("private-marker"), 409, "TURN_CANCELLED"),
    ],
)
async def test_control_api_maps_known_vision_failures_without_internal_details(
    error: Exception,
    status_code: int,
    code: str,
) -> None:
    app = create_control_app(
        DeviceRegistry(command_timeout_seconds=5),
        vision_turn_service=FailingVisionService(error),
    )
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://control") as client:
        response = await client.post(
            "/v1/control/devices/sim-001/vision",
            json={"question": "何が見えますか"},
        )

    assert response.status_code == status_code
    assert response.json()["error"]["code"] == code
    assert "private-marker" not in response.text


@pytest.mark.asyncio
async def test_control_api_resets_only_the_conversation_scope() -> None:
    resetter = RecordingConversationResetter()
    app = create_control_app(
        DeviceRegistry(command_timeout_seconds=5),
        conversation_resetter=resetter,
    )
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://control") as client:
        response = await client.post(
            "/v1/control/devices/sim-001/conversation/reset",
        )

    assert response.status_code == 200
    assert response.json() == {"conversation": "stackchan:sim-001:reset-1"}
    assert resetter.calls == ["sim-001"]


@pytest.mark.asyncio
async def test_control_api_reports_an_unadvertised_device_capability() -> None:
    registry = DeviceRegistry(command_timeout_seconds=5)
    hello_data = simulator_hello().model_dump(mode="json")
    hello_data["payload"]["capabilities"]["camera"] = False
    connection_id = UUID("79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc")
    websocket = LoopbackCommandWebSocket(registry, connection_id)
    await registry.register(
        DeviceConnection(
            connection_id=connection_id,
            device_id="sim-001",
            hello=HelloMessage.model_validate(hello_data),
            websocket=cast(WebSocket, websocket),
        )
    )
    app = create_control_app(registry)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://control") as client:
        response = await client.post(
            "/v1/control/devices/sim-001/commands",
            json={"name": "camera.capture", "args": {"quality": 80}},
        )

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "CAPABILITY_UNAVAILABLE",
            "message": "device capability is unavailable: camera",
        }
    }
    assert websocket.commands == []


@pytest.mark.asyncio
async def test_health_distinguishes_liveness_from_dependency_readiness() -> None:
    registry = DeviceRegistry(command_timeout_seconds=5)

    async def ready() -> bool:
        return True

    async def unavailable() -> bool:
        return False

    app = create_control_app(
        registry,
        readiness_checks={"config": ready, "capture_store": ready, "hermes": unavailable},
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://control") as client:
        live = await client.get("/health/live")
        not_ready = await client.get("/health/ready")

    assert live.status_code == 200
    assert live.json() == {"status": "live"}
    assert not_ready.status_code == 503
    assert not_ready.json() == {
        "ready": False,
        "connected_devices": 0,
        "checks": {"capture_store": True, "config": True, "hermes": False},
    }


@pytest.mark.asyncio
async def test_metrics_endpoint_exposes_required_names_and_live_device_count() -> None:
    metrics = BridgeMetrics()
    registry = DeviceRegistry(command_timeout_seconds=5, metrics=metrics)
    app = create_control_app(registry, metrics=metrics)
    await registry.register(
        DeviceConnection(
            connection_id=UUID("79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc"),
            device_id="sim-001",
            hello=simulator_hello(),
            websocket=cast(WebSocket, object()),
        )
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://control") as client:
        response = await client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "connected_devices 1.0" in response.text
    for metric_name in (
        "websocket_connect_total",
        "websocket_disconnect_total",
        "websocket_auth_failure_total",
        "active_turns",
        "touch_events_total",
        "audio_input_frames_total",
        "audio_output_frames_total",
        "audio_decode_error_total",
        "audio_underrun_total",
        "audio_overflow_total",
        "stt_duration_seconds",
        "hermes_time_to_first_delta_seconds",
        "hermes_total_duration_seconds",
        "tts_duration_seconds",
        "time_to_first_audio_seconds",
        "turn_total_duration_seconds",
        "capture_total",
        "capture_failure_total",
        "command_timeout_total",
    ):
        assert metric_name in response.text


@pytest.mark.asyncio
async def test_control_api_reads_and_deletes_a_capture_resource(tmp_path: Path) -> None:
    store = CaptureStore(directory=tmp_path, ttl_seconds=600, max_bytes=2_097_152)
    reservation = store.reserve("sim-001")
    jpeg = generate_synthetic_jpeg()
    record = store.save(
        reservation.capture_id,
        device_id="sim-001",
        content_type="image/jpeg",
        body=jpeg,
    )
    registry = DeviceRegistry(command_timeout_seconds=5)
    app = create_control_app(registry, capture_store=store)
    transport = httpx.ASGITransport(app=app)
    url = f"/v1/control/captures/{record.capture_id}"
    async with httpx.AsyncClient(transport=transport, base_url="http://control") as client:
        fetched = await client.get(url)
        deleted = await client.delete(url)
        missing = await client.get(url)

    assert fetched.status_code == 200
    assert fetched.headers["content-type"] == "image/jpeg"
    assert fetched.headers["cache-control"] == "no-store"
    assert fetched.content == jpeg
    assert deleted.status_code == 204
    assert deleted.content == b""
    assert not record.path.exists()
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "CAPTURE_NOT_FOUND"


@pytest.mark.asyncio
async def test_control_api_initiates_an_owned_camera_capture(tmp_path: Path) -> None:
    store = CaptureStore(directory=tmp_path, ttl_seconds=600, max_bytes=2_097_152)
    registry = DeviceRegistry(command_timeout_seconds=5)
    connection_id = UUID("79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc")
    websocket = UploadingCaptureWebSocket(registry, connection_id, store)
    await registry.register(
        DeviceConnection(
            connection_id=connection_id,
            device_id="sim-001",
            hello=simulator_hello(),
            websocket=cast(WebSocket, websocket),
        )
    )
    capture_coordinator = CaptureCoordinator(registry, store, timeout_seconds=1)
    app = create_control_app(
        registry,
        capture_store=store,
        capture_coordinator=capture_coordinator,
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://control") as client:
        response = await client.post(
            "/v1/control/devices/sim-001/captures",
            json={"quality": 75},
        )

    assert response.status_code == 201
    payload = response.json()
    assert payload["mime_type"] == "image/jpeg"
    assert (payload["width"], payload["height"]) == (320, 240)
    assert len(payload["sha256"]) == 64
    assert payload["local_url"] == f"/v1/control/captures/{payload['capture_id']}"
    assert websocket.command is not None
    assert websocket.command.payload.name == "camera.capture"
    assert websocket.command.payload.args.quality == 75
