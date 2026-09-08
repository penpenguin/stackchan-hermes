from __future__ import annotations

import json
from asyncio import CancelledError, Event, create_task, wait_for
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest
from fastapi import WebSocket
from stackchan_bridge.captures.coordinator import (
    CaptureCommandFailedError,
    CaptureCoordinator,
)
from stackchan_bridge.captures.store import CaptureStore, CaptureValidationError
from stackchan_bridge.device_gateway.application import DeviceConnection, DeviceRegistry
from stackchan_bridge.protocol.models import CommandMessage, CommandResultMessage
from stackchan_simulator.fixtures import generate_synthetic_jpeg

from .test_control_api import simulator_hello


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
        record = self.store.get(UUID(str(args["capture_id"])))
        assert record is not None
        self.store.complete(
            record.capture_id,
            device_id="sim-001",
            ok=True,
            digest=record.sha256,
            size_bytes=record.size_bytes,
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


class AcknowledgingCaptureWebSocket:
    def __init__(self, registry: DeviceRegistry, connection_id: UUID) -> None:
        self.registry = registry
        self.connection_id = connection_id
        self.command: CommandMessage | None = None
        self.sent = Event()

    async def send_text(self, data: str) -> None:
        command = CommandMessage.model_validate(json.loads(data))
        self.command = command
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
        self.sent.set()


@pytest.mark.asyncio
async def test_capture_coordinator_reserves_commands_and_waits_for_upload(tmp_path: Path) -> None:
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
    coordinator = CaptureCoordinator(registry, store, timeout_seconds=1)

    record = await coordinator.take_photo("sim-001", quality=75)

    assert websocket.command is not None
    assert websocket.command.payload.name == "camera.capture"
    assert websocket.command.payload.args.quality == 75
    assert websocket.command.payload.args.capture_id == record.capture_id
    assert (record.width, record.height) == (320, 240)


@pytest.mark.asyncio
async def test_missing_command_ack_does_not_override_saved_and_completed_capture(
    tmp_path: Path,
) -> None:
    class MissingAck(UploadingCaptureWebSocket):
        async def send_text(self, data: str) -> None:
            command = CommandMessage.model_validate_json(data)
            if command.payload.name != "camera.capture":
                return
            record = self.store.save(
                command.payload.args.capture_id,
                device_id="sim-001",
                content_type="image/jpeg",
                body=generate_synthetic_jpeg(),
            )
            self.store.complete(
                record.capture_id,
                device_id="sim-001",
                ok=True,
                digest=record.sha256,
                size_bytes=record.size_bytes,
            )

    store = CaptureStore(directory=tmp_path, ttl_seconds=600, max_bytes=2097152)
    registry = DeviceRegistry(command_timeout_seconds=0.01)
    connection_id = UUID("79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc")
    ws = MissingAck(registry, connection_id, store)
    await registry.register(
        DeviceConnection(
            connection_id=connection_id,
            device_id="sim-001",
            hello=simulator_hello(),
            websocket=cast(WebSocket, ws),
        )
    )
    record = await CaptureCoordinator(registry, store, timeout_seconds=0.1).take_photo("sim-001")
    assert store.get(record.capture_id) == record


@pytest.mark.asyncio
async def test_capture_coordinator_cancellation_invalidates_the_reservation(
    tmp_path: Path,
) -> None:
    store = CaptureStore(directory=tmp_path, ttl_seconds=600, max_bytes=2_097_152)
    registry = DeviceRegistry(command_timeout_seconds=5)
    connection_id = UUID("79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc")
    websocket = AcknowledgingCaptureWebSocket(registry, connection_id)
    await registry.register(
        DeviceConnection(
            connection_id=connection_id,
            device_id="sim-001",
            hello=simulator_hello(),
            websocket=cast(WebSocket, websocket),
        )
    )
    coordinator = CaptureCoordinator(registry, store, timeout_seconds=30)
    task = create_task(coordinator.take_photo("sim-001"))
    await websocket.sent.wait()

    task.cancel()
    with pytest.raises(CancelledError):
        await task

    assert websocket.command is not None
    capture_id = websocket.command.payload.args.capture_id
    with pytest.raises(CaptureValidationError) as error:
        store.save(
            capture_id,
            device_id="sim-001",
            content_type="image/jpeg",
            body=generate_synthetic_jpeg(),
        )
    assert error.value.code == "CAPTURE_NOT_FOUND"


@pytest.mark.asyncio
async def test_reported_camera_failure_interrupts_the_owned_upload_wait(tmp_path: Path) -> None:
    store = CaptureStore(directory=tmp_path, ttl_seconds=600, max_bytes=2_097_152)
    registry = DeviceRegistry(command_timeout_seconds=5)
    connection_id = UUID("79e1d2f4-e7d9-4c44-b560-af9ed6b0cacc")
    websocket = AcknowledgingCaptureWebSocket(registry, connection_id)
    await registry.register(
        DeviceConnection(
            connection_id=connection_id,
            device_id="sim-001",
            hello=simulator_hello(),
            websocket=cast(WebSocket, websocket),
        )
    )
    coordinator = CaptureCoordinator(registry, store, timeout_seconds=30)
    task = create_task(coordinator.take_photo("sim-001"))
    await websocket.sent.wait()
    assert websocket.command is not None
    capture_id = websocket.command.payload.args.capture_id

    try:
        assert coordinator.report_failure("sim-001", capture_id)
        with pytest.raises(CaptureCommandFailedError):
            await wait_for(task, timeout=0.1)
    finally:
        if not task.done():
            task.cancel()
            with pytest.raises(CancelledError):
                await task
