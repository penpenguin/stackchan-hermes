from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

import pytest
from stackchan_bridge.protocol.models import (
    CommandMessage,
    CommandResultMessage,
    EventMessage,
    HelloAckMessage,
    HelloMessage,
    parse_text_frame,
)
from stackchan_simulator.device import DeviceSimulator, SimulatorConfig, SimulatorFault
from websockets.asyncio.server import ServerConnection, serve


@asynccontextmanager
async def handshake_server() -> AsyncIterator[tuple[str, list[HelloMessage]]]:
    received: list[HelloMessage] = []

    async def handler(connection: ServerConnection) -> None:
        assert connection.request.headers["Authorization"] == "Bearer test-device-token"
        assert connection.request.headers["X-StackChan-Device-Id"] == "sim-001"
        message = parse_text_frame(await connection.recv())
        assert isinstance(message, HelloMessage)
        received.append(message)
        acknowledgement = HelloAckMessage.model_validate(
            {
                "v": 1,
                "type": "hello_ack",
                "message_id": "519a16ce-3a07-4ab6-9767-f39bcc096cb8",
                "sent_at_ms": 1,
                "payload": {
                    "connection_id": "79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc",
                    "capture_protocol_version": 2,
                    "selected_protocol_version": 1,
                    "heartbeat_interval_ms": 15_000,
                    "max_command_timeout_ms": 5_000,
                    "server_version": "0.1.0",
                },
            }
        )
        await connection.send(acknowledgement.model_dump_json())

    async with serve(handler, "127.0.0.1", 0) as server:
        socket = server.sockets[0]
        port = socket.getsockname()[1]
        yield f"ws://127.0.0.1:{port}/v1/device/ws", received


@pytest.mark.asyncio
async def test_simulator_completes_authenticated_hello_handshake() -> None:
    async with handshake_server() as (bridge_url, received):
        simulator = DeviceSimulator(
            SimulatorConfig(
                bridge_url=bridge_url,
                device_id="sim-001",
                token="test-device-token",  # pragma: allowlist secret
            )
        )

        acknowledgement = await simulator.handshake()

    assert acknowledgement.payload.selected_protocol_version == 1
    assert acknowledgement.payload.connection_id == UUID("79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc")
    assert [hello.payload.device_id for hello in received] == ["sim-001"]


@pytest.mark.asyncio
async def test_simulator_returns_a_correlated_head_command_result() -> None:
    results: list[CommandResultMessage] = []

    async def handler(connection: ServerConnection) -> None:
        hello = parse_text_frame(await connection.recv())
        assert isinstance(hello, HelloMessage)
        acknowledgement = HelloAckMessage.model_validate(
            {
                "v": 1,
                "type": "hello_ack",
                "message_id": "519a16ce-3a07-4ab6-9767-f39bcc096cb8",
                "sent_at_ms": 1,
                "payload": {
                    "connection_id": "79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc",
                    "capture_protocol_version": 2,
                    "selected_protocol_version": 1,
                    "heartbeat_interval_ms": 15_000,
                    "max_command_timeout_ms": 5_000,
                    "server_version": "0.1.0",
                },
            }
        )
        await connection.send(acknowledgement.model_dump_json())
        pong_waiter = await connection.ping(b"phase-2-heartbeat")
        await pong_waiter
        command = CommandMessage.model_validate(
            {
                "v": 1,
                "type": "command",
                "message_id": "b74d56ae-9e0d-453f-81d6-29c74361c8a4",
                "request_id": "a75dff8d-b78a-4f14-9d33-848a817301da",
                "sent_at_ms": 2,
                "payload": {
                    "name": "head.set_angles",
                    "args": {"yaw": 15, "pitch": 40, "speed": 30},
                },
            }
        )
        await connection.send(command.model_dump_json())
        result = parse_text_frame(await connection.recv())
        assert isinstance(result, CommandResultMessage)
        results.append(result)

    async with serve(handler, "127.0.0.1", 0) as server:
        port = server.sockets[0].getsockname()[1]
        simulator = DeviceSimulator(
            SimulatorConfig(
                bridge_url=f"ws://127.0.0.1:{port}/v1/device/ws",
                device_id="sim-001",
                token="test-device-token",  # pragma: allowlist secret
            )
        )

        command = await simulator.run_one_command()

    assert command.payload.name == "head.set_angles"
    assert simulator.head_angles == (15, 40)
    assert len(results) == 1
    assert results[0].request_id == command.request_id
    assert results[0].payload.ok is True
    assert results[0].payload.result == {"yaw": 15, "pitch": 40}


def test_simulator_can_advertise_an_unsupported_protocol_for_fault_testing() -> None:
    simulator = DeviceSimulator(
        SimulatorConfig(
            bridge_url="ws://127.0.0.1:8765/v1/device/ws",
            device_id="sim-001",
            token="test-device-token",  # pragma: allowlist secret
            protocol_versions=(2,),
        )
    )

    assert simulator.hello_message().payload.protocol_versions == [2]


