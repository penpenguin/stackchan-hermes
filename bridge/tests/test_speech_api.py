from __future__ import annotations

from asyncio import wait_for
from dataclasses import replace
from typing import cast
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import WebSocket
from stackchan_bridge.control.application import create_control_app
from stackchan_bridge.device_gateway.application import DeviceRegistry
from stackchan_bridge.turns.coordinator import TurnTrigger

from .test_control_api import LoopbackCommandWebSocket
from .test_speech import finished, make_service


@pytest.fixture
async def speech_api():
    service, coordinator, registry, adapter, player = await make_service()
    connection = registry.get_connection("sim-001")
    socket = LoopbackCommandWebSocket(registry, connection.connection_id)
    await registry.register(replace(connection, websocket=cast(WebSocket, socket)))
    app = create_control_app(registry, turn_coordinator=coordinator, speech_turn_service=service)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://control"
        ) as client:
            yield client, service, coordinator, registry, adapter, player, socket
    finally:
        await service.aclose()


@pytest.mark.asyncio
async def test_api_accepts_background_speech_and_reports_completion(speech_api) -> None:
    client, service, _, _, adapter, _, _ = speech_api
    adapter.release.clear()
    response = await client.post(
        "/v1/control/devices/sim-001/speech", json={"text": "通知します。"}
    )
    assert response.status_code == 202
    accepted = response.json()
    assert accepted["state"] == "ACCEPTED"
    await wait_for(adapter.started.wait(), 1)
    path = f"/v1/control/devices/sim-001/speech/{accepted['turn_id']}"
    assert (await client.get(path)).json()["state"] == "RUNNING"
    adapter.release.set()
    await finished(service, UUID(accepted["turn_id"]))
    result = await client.get(path)
    assert result.status_code == 200
    assert result.json()["state"] == "COMPLETED"
    assert result.json()["error_code"] is None
    assert "通知" not in result.text


@pytest.mark.asyncio
async def test_api_speech_can_be_cancelled_with_existing_endpoint(speech_api) -> None:
    client, service, coordinator, _, adapter, _, socket = speech_api
    adapter.release.clear()
    accepted = (
        await client.post("/v1/control/devices/sim-001/speech", json={"text": "通知"})
    ).json()
    response = await client.post(
        "/v1/control/devices/sim-001/speech/cancel", json={"turn_id": accepted["turn_id"]}
    )
    assert response.status_code == 200
    assert (await finished(service, UUID(accepted["turn_id"]))).state == "CANCELLED"
    assert coordinator.current("sim-001") is None
    assert socket.commands[0].turn_id == UUID(accepted["turn_id"])
    assert socket.commands[0].payload.name == "speech.cancel"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text", ["", " \n", "あ" * 1001, 42], ids=["empty", "blank", "too-long", "number"]
)
async def test_api_rejects_invalid_text_without_side_effects(speech_api, text: object) -> None:
    client, _, coordinator, _, adapter, _, _ = speech_api
    response = await client.post("/v1/control/devices/sim-001/speech", json={"text": text})
    assert response.status_code == 422
    assert coordinator.current("sim-001") is None
    assert adapter.texts == []


@pytest.mark.asyncio
async def test_api_speech_errors_are_typed(speech_api) -> None:
    client, service, coordinator, registry, adapter, _, _ = speech_api
    offline = await client.post("/v1/control/devices/offline/speech", json={"text": "通知"})
    assert (offline.status_code, offline.json()["error"]["code"]) == (404, "DEVICE_NOT_CONNECTED")
    connection = registry.get_connection("sim-001")
    connection.hello.payload.capabilities.speaker = False
    unsupported = await client.post("/v1/control/devices/sim-001/speech", json={"text": "通知"})
    assert (unsupported.status_code, unsupported.json()["error"]["code"]) == (
        409,
        "CAPABILITY_UNAVAILABLE",
    )
    connection.hello.payload.capabilities.speaker = True
    turn = await coordinator.begin("sim-001", trigger=TurnTrigger.TOUCH)
    busy = await client.post("/v1/control/devices/sim-001/speech", json={"text": "通知"})
    assert (busy.status_code, busy.json()["error"]["code"]) == (409, "TURN_BUSY")
    assert coordinator.current("sim-001") is turn
    assert adapter.texts == []
    await coordinator.cancel_turn("sim-001", turn.turn_id, reason="test_cleanup")
    await service.aclose()
    closed = await client.post("/v1/control/devices/sim-001/speech", json={"text": "通知"})
    assert (closed.status_code, closed.json()["error"]["code"]) == (503, "SPEECH_UNAVAILABLE")


@pytest.mark.asyncio
async def test_api_status_handles_invalid_missing_and_other_device_ids(speech_api) -> None:
    client, service, _, _, _, _, _ = speech_api
    accepted = await service.start("sim-001", text="通知")
    await finished(service, accepted.turn_id)
    assert (await client.get("/v1/control/devices/sim-001/speech/not-a-uuid")).status_code == 422
    assert (
        await client.post("/v1/control/devices/bad!id/speech", json={"text": "通知"})
    ).status_code == 422
    for device_id, turn_id in [("other-device", accepted.turn_id), ("sim-001", uuid4())]:
        response = await client.get(f"/v1/control/devices/{device_id}/speech/{turn_id}")
        assert (response.status_code, response.json()["error"]["code"]) == (404, "SPEECH_NOT_FOUND")


@pytest.mark.asyncio
async def test_api_reports_unconfigured_speech_service() -> None:
    app = create_control_app(DeviceRegistry(command_timeout_seconds=1))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://control"
    ) as client:
        for response in [
            await client.post("/v1/control/devices/sim-001/speech", json={"text": "通知"}),
            await client.get(f"/v1/control/devices/sim-001/speech/{uuid4()}"),
        ]:
            assert (response.status_code, response.json()["error"]["code"]) == (
                503,
                "SPEECH_UNAVAILABLE",
            )
