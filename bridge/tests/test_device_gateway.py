from __future__ import annotations

import json
from asyncio import CancelledError, create_task, sleep
from collections.abc import Callable
from threading import Event as ThreadEvent
from typing import cast
from uuid import UUID, uuid4

import pytest
from fastapi import WebSocket
from fastapi.testclient import TestClient
from prometheus_client import generate_latest
from stackchan_bridge.device_gateway.application import (
    CommandTimedOutError,
    DeviceCapabilityError,
    DeviceConnection,
    DeviceDisconnectedError,
    DeviceGatewayConfig,
    DeviceNotConnectedError,
    DeviceRegistry,
    _AuthenticationGate,
    create_device_gateway_app,
)
from stackchan_bridge.observability.metrics import BridgeMetrics
from stackchan_bridge.protocol.models import (
    AudioInputEndMessage,
    AudioInputStartMessage,
    ErrorMessage,
    EventMessage,
    HelloAckMessage,
    HelloMessage,
    ProtocolErrorCode,
)
from stackchan_bridge.security.tokens import hash_device_token
from stackchan_bridge.turns.coordinator import Turn, TurnCoordinator, TurnState, TurnTrigger
from starlette.websockets import WebSocketDisconnect


def hello_message(device_id: str = "sim-001") -> HelloMessage:
    return HelloMessage.model_validate(
        {
            "v": 1,
            "type": "hello",
            "message_id": "d5dd9e57-e4f7-4f07-9dc4-b939d0b6a947",
            "sent_at_ms": 0,
            "payload": {
                "device_id": device_id,
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


class RecordingCommandWebSocket:
    def __init__(self) -> None:
        self.frames: list[str] = []

    async def send_text(self, data: str) -> None:
        self.frames.append(data)


class CloseFailingWebSocket(RecordingCommandWebSocket):
    async def close(self, *, code: int, reason: str) -> None:
        raise RuntimeError(f"socket already closed: {code} {reason}")


class SendFailingCommandWebSocket(RecordingCommandWebSocket):
    async def send_text(self, data: str) -> None:
        self.frames.append(data)
        raise RuntimeError("peer disconnected while sending")


@pytest.mark.asyncio
async def test_registry_keeps_the_replacement_when_the_old_socket_is_already_closed() -> None:
    registry = DeviceRegistry(command_timeout_seconds=0.01)
    previous = DeviceConnection(
        connection_id=UUID("79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc"),
        device_id="sim-001",
        hello=hello_message(),
        websocket=cast(WebSocket, CloseFailingWebSocket()),
    )
    replacement = DeviceConnection(
        connection_id=UUID("89e1d2f4-e7d9-4c44-b560-af9ed6b0cacc"),
        device_id="sim-001",
        hello=hello_message(),
        websocket=cast(WebSocket, RecordingCommandWebSocket()),
    )
    await registry.register(previous)

    await registry.register(replacement)

    assert registry.get_connection("sim-001") is replacement


@pytest.mark.asyncio
async def test_registry_omits_absent_optional_envelope_fields_from_command_wire_json() -> None:
    websocket = RecordingCommandWebSocket()
    registry = DeviceRegistry(command_timeout_seconds=0.01)
    await registry.register(
        DeviceConnection(
            connection_id=UUID("79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc"),
            device_id="sim-001",
            hello=hello_message(),
            websocket=cast(WebSocket, websocket),
        )
    )

    with pytest.raises(CommandTimedOutError):
        await registry.send_command("sim-001", "device.get_status", {})

    frame = json.loads(websocket.frames[0])
    assert "turn_id" not in frame
    assert "stream_id" not in frame
    assert "device_id" not in frame


@pytest.mark.asyncio
async def test_registry_maps_command_send_failure_to_device_disconnected() -> None:
    websocket = SendFailingCommandWebSocket()
    registry = DeviceRegistry(command_timeout_seconds=0.01)
    connection = DeviceConnection(
        connection_id=UUID("79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc"),
        device_id="sim-001",
        hello=hello_message(),
        websocket=cast(WebSocket, websocket),
    )
    await registry.register(connection)

    with pytest.raises(DeviceDisconnectedError):
        await registry.send_command("sim-001", "device.get_status", {})

    assert len(websocket.frames) == 1
    assert connection.pending_commands == {}


def test_gateway_duplicate_message_cache_has_the_protocol_v1_bound() -> None:
    assert DeviceGatewayConfig().max_seen_message_ids == 256


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("advertised_field", "unavailable_value", "command_name", "expected_capability"),
    [
        ("camera", False, "camera.capture", "camera"),
        ("head", False, "head.home", "head"),
        ("avatar", False, "avatar.set_expression", "avatar"),
        ("display", False, "display.show_text", "display"),
        ("speaker", False, "audio.set_volume", "speaker"),
        ("led_count", 0, "led.clear", "led"),
    ],
)
async def test_registry_rejects_a_command_for_an_unadvertised_capability(
    advertised_field: str,
    unavailable_value: bool | int,
    command_name: str,
    expected_capability: str,
) -> None:
    hello_data = hello_message().model_dump(mode="json")
    hello_data["payload"]["capabilities"][advertised_field] = unavailable_value
    websocket = RecordingCommandWebSocket()
    registry = DeviceRegistry(command_timeout_seconds=0.01)
    await registry.register(
        DeviceConnection(
            connection_id=UUID("79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc"),
            device_id="sim-001",
            hello=HelloMessage.model_validate(hello_data),
            websocket=cast(WebSocket, websocket),
        )
    )

    with pytest.raises(DeviceCapabilityError) as error:
        await registry.send_command("sim-001", command_name, {})

    assert error.value.capability == expected_capability
    assert websocket.frames == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("command_name", "args"),
    [
        ("head.set_angles", {"yaw": -45.1, "pitch": 45, "speed": 15}),
        ("head.set_angles", {"yaw": 45.1, "pitch": 45, "speed": 15}),
        ("head.set_angles", {"yaw": 0, "pitch": 4.9, "speed": 15}),
        ("head.set_angles", {"yaw": 0, "pitch": 85.1, "speed": 15}),
        ("head.set_angles", {"yaw": 0, "pitch": 45, "speed": 31}),
        ("head.home", {"speed": 31}),
    ],
)
async def test_registry_rejects_motion_outside_the_k151_physical_profile(
    command_name: str,
    args: dict[str, float | int],
) -> None:
    hello_data = hello_message().model_dump(mode="json")
    hello_data["payload"]["hardware_model"] = "M5STACK-K151"
    websocket = RecordingCommandWebSocket()
    registry = DeviceRegistry(command_timeout_seconds=0.01)
    await registry.register(
        DeviceConnection(
            connection_id=UUID("79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc"),
            device_id="sim-001",
            hello=HelloMessage.model_validate(hello_data),
            websocket=cast(WebSocket, websocket),
        )
    )

    with pytest.raises(ValueError, match="K151 motion safety profile"):
        await registry.send_command("sim-001", command_name, args)

    assert websocket.frames == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("hardware_model", "command_name", "args"),
    [
        ("M5STACK-K151", "head.set_angles", {"yaw": -45, "pitch": 5, "speed": 1}),
        ("M5STACK-K151", "head.set_angles", {"yaw": 45, "pitch": 85, "speed": 30}),
        ("M5STACK-K151", "head.home", {}),
        ("SIMULATOR", "head.set_angles", {"yaw": 90, "pitch": -90, "speed": 100}),
    ],
)
async def test_registry_forwards_motion_within_the_selected_board_profile(
    hardware_model: str,
    command_name: str,
    args: dict[str, float | int],
) -> None:
    hello_data = hello_message().model_dump(mode="json")
    hello_data["payload"]["hardware_model"] = hardware_model
    websocket = RecordingCommandWebSocket()
    registry = DeviceRegistry(command_timeout_seconds=0.01)
    await registry.register(
        DeviceConnection(
            connection_id=UUID("79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc"),
            device_id="sim-001",
            hello=HelloMessage.model_validate(hello_data),
            websocket=cast(WebSocket, websocket),
        )
    )

    with pytest.raises(CommandTimedOutError):
        await registry.send_command("sim-001", command_name, args)

    assert len(websocket.frames) == 1
    payload = json.loads(websocket.frames[0])["payload"]
    assert payload == {"name": command_name, "args": args}


