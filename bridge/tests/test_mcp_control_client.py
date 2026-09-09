from __future__ import annotations

import httpx
import pytest
from mcp.server.mcpserver.exceptions import ToolError
from stackchan_bridge.mcp_server.control_client import ControlApiClient


@pytest.mark.asyncio
async def test_speech_client_maps_async_start_status_and_safe_errors() -> None:
    turn_id = "0819e40d-71f3-4d44-9a31-928358122a83"
    calls = []

    async def handle(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert request.extensions["timeout"]["read"] == 10
        if "busy" in request.url.path:
            return httpx.Response(
                409, json={"error": {"code": "TURN_BUSY", "message": "private text"}}
            )
        if request.method == "POST":
            assert request.url.path == "/v1/control/devices/sim-001/speech"
            assert await request.aread() == '{"text":"通知です。"}'.encode()
            return httpx.Response(202, json={"turn_id": turn_id, "state": "ACCEPTED"})
        assert request.url.path == f"/v1/control/devices/sim-001/speech/{turn_id}"
        return httpx.Response(
            200, json={"turn_id": turn_id, "state": "FAILED", "error_code": "TTS_FAILED"}
        )

    control = ControlApiClient("http://127.0.0.1:8766", transport=httpx.MockTransport(handle))
    assert (await control.speak("sim-001", text="通知です。"))["state"] == "ACCEPTED"
    assert (await control.get_speech_status("sim-001", turn_id=turn_id))[
        "error_code"
    ] == "TTS_FAILED"
    with pytest.raises(ToolError, match="TURN_BUSY") as error:
        await control.speak("busy", text="通知")
    assert "private text" not in str(error.value)
    for invalid_device in ["../bad", "bad!id"]:
        with pytest.raises(ToolError, match="INVALID_DEVICE_ID"):
            await control.speak(invalid_device, text="通知")
    with pytest.raises(ToolError, match="INVALID_TURN_ID"):
        await control.get_speech_status("sim-001", turn_id="../bad")
    with pytest.raises(ToolError, match="INVALID_ARGUMENT"):
        await control.speak("sim-001", text=" \n")
    assert len(calls) == 3


@pytest.mark.asyncio
async def test_mcp_control_client_maps_commands_captures_and_safe_errors() -> None:
    private_message = "private-control-diagnostic"
    read_timeouts: dict[str, float | None] = {}

    async def handle(request: httpx.Request) -> httpx.Response:
        timeout = request.extensions.get("timeout", {})
        read_timeouts[request.url.path] = timeout.get("read")
        if request.url.path == "/v1/control/devices/offline":
            return httpx.Response(
                404,
                json={
                    "error": {
                        "code": "DEVICE_NOT_CONNECTED",
                        "message": private_message,
                    }
                },
            )
        if request.url.path.endswith("/commands"):
            assert await request.aread() == (
                b'{"name":"head.home","args":{"speed":30},"turn_id":null}'
            )
            return httpx.Response(200, json={"ok": True, "result": {"yaw": 0, "pitch": 0}})
        if request.url.path.endswith("/speech/cancel"):
            assert await request.aread() == (b'{"turn_id":"a74e6e0a-dc71-4828-a274-a9b6b21682d4"}')
            return httpx.Response(200, json={"ok": True, "result": {"cancelled": True}})
        if request.url.path.endswith("/captures"):
            return httpx.Response(
                201,
                json={
                    "capture_id": "3d27c065-15a7-4f85-87ba-df14912a8098",
                    "mime_type": "image/jpeg",
                    "width": 320,
                    "height": 240,
                    "sha256": "a" * 64,
                    "local_url": "/v1/control/captures/3d27c065-15a7-4f85-87ba-df14912a8098",
                    "expires_at": 1234.0,
                },
            )
        if request.url.path.endswith("/vision"):
            assert await request.aread() == ('{"question":"何が見えますか","quality":75}'.encode())
            return httpx.Response(
                200,
                json={
                    "turn_id": "a74e6e0a-dc71-4828-a274-a9b6b21682d4",
                    "state": "COMPLETED",
                    "capture_id": "3d27c065-15a7-4f85-87ba-df14912a8098",
                },
            )
        if request.url.path.startswith("/v1/control/captures/"):
            return httpx.Response(
                200,
                content=b"\xff\xd8\xfftest\xff\xd9",
                headers={"Content-Type": "image/jpeg"},
            )
        return httpx.Response(200, json={"device_id": "sim-001"})

    control = ControlApiClient(
        base_url="http://127.0.0.1:8766",
        transport=httpx.MockTransport(handle),
    )

    device = await control.get_device("sim-001")
    command = await control.command("sim-001", "head.home", {"speed": 30})
    cancelled = await control.cancel_speech(
        "sim-001",
        turn_id="a74e6e0a-dc71-4828-a274-a9b6b21682d4",
    )
    capture = await control.take_photo("sim-001", quality=80)
    vision = await control.vision("sim-001", question="何が見えますか", quality=75)
    jpeg, mime_type = await control.get_capture(capture["local_url"])
    with pytest.raises(ToolError) as error:
        await control.get_device("offline")

    assert device == {"device_id": "sim-001"}
    assert command["ok"] is True
    assert cancelled["result"] == {"cancelled": True}
    assert vision["state"] == "COMPLETED"
    assert mime_type == "image/jpeg"
    assert jpeg.startswith(b"\xff\xd8\xff")
    assert "DEVICE_NOT_CONNECTED" in str(error.value)
    assert private_message not in str(error.value)
    assert read_timeouts["/v1/control/devices/sim-001/commands"] >= 35
    assert read_timeouts["/v1/control/devices/sim-001/speech/cancel"] >= 35
    assert read_timeouts["/v1/control/devices/sim-001/captures"] >= 155
    assert read_timeouts["/v1/control/devices/sim-001/vision"] >= 2_100