def test_simulator_builds_bounded_transport_fault_frames() -> None:
    simulator = DeviceSimulator(
        SimulatorConfig(
            bridge_url="ws://127.0.0.1:8765/v1/device/ws",
            device_id="sim-001",
            token="test-device-token",  # pragma: allowlist secret
        )
    )

    assert simulator.fault_frames(SimulatorFault.MALFORMED_JSON) == ("{",)
    malformed_opus = simulator.fault_frames(SimulatorFault.MALFORMED_OPUS)
    assert len(malformed_opus) == 2
    assert isinstance(malformed_opus[0], str)
    assert malformed_opus[1] == b"malformed-opus"
    duplicate = simulator.fault_frames(SimulatorFault.DUPLICATE_MESSAGE)
    assert len(duplicate) == 2
    assert duplicate[0] == duplicate[1]
    assert simulator.fault_frames(SimulatorFault.DISCONNECT) == ()


@pytest.mark.parametrize(
    "overrides",
    [
        {"protocol_versions": ()},
        {"protocol_versions": (1, 1)},
        {"protocol_versions": (0,)},
        {"command_delay_seconds": -0.1},
        {"command_delay_seconds": 31},
    ],
)
def test_simulator_rejects_unbounded_fault_configuration(overrides: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        SimulatorConfig(
            bridge_url="ws://127.0.0.1:8765/v1/device/ws",
            device_id="sim-001",
            token="test-device-token",  # pragma: allowlist secret
            **overrides,
        )


@pytest.mark.asyncio
async def test_simulator_sends_touch_battery_and_wifi_events() -> None:
    received: list[EventMessage] = []

    async def handler(connection: ServerConnection) -> None:
        hello = parse_text_frame(await connection.recv())
        assert isinstance(hello, HelloMessage)
        acknowledgement = HelloAckMessage.model_validate(
            {
                "v": 1,
                "type": "hello_ack",
                "message_id": "519a16ce-3a07-4ab6-9767-f39bcc096cb8",
                "sent_at_ms": 1,
                "payload": {
                    "connection_id": "79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc",
                    "capture_protocol_version": 2,
                    "selected_protocol_version": 1,
                    "heartbeat_interval_ms": 15_000,
                    "max_command_timeout_ms": 5_000,
                    "server_version": "0.1.0",
                },
            }
        )
        await connection.send(acknowledgement.model_dump_json())
        for _ in range(3):
            event = parse_text_frame(await connection.recv())
            assert isinstance(event, EventMessage)
            received.append(event)

    async with serve(handler, "127.0.0.1", 0) as server:
        port = server.sockets[0].getsockname()[1]
        simulator = DeviceSimulator(
            SimulatorConfig(
                bridge_url=f"ws://127.0.0.1:{port}/v1/device/ws",
                device_id="sim-001",
                token="test-device-token",  # pragma: allowlist secret
            )
        )
        await simulator.send_events(
            (
                simulator.event_message("touch.tap", {"x": 100, "y": 120}),
                simulator.event_message("battery.changed", {"percent": 75, "charging": False}),
                simulator.event_message("wifi.changed", {"connected": True, "rssi_dbm": -55}),
            )
        )

    assert [event.payload.name for event in received] == [
        "touch.tap",
        "battery.changed",
        "wifi.changed",
    ]


@pytest.mark.asyncio
async def test_simulator_injects_duplicate_fault_frames_after_handshake() -> None:
    received: list[str | bytes] = []

    async def handler(connection: ServerConnection) -> None:
        hello = parse_text_frame(await connection.recv())
        assert isinstance(hello, HelloMessage)
        await connection.send(
            HelloAckMessage.model_validate(
                {
                    "v": 1,
                    "type": "hello_ack",
                    "message_id": "519a16ce-3a07-4ab6-9767-f39bcc096cb8",
                    "sent_at_ms": 1,
                    "payload": {
                        "connection_id": "79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc",
                        "capture_protocol_version": 2,
                        "selected_protocol_version": 1,
                        "heartbeat_interval_ms": 15_000,
                        "max_command_timeout_ms": 5_000,
                        "server_version": "0.1.0",
                    },
                }
            ).model_dump_json()
        )
        received.extend((await connection.recv(), await connection.recv()))

    async with serve(handler, "127.0.0.1", 0) as server:
        port = server.sockets[0].getsockname()[1]
        simulator = DeviceSimulator(
            SimulatorConfig(
                bridge_url=f"ws://127.0.0.1:{port}/v1/device/ws",
                device_id="sim-001",
                token="test-device-token",  # pragma: allowlist secret
            )
        )
        await simulator.run_fault(SimulatorFault.DUPLICATE_MESSAGE)

    assert len(received) == 2
    assert received[0] == received[1]