@pytest.mark.asyncio
async def test_registry_rejects_motion_for_an_unknown_hardware_model() -> None:
    hello_data = hello_message().model_dump(mode="json")
    hello_data["payload"]["hardware_model"] = "M5STACK-K151-TYPO"
    websocket = RecordingCommandWebSocket()
    registry = DeviceRegistry(command_timeout_seconds=0.01)
    await registry.register(
        DeviceConnection(
            connection_id=UUID("79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc"),
            device_id="sim-001",
            hello=HelloMessage.model_validate(hello_data),
            websocket=cast(WebSocket, websocket),
        )
    )

    with pytest.raises(ValueError, match="unsupported hardware motion profile"):
        await registry.send_command(
            "sim-001",
            "head.set_angles",
            {"yaw": 0, "pitch": 45, "speed": 15},
        )

    assert websocket.frames == []


def test_gateway_authenticates_hello_and_tracks_the_live_device() -> None:
    token = "simulator-device-token"  # pragma: allowlist secret
    app = create_device_gateway_app(
        DeviceGatewayConfig(
            device_token_hashes={"sim-001": hash_device_token(token, salt=b"0123456789abcdef")}
        )
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "X-StackChan-Device-Id": "sim-001",
    }

    with TestClient(app) as client:
        with client.websocket_connect("/v1/device/ws", headers=headers) as websocket:
            websocket.send_text(hello_message().model_dump_json())
            acknowledgement = HelloAckMessage.model_validate(websocket.receive_json())

            assert acknowledgement.payload.selected_protocol_version == 1
            assert app.state.device_registry.connected_device_ids() == ("sim-001",)

        assert app.state.device_registry.connected_device_ids() == ()


@pytest.mark.asyncio
@pytest.mark.parametrize("replacing", [False, True])
async def test_gateway_exposes_commands_only_after_hello_ack_is_sent(replacing: bool) -> None:
    token = "simulator-device-token"  # pragma: allowlist secret
    app = create_device_gateway_app(
        DeviceGatewayConfig(
            device_token_hashes={"sim-001": hash_device_token(token, salt=b"0123456789abcdef")},
            command_timeout_ms=100,
        )
    )
    registry = app.state.device_registry

    async def assert_unavailable() -> None:
        with pytest.raises(DeviceNotConnectedError):
            await registry.send_command("sim-001", "device.get_status", {})
        assert registry.get_connection("sim-001") is None
        assert registry.connected_device_ids() == ()
        assert registry.connected_devices() == ()

    class PreviousWebSocket(RecordingCommandWebSocket):
        async def close(self, *, code: int, reason: str) -> None:
            await assert_unavailable()

    class HandshakingWebSocket(RecordingCommandWebSocket):
        def __init__(self) -> None:
            super().__init__()
            self.headers = {
                "Authorization": f"Bearer {token}",
                "X-StackChan-Device-Id": "sim-001",
            }

        async def accept(self) -> None:
            return None

        async def receive_text(self) -> str:
            return hello_message().model_dump_json()

        async def send_text(self, data: str) -> None:
            if json.loads(data)["type"] == "hello_ack":
                await assert_unavailable()
            await super().send_text(data)

        async def receive(self) -> dict[str, str]:
            assert registry.get_connection("sim-001") is not None
            with pytest.raises(CommandTimedOutError):
                await registry.send_command("sim-001", "device.get_status", {})
            return {"type": "websocket.disconnect"}

    if replacing:
        await registry.register(
            DeviceConnection(
                connection_id=UUID("79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc"),
                device_id="sim-001",
                hello=hello_message(),
                websocket=cast(WebSocket, PreviousWebSocket()),
            )
        )
    websocket = HandshakingWebSocket()
    route = next(route for route in app.routes if getattr(route, "path", None) == "/v1/device/ws")

    await route.endpoint(cast(WebSocket, websocket))

    assert [json.loads(frame)["type"] for frame in websocket.frames] == ["hello_ack", "command"]
    assert registry.connected_device_ids() == ()


@pytest.mark.asyncio
async def test_gateway_unregisters_when_sending_hello_ack_fails() -> None:
    token = "simulator-device-token"  # pragma: allowlist secret
    app = create_device_gateway_app(
        DeviceGatewayConfig(
            device_token_hashes={"sim-001": hash_device_token(token, salt=b"0123456789abcdef")}
        )
    )

    class AckFailingWebSocket:
        def __init__(self) -> None:
            self.headers = {
                "Authorization": f"Bearer {token}",
                "X-StackChan-Device-Id": "sim-001",
            }

        async def accept(self) -> None:
            return None

        async def receive_text(self) -> str:
            return hello_message().model_dump_json()

        async def send_text(self, _data: str) -> None:
            raise RuntimeError("peer disconnected before hello_ack")

        async def close(self, *, code: int, reason: str) -> None:
            raise AssertionError(f"unexpected close: {code} {reason}")

    route = next(route for route in app.routes if getattr(route, "path", None) == "/v1/device/ws")

    await route.endpoint(cast(WebSocket, AckFailingWebSocket()))

    assert app.state.device_registry.connected_device_ids() == ()


@pytest.mark.parametrize(
    ("header_device_id", "token", "expected_code"),
    [
        ("sim-001", "wrong-device-token", 4401),
        ("unknown-device", "simulator-device-token", 4403),
    ],
)
def test_gateway_rejects_invalid_upgrade_identity(
    header_device_id: str,
    token: str,
    expected_code: int,
) -> None:
    app = create_device_gateway_app(
        DeviceGatewayConfig(
            device_token_hashes={
                "sim-001": hash_device_token(
                    "simulator-device-token",  # pragma: allowlist secret
                    salt=b"0123456789abcdef",
                )
            }
        )
    )
    with (
        TestClient(app) as client,
        client.websocket_connect(
            "/v1/device/ws",
            headers={
                "Authorization": f"Bearer {token}",
                "X-StackChan-Device-Id": header_device_id,
            },
        ) as websocket,
        pytest.raises(WebSocketDisconnect) as error,
    ):
        websocket.receive_json()

    assert error.value.code == expected_code


def test_gateway_rate_limits_expensive_authentication_before_scrypt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verified_tokens: list[str] = []

    def reject_token(token: str, _encoded_hash: str) -> bool:
        verified_tokens.append(token)
        return False

    monkeypatch.setattr(
        "stackchan_bridge.device_gateway.application.verify_device_token",
        reject_token,
    )
    app = create_device_gateway_app(
        DeviceGatewayConfig(
            device_token_hashes={"sim-001": "stored-token-hash"},
            authentication_rate_per_second=0.001,
            authentication_rate_burst=1,
        )
    )
    headers = {
        "Authorization": "Bearer wrong-device-token",
        "X-StackChan-Device-Id": "sim-001",
    }

    with TestClient(app) as client:
        close_codes: list[int] = []
        for _ in range(2):
            with (
                client.websocket_connect("/v1/device/ws", headers=headers) as websocket,
                pytest.raises(WebSocketDisconnect) as error,
            ):
                websocket.receive_json()
            close_codes.append(error.value.code)

    assert close_codes == [4401, 4429]
    assert verified_tokens == ["wrong-device-token"]


def test_gateway_rejects_authentication_when_all_scrypt_workers_are_busy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_started = ThreadEvent()
    release_first = ThreadEvent()
    verified_tokens: list[str] = []

    def verify_token(token: str, _encoded_hash: str) -> bool:
        verified_tokens.append(token)
        if token == "first-wrong-token":
            first_started.set()
            assert release_first.wait(timeout=2)
        return False

    monkeypatch.setattr(
        "stackchan_bridge.device_gateway.application.verify_device_token",
        verify_token,
    )
    app = create_device_gateway_app(
        DeviceGatewayConfig(
            device_token_hashes={"sim-001": "stored-token-hash"},
            authentication_rate_per_second=100,
            authentication_rate_burst=10,
            max_concurrent_authentications=1,
        )
    )

    def headers(token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token}",
            "X-StackChan-Device-Id": "sim-001",
        }

    with (
        TestClient(app) as client,
        client.websocket_connect(
            "/v1/device/ws",
            headers=headers("first-wrong-token"),
        ) as first,
    ):
        assert first_started.wait(timeout=1)
        with (
            client.websocket_connect(
                "/v1/device/ws",
                headers=headers("second-wrong-token"),
            ) as second,
            pytest.raises(WebSocketDisconnect) as second_error,
        ):
            second.receive_json()
        release_first.set()
        with pytest.raises(WebSocketDisconnect) as first_error:
            first.receive_json()

    assert second_error.value.code == 4429
    assert first_error.value.code == 4401
    assert verified_tokens == ["first-wrong-token"]


@pytest.mark.asyncio
async def test_authentication_gate_retains_a_slot_until_cancelled_scrypt_finishes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_started = ThreadEvent()
    release_first = ThreadEvent()
    verified_tokens: list[str] = []

    def verify_token(token: str, _encoded_hash: str) -> bool:
        verified_tokens.append(token)
        if token == "first-wrong-token":
            first_started.set()
            assert release_first.wait(timeout=2)
        return False

    monkeypatch.setattr(
        "stackchan_bridge.device_gateway.application.verify_device_token",
        verify_token,
    )
    gate = _AuthenticationGate(rate_per_second=100, capacity=10, max_concurrent=1)
    first = create_task(gate.verify("first-wrong-token", "stored-token-hash"))
    for _ in range(100):
        if first_started.is_set():
            break
        await sleep(0.01)
    assert first_started.is_set()
    first.cancel()
    with pytest.raises(CancelledError):
        await first

    try:
        second = await gate.verify("second-wrong-token", "stored-token-hash")
    finally:
        release_first.set()

    assert second.rate_limited is True
    assert verified_tokens == ["first-wrong-token"]


@pytest.mark.parametrize(
    ("payload_device_id", "versions", "expected_code"),
    [("different-device", [1], 4403), ("sim-001", [2], 4410)],
)
def test_gateway_rejects_invalid_hello_identity_or_version(
    payload_device_id: str,
    versions: list[int],
    expected_code: int,
) -> None:
    token = "simulator-device-token"  # pragma: allowlist secret
    app = create_device_gateway_app(
        DeviceGatewayConfig(
            device_token_hashes={"sim-001": hash_device_token(token, salt=b"0123456789abcdef")}
        )
    )
    hello = hello_message(payload_device_id).model_dump(mode="json")
    payload = hello["payload"]
    assert isinstance(payload, dict)
    payload["protocol_versions"] = versions
    with (
        TestClient(app) as client,
        client.websocket_connect(
            "/v1/device/ws",
            headers={
                "Authorization": f"Bearer {token}",
                "X-StackChan-Device-Id": "sim-001",
            },
        ) as websocket,
    ):
        websocket.send_json(hello)
        with pytest.raises(WebSocketDisconnect) as error:
            websocket.receive_json()

    assert error.value.code == expected_code


def test_new_connection_replaces_the_old_connection_for_the_same_device() -> None:
    token = "simulator-device-token"  # pragma: allowlist secret
    app = create_device_gateway_app(
        DeviceGatewayConfig(
            device_token_hashes={"sim-001": hash_device_token(token, salt=b"0123456789abcdef")}
        )
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "X-StackChan-Device-Id": "sim-001",
    }

    with (
        TestClient(app) as client,
        client.websocket_connect("/v1/device/ws", headers=headers) as first,
    ):
        first.send_text(hello_message().model_dump_json())
        first_ack = HelloAckMessage.model_validate(first.receive_json())
        with client.websocket_connect("/v1/device/ws", headers=headers) as second:
            second.send_text(hello_message().model_dump_json())
            second_ack = HelloAckMessage.model_validate(second.receive_json())

            with pytest.raises(WebSocketDisconnect) as replaced:
                first.receive_json()

            assert replaced.value.code == 4409
            assert first_ack.payload.connection_id != second_ack.payload.connection_id
            assert app.state.device_registry.connected_device_ids() == ("sim-001",)


class RecordingAudioInputHandler:
    def __init__(self) -> None:
        self.started: list[tuple[str, AudioInputStartMessage]] = []
        self.frames: list[tuple[str, AudioInputStartMessage, bytes]] = []
        self.ended: list[tuple[str, AudioInputEndMessage]] = []
        self.completed = ThreadEvent()
        self.stream_timeout_handler: Callable[[str, AudioInputStartMessage], None] | None = None

    def set_stream_timeout_handler(
        self,
        handler: Callable[[str, AudioInputStartMessage], None],
    ) -> None:
        self.stream_timeout_handler = handler

    async def start(self, device_id: str, message: AudioInputStartMessage) -> None:
        self.started.append((device_id, message))

    async def frame(
        self,
        device_id: str,
        stream: AudioInputStartMessage,
        packet: bytes,
    ) -> None:
        self.frames.append((device_id, stream, packet))

    async def end(self, device_id: str, message: AudioInputEndMessage) -> None:
        self.ended.append((device_id, message))
        self.completed.set()

    async def disconnect(self, device_id: str, stream: AudioInputStartMessage) -> None:
        raise AssertionError("completed stream must not disconnect as active")


class ReconnectAwareAudioInputHandler(RecordingAudioInputHandler):
    def __init__(self) -> None:
        super().__init__()
        self.active: dict[str, AudioInputStartMessage] = {}
        self.first_started = ThreadEvent()
        self.second_started = ThreadEvent()
        self.disconnected: list[tuple[str, AudioInputStartMessage]] = []

    async def start(self, device_id: str, message: AudioInputStartMessage) -> None:
        if device_id in self.active:
            raise RuntimeError("device already has an active microphone stream")
        self.active[device_id] = message
        await super().start(device_id, message)
        if len(self.started) == 1:
            self.first_started.set()
        elif len(self.started) == 2:
            self.second_started.set()

    async def end(self, device_id: str, message: AudioInputEndMessage) -> None:
        self.active.pop(device_id, None)
        await super().end(device_id, message)

    async def disconnect(self, device_id: str, stream: AudioInputStartMessage) -> None:
        active = self.active.get(device_id)
        if active is not None and active.stream_id == stream.stream_id:
            self.active.pop(device_id)
        self.disconnected.append((device_id, stream))


class StreamEndingAudioInputHandler(RecordingAudioInputHandler):
    async def frame(
        self,
        device_id: str,
        stream: AudioInputStartMessage,
        packet: bytes,
    ) -> ProtocolErrorCode | None:
        await super().frame(device_id, stream, packet)
        return ProtocolErrorCode.AUDIO_DECODE_ERROR


class TimingOutAudioInputHandler(RecordingAudioInputHandler):
    def __init__(self) -> None:
        super().__init__()
        self.timed_out = ThreadEvent()
        self.second_started = ThreadEvent()
        self.expired: AudioInputStartMessage | None = None

    async def start(self, device_id: str, message: AudioInputStartMessage) -> None:
        await super().start(device_id, message)
        if len(self.started) == 1:
            self.expired = message
            assert self.stream_timeout_handler is not None
            self.stream_timeout_handler(device_id, message)
            self.timed_out.set()
        else:
            self.second_started.set()

    async def end(self, device_id: str, message: AudioInputEndMessage) -> None:
        if self.expired is not None and message.stream_id == self.expired.stream_id:
            raise RuntimeError("timed-out stream is no longer active")
        await super().end(device_id, message)


class RecordingEventHandler:
    def __init__(self) -> None:
        self.events: list[tuple[str, EventMessage]] = []
        self.handled = ThreadEvent()

    async def handle(self, device_id: str, message: EventMessage) -> None:
        self.events.append((device_id, message))
        self.handled.set()


class TurnStartingEventHandler:
    def __init__(self, coordinator: TurnCoordinator) -> None:
        self.coordinator = coordinator
        self.turn: Turn | None = None
        self.started = ThreadEvent()

    async def handle(self, device_id: str, message: EventMessage) -> None:
        self.turn = await self.coordinator.begin(device_id, trigger=TurnTrigger.CONTROL_API)
        await self.coordinator.transition(self.turn.turn_id, TurnState.TRANSCRIBING)
        await self.coordinator.transition(self.turn.turn_id, TurnState.WAITING_HERMES)
        self.started.set()


def test_gateway_disconnect_cancels_a_turn_after_audio_input_has_ended() -> None:
    token = "simulator-device-token"  # pragma: allowlist secret
    coordinator = TurnCoordinator()
    handler = TurnStartingEventHandler(coordinator)
    app = create_device_gateway_app(
        DeviceGatewayConfig(
            device_token_hashes={"sim-001": hash_device_token(token, salt=b"0123456789abcdef")}
        ),
        event_handler=handler,
        turn_coordinator=coordinator,
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "X-StackChan-Device-Id": "sim-001",
    }

    with (
        TestClient(app) as client,
        client.websocket_connect("/v1/device/ws", headers=headers) as websocket,
    ):
        websocket.send_text(hello_message().model_dump_json())
        websocket.receive_json()
        websocket.send_json(
            {
                "v": 1,
                "type": "event",
                "message_id": "669f5c66-9582-413b-bb2d-a94315a3a8a8",
                "device_id": "sim-001",
                "sent_at_ms": 10,
                "payload": {"name": "touch.tap", "data": {"x": 100, "y": 120}},
            }
        )
        assert handler.started.wait(timeout=1)

    assert handler.turn is not None
    assert handler.turn.state is TurnState.CANCELLING
    assert handler.turn.failure_reason == "disconnect"
    assert coordinator.current("sim-001") is None


def test_reconnection_cancels_the_turn_owned_by_the_replaced_connection() -> None:
    token = "simulator-device-token"  # pragma: allowlist secret
    coordinator = TurnCoordinator()
    handler = TurnStartingEventHandler(coordinator)
    app = create_device_gateway_app(
        DeviceGatewayConfig(
            device_token_hashes={"sim-001": hash_device_token(token, salt=b"0123456789abcdef")}
        ),
        event_handler=handler,
        turn_coordinator=coordinator,
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "X-StackChan-Device-Id": "sim-001",
    }

    with (
        TestClient(app) as client,
        client.websocket_connect("/v1/device/ws", headers=headers) as first,
    ):
        first.send_text(hello_message().model_dump_json())
        first.receive_json()
        first.send_json(
            {
                "v": 1,
                "type": "event",
                "message_id": "769f5c66-9582-413b-bb2d-a94315a3a8a8",
                "device_id": "sim-001",
                "sent_at_ms": 10,
                "payload": {"name": "touch.tap", "data": {"x": 100, "y": 120}},
            }
        )
        assert handler.started.wait(timeout=1)
        assert coordinator.current("sim-001") is handler.turn

        with client.websocket_connect("/v1/device/ws", headers=headers) as second:
            second.send_text(hello_message().model_dump_json())
            second.receive_json()

            assert coordinator.current("sim-001") is None
            assert handler.turn is not None
            assert handler.turn.failure_reason == "connection_replaced"


def test_reconnection_releases_the_replaced_audio_input_before_acknowledging() -> None:
    token = "simulator-device-token"  # pragma: allowlist secret
    handler = ReconnectAwareAudioInputHandler()
    app = create_device_gateway_app(
        DeviceGatewayConfig(
            device_token_hashes={"sim-001": hash_device_token(token, salt=b"0123456789abcdef")}
        ),
        audio_input_handler=handler,
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "X-StackChan-Device-Id": "sim-001",
    }
    first_stream = {
        "v": 1,
        "type": "audio.input.start",
        "message_id": "4154f260-6354-4827-8b4d-30782c14fe4e",
        "turn_id": "168b58ca-7c31-4744-b445-d2f20c9bdde0",
        "stream_id": "90c213a0-61a0-4564-9a12-124ddb855c04",
        "sent_at_ms": 1,
        "payload": {
            "codec": "opus",
            "sample_rate": 16_000,
            "channels": 1,
            "frame_ms": 60,
            "trigger": "touch",
        },
    }
    second_stream = {
        **first_stream,
        "message_id": "5154f260-6354-4827-8b4d-30782c14fe4e",
        "turn_id": "268b58ca-7c31-4744-b445-d2f20c9bdde0",
        "stream_id": "a0c213a0-61a0-4564-9a12-124ddb855c04",
        "sent_at_ms": 2,
    }

    with (
        TestClient(app) as client,
        client.websocket_connect("/v1/device/ws", headers=headers) as first,
    ):
        first.send_text(hello_message().model_dump_json())
        first.receive_json()
        first.send_json(first_stream)
        assert handler.first_started.wait(timeout=1)

        with client.websocket_connect("/v1/device/ws", headers=headers) as second:
            second.send_text(hello_message().model_dump_json())
            second.receive_json()

            assert [stream.stream_id for _, stream in handler.disconnected] == [
                AudioInputStartMessage.model_validate(first_stream).stream_id
            ]
            second.send_json(second_stream)
            assert handler.second_started.wait(timeout=1)


def test_gateway_routes_binary_only_during_the_owned_audio_input_stream() -> None:
    token = "simulator-device-token"  # pragma: allowlist secret
    handler = RecordingAudioInputHandler()
    app = create_device_gateway_app(
        DeviceGatewayConfig(
            device_token_hashes={"sim-001": hash_device_token(token, salt=b"0123456789abcdef")}
        ),
        audio_input_handler=handler,
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "X-StackChan-Device-Id": "sim-001",
    }
    stream = {
        "v": 1,
        "type": "audio.input.start",
        "message_id": "4154f260-6354-4827-8b4d-30782c14fe4e",
        "turn_id": "168b58ca-7c31-4744-b445-d2f20c9bdde0",
        "stream_id": "90c213a0-61a0-4564-9a12-124ddb855c04",
        "sent_at_ms": 1,
        "payload": {
            "codec": "opus",
            "sample_rate": 16_000,
            "channels": 1,
            "frame_ms": 60,
            "trigger": "touch",
        },
    }
    end = {
        "v": 1,
        "type": "audio.input.end",
        "message_id": "0581ece7-3baf-4277-9420-eeea9dfa35b6",
        "turn_id": stream["turn_id"],
        "stream_id": stream["stream_id"],
        "sent_at_ms": 2,
        "payload": {"reason": "silence"},
    }

    with (
        TestClient(app) as client,
        client.websocket_connect("/v1/device/ws", headers=headers) as websocket,
    ):
        websocket.send_text(hello_message().model_dump_json())
        websocket.receive_json()
        websocket.send_bytes(b"orphan")
        websocket.send_json(stream)
        websocket.send_bytes(b"owned-opus")
        websocket.send_json(end)
        websocket.send_bytes(b"late")
        websocket.send_text("{}")
        orphan_error = ErrorMessage.model_validate(websocket.receive_json())
        late_error = ErrorMessage.model_validate(websocket.receive_json())
        with pytest.raises(WebSocketDisconnect) as closed:
            websocket.receive_json()

    assert orphan_error.payload.code.value == "INVALID_STATE"
    assert late_error.payload.code.value == "INVALID_STATE"
    assert closed.value.code == 4400

    assert [(device_id, message.stream_id) for device_id, message in handler.started] == [
        ("sim-001", AudioInputStartMessage.model_validate(stream).stream_id)
    ]
    assert [(device_id, packet) for device_id, _, packet in handler.frames] == [
        ("sim-001", b"owned-opus")
    ]
    assert [(device_id, message.payload.reason) for device_id, message in handler.ended] == [
        ("sim-001", "silence")
    ]


def test_gateway_reports_and_counts_binary_frames_outside_an_input_stream() -> None:
    token = "simulator-device-token"  # pragma: allowlist secret
    handler = RecordingAudioInputHandler()
    app = create_device_gateway_app(
        DeviceGatewayConfig(
            device_token_hashes={"sim-001": hash_device_token(token, salt=b"0123456789abcdef")},
            audio_packet_rate_per_second=0.001,
            audio_packet_rate_burst=3,
        ),
        audio_input_handler=handler,
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "X-StackChan-Device-Id": "sim-001",
    }

    with (
        TestClient(app) as client,
        client.websocket_connect("/v1/device/ws", headers=headers) as websocket,
    ):
        websocket.send_text(hello_message().model_dump_json())
        websocket.receive_json()
        for _ in range(4):
            websocket.send_bytes(b"orphan-opus")

        first = ErrorMessage.model_validate(websocket.receive_json())
        second = ErrorMessage.model_validate(websocket.receive_json())
        with pytest.raises(WebSocketDisconnect) as closed:
            websocket.receive_json()

    assert first.payload.code.value == "INVALID_STATE"
    assert second.payload.code.value == "INVALID_STATE"
    assert closed.value.code == 4400
    assert handler.frames == []


def test_gateway_reports_an_audio_stream_failure_without_closing_the_connection() -> None:
    token = "simulator-device-token"  # pragma: allowlist secret
    handler = StreamEndingAudioInputHandler()
    app = create_device_gateway_app(
        DeviceGatewayConfig(
            device_token_hashes={"sim-001": hash_device_token(token, salt=b"0123456789abcdef")}
        ),
        audio_input_handler=handler,
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "X-StackChan-Device-Id": "sim-001",
    }
    first_stream = {
        "v": 1,
        "type": "audio.input.start",
        "message_id": "4154f260-6354-4827-8b4d-30782c14fe4e",
        "turn_id": "168b58ca-7c31-4744-b445-d2f20c9bdde0",
        "stream_id": "90c213a0-61a0-4564-9a12-124ddb855c04",
        "sent_at_ms": 1,
        "payload": {
            "codec": "opus",
            "sample_rate": 16_000,
            "channels": 1,
            "frame_ms": 60,
            "trigger": "touch",
        },
    }
    second_stream = {
        **first_stream,
        "message_id": "5154f260-6354-4827-8b4d-30782c14fe4e",
        "turn_id": "268b58ca-7c31-4744-b445-d2f20c9bdde0",
        "stream_id": "a0c213a0-61a0-4564-9a12-124ddb855c04",
        "sent_at_ms": 2,
    }
    second_end = {
        "v": 1,
        "type": "audio.input.end",
        "message_id": "6154f260-6354-4827-8b4d-30782c14fe4e",
        "turn_id": second_stream["turn_id"],
        "stream_id": second_stream["stream_id"],
        "sent_at_ms": 3,
        "payload": {"reason": "device_error"},
    }

    with (
        TestClient(app) as client,
        client.websocket_connect("/v1/device/ws", headers=headers) as websocket,
    ):
        websocket.send_text(hello_message().model_dump_json())
        websocket.receive_json()
        websocket.send_json(first_stream)
        websocket.send_bytes(b"third-malformed-packet")
        websocket.send_json(second_stream)
        error = ErrorMessage.model_validate(websocket.receive_json())
        websocket.send_json(second_end)
        assert handler.completed.wait(timeout=1)

    assert error.payload.code is ProtocolErrorCode.AUDIO_DECODE_ERROR
    assert error.turn_id == UUID(str(first_stream["turn_id"]))
    assert error.stream_id == UUID(str(first_stream["stream_id"]))
    assert len(handler.started) == 2


@pytest.mark.parametrize("violation", ["second_start", "wrong_turn_end", "wrong_stream_end"])
def test_gateway_preserves_audio_input_after_invalid_control(violation: str) -> None:
    token = "simulator-device-token"  # pragma: allowlist secret
    handler = ReconnectAwareAudioInputHandler()
    app = create_device_gateway_app(
        DeviceGatewayConfig(
            device_token_hashes={"sim-001": hash_device_token(token, salt=b"0123456789abcdef")}
        ),
        audio_input_handler=handler,
    )
    start = AudioInputStartMessage.model_validate(
        {
            "v": 1,
            "type": "audio.input.start",
            "message_id": str(uuid4()),
            "turn_id": str(uuid4()),
            "stream_id": str(uuid4()),
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
    end = {
        **start.model_dump(mode="json", exclude_none=True),
        "type": "audio.input.end",
        "message_id": str(uuid4()),
        "payload": {"reason": "silence"},
    }
    invalid = (
        start.model_dump(mode="json", exclude_none=True) if violation == "second_start" else end
    )
    invalid = {**invalid, "message_id": str(uuid4())}
    invalid["turn_id" if violation == "wrong_turn_end" else "stream_id"] = str(uuid4())
    headers = {"Authorization": f"Bearer {token}", "X-StackChan-Device-Id": "sim-001"}

    with (
        TestClient(app) as client,
        client.websocket_connect("/v1/device/ws", headers=headers) as websocket,
    ):
        websocket.send_text(hello_message().model_dump_json())
        websocket.receive_json()
        websocket.send_text(start.model_dump_json())
        for _ in range(2):
            websocket.send_json({**invalid, "message_id": str(uuid4())})
            error = ErrorMessage.model_validate(websocket.receive_json())
            assert error.payload.code is ProtocolErrorCode.INVALID_STATE
        websocket.send_bytes(b"still-owned")
        websocket.send_json(end)
        assert handler.completed.wait(timeout=1)
        websocket.send_json({**end, "message_id": str(uuid4())})
        with pytest.raises(WebSocketDisconnect) as closed:
            websocket.receive_json()
        assert closed.value.code == 4400

    assert handler.started == [("sim-001", start)]
    assert handler.frames == [("sim-001", start, b"still-owned")]
    assert [message.stream_id for _, message in handler.ended] == [start.stream_id]


def test_gateway_keeps_connection_reusable_after_audio_input_deadline() -> None:
    token = "simulator-device-token"  # pragma: allowlist secret
    handler = TimingOutAudioInputHandler()
    app = create_device_gateway_app(
        DeviceGatewayConfig(
            device_token_hashes={"sim-001": hash_device_token(token, salt=b"0123456789abcdef")}
        ),
        audio_input_handler=handler,
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "X-StackChan-Device-Id": "sim-001",
    }
    first_stream = {
        "v": 1,
        "type": "audio.input.start",
        "message_id": "b154f260-6354-4827-8b4d-30782c14fe4e",
        "turn_id": "b68b58ca-7c31-4744-b445-d2f20c9bdde0",
        "stream_id": "b0c213a0-61a0-4564-9a12-124ddb855c04",
        "sent_at_ms": 1,
        "payload": {
            "codec": "opus",
            "sample_rate": 16_000,
            "channels": 1,
            "frame_ms": 60,
            "trigger": "touch",
        },
    }
    first_end = {
        "v": 1,
        "type": "audio.input.end",
        "message_id": "b254f260-6354-4827-8b4d-30782c14fe4e",
        "turn_id": first_stream["turn_id"],
        "stream_id": first_stream["stream_id"],
        "sent_at_ms": 2,
        "payload": {"reason": "max_duration"},
    }
    second_stream = {
        **first_stream,
        "message_id": "b354f260-6354-4827-8b4d-30782c14fe4e",
        "turn_id": "b78b58ca-7c31-4744-b445-d2f20c9bdde0",
        "stream_id": "b1c213a0-61a0-4564-9a12-124ddb855c04",
        "sent_at_ms": 3,
    }
    second_end = {
        **first_end,
        "message_id": "b454f260-6354-4827-8b4d-30782c14fe4e",
        "turn_id": second_stream["turn_id"],
        "stream_id": second_stream["stream_id"],
        "sent_at_ms": 4,
        "payload": {"reason": "user_cancel"},
    }

    with (
        TestClient(app) as client,
        client.websocket_connect("/v1/device/ws", headers=headers) as websocket,
    ):
        websocket.send_text(hello_message().model_dump_json())
        websocket.receive_json()
        websocket.send_json(first_stream)
        assert handler.timed_out.wait(timeout=1)
        websocket.send_json(first_end)
        websocket.send_json(second_stream)
        assert handler.second_started.wait(timeout=1)
        websocket.send_json(second_end)
        assert handler.completed.wait(timeout=1)

    assert [message.stream_id for _, message in handler.ended] == [
        AudioInputEndMessage.model_validate(second_end).stream_id
    ]


def test_gateway_ignores_a_retried_text_message_id() -> None:
    token = "simulator-device-token"  # pragma: allowlist secret
    handler = RecordingAudioInputHandler()
    app = create_device_gateway_app(
        DeviceGatewayConfig(
            device_token_hashes={"sim-001": hash_device_token(token, salt=b"0123456789abcdef")}
        ),
        audio_input_handler=handler,
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "X-StackChan-Device-Id": "sim-001",
    }
    stream = {
        "v": 1,
        "type": "audio.input.start",
        "message_id": "4154f260-6354-4827-8b4d-30782c14fe4e",
        "turn_id": "168b58ca-7c31-4744-b445-d2f20c9bdde0",
        "stream_id": "90c213a0-61a0-4564-9a12-124ddb855c04",
        "sent_at_ms": 1,
        "payload": {
            "codec": "opus",
            "sample_rate": 16_000,
            "channels": 1,
            "frame_ms": 60,
            "trigger": "touch",
        },
    }
    end = {
        "v": 1,
        "type": "audio.input.end",
        "message_id": "0581ece7-3baf-4277-9420-eeea9dfa35b6",
        "turn_id": stream["turn_id"],
        "stream_id": stream["stream_id"],
        "sent_at_ms": 2,
        "payload": {"reason": "silence"},
    }

    with (
        TestClient(app) as client,
        client.websocket_connect("/v1/device/ws", headers=headers) as websocket,
    ):
        websocket.send_text(hello_message().model_dump_json())
        websocket.receive_json()
        websocket.send_json(stream)
        websocket.send_json(stream)
        websocket.send_bytes(b"one-packet")
        websocket.send_json(end)
        websocket.send_text("{}")
        assert ErrorMessage.model_validate(websocket.receive_json()).payload.code.value == (
            "INVALID_MESSAGE"
        )

    assert len(handler.started) == 1
    assert [packet for _, _, packet in handler.frames] == [b"one-packet"]
    assert len(handler.ended) == 1


def test_gateway_routes_an_owned_device_event_once() -> None:
    token = "simulator-device-token"  # pragma: allowlist secret
    handler = RecordingEventHandler()
    app = create_device_gateway_app(
        DeviceGatewayConfig(
            device_token_hashes={"sim-001": hash_device_token(token, salt=b"0123456789abcdef")}
        ),
        event_handler=handler,
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "X-StackChan-Device-Id": "sim-001",
    }
    event = {
        "v": 1,
        "type": "event",
        "message_id": "669f5c66-9582-413b-bb2d-a94315a3a8a8",
        "device_id": "sim-001",
        "sent_at_ms": 10,
        "payload": {
            "name": "touch.tap",
            "data": {"x": 100, "y": 120},
        },
    }

    with (
        TestClient(app) as client,
        client.websocket_connect("/v1/device/ws", headers=headers) as websocket,
    ):
        websocket.send_text(hello_message().model_dump_json())
        websocket.receive_json()
        websocket.send_json(event)
        websocket.send_json(event)
        websocket.send_text("{}")
        assert ErrorMessage.model_validate(websocket.receive_json()).payload.code.value == (
            "INVALID_MESSAGE"
        )

    assert len(handler.events) == 1
    assert handler.events[0][0] == "sim-001"
    assert handler.events[0][1].payload.name == "touch.tap"


def test_gateway_counts_device_audio_buffer_events() -> None:
    token = "simulator-device-token"  # pragma: allowlist secret
    metrics = BridgeMetrics()
    registry = DeviceRegistry(command_timeout_seconds=5, metrics=metrics)
    app = create_device_gateway_app(
        DeviceGatewayConfig(
            device_token_hashes={"sim-001": hash_device_token(token, salt=b"0123456789abcdef")}
        ),
        registry=registry,
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "X-StackChan-Device-Id": "sim-001",
    }
    event = {
        "v": 1,
        "type": "event",
        "message_id": "669f5c66-9582-413b-bb2d-a94315a3a8a8",
        "device_id": "sim-001",
        "sent_at_ms": 10,
        "payload": {
            "name": "audio.underrun",
            "data": {
                "stream_id": "168b58ca-7c31-4744-b445-d2f20c9bdde0",
                "dropped_packets": 1,
            },
        },
    }

    with (
        TestClient(app) as client,
        client.websocket_connect("/v1/device/ws", headers=headers) as websocket,
    ):
        websocket.send_text(hello_message().model_dump_json())
        websocket.receive_json()
        websocket.send_json(event)
        websocket.send_json(
            {
                **event,
                "message_id": "ea9a54b2-827a-4149-9394-787947d9c09a",
                "payload": {**event["payload"], "name": "audio.overflow"},
            }
        )
        websocket.send_text("{}")
        assert ErrorMessage.model_validate(websocket.receive_json()).payload.code.value == (
            "INVALID_MESSAGE"
        )

    output = generate_latest(metrics.registry)
    assert b"audio_underrun_total 1.0" in output
    assert b"audio_overflow_total 1.0" in output


def test_gateway_closes_a_connection_that_exceeds_the_configured_request_burst() -> None:
    token = "simulator-device-token"  # pragma: allowlist secret
    handler = RecordingEventHandler()
    app = create_device_gateway_app(
        DeviceGatewayConfig(
            device_token_hashes={"sim-001": hash_device_token(token, salt=b"0123456789abcdef")},
            request_rate_per_second=1,
            request_rate_burst=1,
        ),
        event_handler=handler,
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "X-StackChan-Device-Id": "sim-001",
    }
    first = {
        "v": 1,
        "type": "event",
        "message_id": "669f5c66-9582-413b-bb2d-a94315a3a8a8",
        "device_id": "sim-001",
        "sent_at_ms": 10,
        "payload": {"name": "touch.tap", "data": {"x": 100, "y": 120}},
    }
    second = {
        **first,
        "message_id": "ea9a54b2-827a-4149-9394-787947d9c09a",
        "sent_at_ms": 11,
    }

    with (
        TestClient(app) as client,
        client.websocket_connect("/v1/device/ws", headers=headers) as websocket,
    ):
        websocket.send_text(hello_message().model_dump_json())
        websocket.receive_json()
        websocket.send_json(first)
        websocket.send_json(second)
        with pytest.raises(WebSocketDisconnect) as error:
            websocket.receive_json()

    assert error.value.code == 4429
    assert len(handler.events) == 1


def test_gateway_excludes_audio_packets_from_the_non_audio_rate_limit() -> None:
    token = "simulator-device-token"  # pragma: allowlist secret

    class DisconnectTolerantHandler(RecordingAudioInputHandler):
        async def disconnect(self, device_id: str, stream: AudioInputStartMessage) -> None:
            return None

    handler = DisconnectTolerantHandler()
    app = create_device_gateway_app(
        DeviceGatewayConfig(
            device_token_hashes={"sim-001": hash_device_token(token, salt=b"0123456789abcdef")},
            request_rate_per_second=0.001,
            request_rate_burst=2,
            audio_packet_rate_per_second=0.001,
            audio_packet_rate_burst=300,
        ),
        audio_input_handler=handler,
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "X-StackChan-Device-Id": "sim-001",
    }
    stream = {
        "v": 1,
        "type": "audio.input.start",
        "message_id": "4154f260-6354-4827-8b4d-30782c14fe4e",
        "turn_id": "168b58ca-7c31-4744-b445-d2f20c9bdde0",
        "stream_id": "90c213a0-61a0-4564-9a12-124ddb855c04",
        "sent_at_ms": 1,
        "payload": {
            "codec": "opus",
            "sample_rate": 16_000,
            "channels": 1,
            "frame_ms": 60,
            "trigger": "simulator",
        },
    }
    end = {
        "v": 1,
        "type": "audio.input.end",
        "message_id": "0581ece7-3baf-4277-9420-eeea9dfa35b6",
        "turn_id": stream["turn_id"],
        "stream_id": stream["stream_id"],
        "sent_at_ms": 2,
        "payload": {"reason": "silence"},
    }

    with (
        TestClient(app) as client,
        client.websocket_connect("/v1/device/ws", headers=headers) as websocket,
    ):
        websocket.send_text(hello_message().model_dump_json())
        websocket.receive_json()
        websocket.send_json(stream)
        for _ in range(250):
            websocket.send_bytes(b"legal-opus-packet")
        websocket.send_json(end)
        assert handler.completed.wait(timeout=1)

    assert len(handler.frames) == 250


def test_gateway_rate_limits_binary_audio_packets_with_a_separate_bucket() -> None:
    token = "simulator-device-token"  # pragma: allowlist secret

    class DisconnectTolerantHandler(RecordingAudioInputHandler):
        async def disconnect(self, device_id: str, stream: AudioInputStartMessage) -> None:
            return None

    handler = DisconnectTolerantHandler()
    app = create_device_gateway_app(
        DeviceGatewayConfig(
            device_token_hashes={"sim-001": hash_device_token(token, salt=b"0123456789abcdef")},
            audio_packet_rate_per_second=0.001,
            audio_packet_rate_burst=2,
        ),
        audio_input_handler=handler,
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "X-StackChan-Device-Id": "sim-001",
    }
    stream = {
        "v": 1,
        "type": "audio.input.start",
        "message_id": "4154f260-6354-4827-8b4d-30782c14fe4e",
        "turn_id": "168b58ca-7c31-4744-b445-d2f20c9bdde0",
        "stream_id": "90c213a0-61a0-4564-9a12-124ddb855c04",
        "sent_at_ms": 1,
        "payload": {
            "codec": "opus",
            "sample_rate": 16_000,
            "channels": 1,
            "frame_ms": 60,
            "trigger": "simulator",
        },
    }

    with (
        TestClient(app) as client,
        client.websocket_connect("/v1/device/ws", headers=headers) as websocket,
    ):
        websocket.send_text(hello_message().model_dump_json())
        websocket.receive_json()
        websocket.send_json(stream)
        websocket.send_bytes(b"first-opus-packet")
        websocket.send_bytes(b"second-opus-packet")
        websocket.send_bytes(b"third-opus-packet")
        with pytest.raises(WebSocketDisconnect) as error:
            websocket.receive_json()

    assert error.value.code == 4429
    assert len(handler.frames) == 2


def test_gateway_reports_two_invalid_json_messages_before_closing_on_the_third() -> None:
    token = "simulator-device-token"  # pragma: allowlist secret
    handler = RecordingEventHandler()
    app = create_device_gateway_app(
        DeviceGatewayConfig(
            device_token_hashes={"sim-001": hash_device_token(token, salt=b"0123456789abcdef")}
        ),
        event_handler=handler,
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "X-StackChan-Device-Id": "sim-001",
    }

    with (
        TestClient(app) as client,
        client.websocket_connect("/v1/device/ws", headers=headers) as websocket,
    ):
        websocket.send_text(hello_message().model_dump_json())
        websocket.receive_json()
        websocket.send_text("{")
        first = ErrorMessage.model_validate(websocket.receive_json())
        websocket.send_text("{}")
        second = ErrorMessage.model_validate(websocket.receive_json())
        websocket.send_json(
            {
                "v": 1,
                "type": "event",
                "message_id": "669f5c66-9582-413b-bb2d-a94315a3a8a8",
                "device_id": "sim-001",
                "sent_at_ms": 10,
                "payload": {"name": "touch.tap", "data": {"x": 100, "y": 120}},
            }
        )
        assert handler.handled.wait(timeout=1)
        websocket.send_text("[]")
        with pytest.raises(WebSocketDisconnect) as closed:
            websocket.receive_json()

    assert first.payload.code.value == "INVALID_MESSAGE"
    assert second.payload.code.value == "INVALID_MESSAGE"
    assert closed.value.code == 4400


def test_gateway_accepts_and_records_a_firmware_error_message(
    caplog: pytest.LogCaptureFixture,
) -> None:
    token = "simulator-device-token"  # pragma: allowlist secret
    handler = RecordingEventHandler()
    app = create_device_gateway_app(
        DeviceGatewayConfig(
            device_token_hashes={"sim-001": hash_device_token(token, salt=b"0123456789abcdef")}
        ),
        event_handler=handler,
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "X-StackChan-Device-Id": "sim-001",
    }

    with (
        caplog.at_level("WARNING", logger="stackchan_bridge.device_gateway"),
        TestClient(app) as client,
        client.websocket_connect("/v1/device/ws", headers=headers) as websocket,
    ):
        websocket.send_text(hello_message().model_dump_json())
        websocket.receive_json()
        websocket.send_json(
            {
                "v": 1,
                "type": "error",
                "message_id": "44c57d22-05cf-409d-a527-d20cf2dac723",
                "sent_at_ms": 10,
                "payload": {
                    "code": "AUDIO_DECODE_ERROR",
                    "message": "audio frame was dropped",
                },
            }
        )
        websocket.send_json(
            {
                "v": 1,
                "type": "event",
                "message_id": "669f5c66-9582-413b-bb2d-a94315a3a8a8",
                "device_id": "sim-001",
                "sent_at_ms": 11,
                "payload": {"name": "touch.tap", "data": {"x": 100, "y": 120}},
            }
        )
        assert handler.handled.wait(timeout=1)

    assert any(
        getattr(record, "error_code", None) == "AUDIO_DECODE_ERROR" for record in caplog.records
    )


def test_gateway_rejects_a_new_device_over_the_connection_limit() -> None:
    first_token = "first-device-token"  # pragma: allowlist secret
    second_token = "second-device-token"  # pragma: allowlist secret
    app = create_device_gateway_app(
        DeviceGatewayConfig(
            device_token_hashes={
                "sim-001": hash_device_token(first_token, salt=b"0123456789abcdef"),
                "sim-002": hash_device_token(second_token, salt=b"fedcba9876543210"),
            },
            max_connections=1,
        )
    )

    with (
        TestClient(app) as client,
        client.websocket_connect(
            "/v1/device/ws",
            headers={
                "Authorization": f"Bearer {first_token}",
                "X-StackChan-Device-Id": "sim-001",
            },
        ) as first,
    ):
        first.send_text(hello_message("sim-001").model_dump_json())
        first.receive_json()
        with client.websocket_connect(
            "/v1/device/ws",
            headers={
                "Authorization": f"Bearer {second_token}",
                "X-StackChan-Device-Id": "sim-002",
            },
        ) as second:
            second.send_text(hello_message("sim-002").model_dump_json())
            with pytest.raises(WebSocketDisconnect) as rejected:
                second.receive_json()

        assert rejected.value.code == 4429
        assert app.state.device_registry.connected_device_ids() == ("sim-001",)
