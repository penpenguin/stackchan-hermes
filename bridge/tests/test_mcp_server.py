from __future__ import annotations

from typing import Any

import pytest
from mcp.server.mcpserver.exceptions import ToolError
from stackchan_bridge.mcp_server.server import create_mcp_server


class FakeControlClient:
    def __init__(self) -> None:
        self.commands: list[tuple[str, str, dict[str, object], str | None]] = []
        self.speech_cancellations: list[tuple[str, str]] = []
        self.touch_requests: list[str] = []
        self.speeches: list[tuple[str, str]] = []

    async def speak(self, device_id: str, *, text: str) -> dict[str, Any]:
        self.speeches.append((device_id, text))
        return {"turn_id": "0819e40d-71f3-4d44-9a31-928358122a83", "state": "ACCEPTED"}

    async def get_speech_status(self, device_id: str, *, turn_id: str) -> dict[str, Any]:
        return {"turn_id": turn_id, "state": "COMPLETED", "error_code": None}

    async def get_device(self, device_id: str) -> dict[str, Any]:
        if device_id == "offline":
            raise ToolError("DEVICE_NOT_CONNECTED")
        return {
            "device_id": device_id,
            "capabilities": {"head": True, "led_count": 12},
        }

    async def command(
        self,
        device_id: str,
        name: str,
        args: dict[str, object],
        *,
        turn_id: str | None = None,
    ) -> dict[str, Any]:
        self.commands.append((device_id, name, args, turn_id))
        return {"ok": True, "result": args}

    async def cancel_speech(self, device_id: str, *, turn_id: str) -> dict[str, Any]:
        self.speech_cancellations.append((device_id, turn_id))
        return {"ok": True, "result": {"cancelled": True}}

    async def get_touch_state(self, device_id: str) -> dict[str, Any]:
        self.touch_requests.append(device_id)
        return {"touch": None}

    async def take_photo(self, device_id: str, *, quality: int) -> dict[str, Any]:
        raise AssertionError("not used")

    async def get_capture(self, local_url: str) -> tuple[bytes, str]:
        raise AssertionError("not used")

    async def vision(
        self,
        device_id: str,
        *,
        question: str,
        quality: int,
    ) -> dict[str, Any]:
        raise AssertionError("not used")


class FakePhotoControlClient(FakeControlClient):
    async def take_photo(self, device_id: str, *, quality: int) -> dict[str, Any]:
        assert (device_id, quality) == ("sim-001", 75)
        return {
            "capture_id": "3d27c065-15a7-4f85-87ba-df14912a8098",
            "mime_type": "image/jpeg",
            "width": 320,
            "height": 240,
            "sha256": "a" * 64,
            "local_url": "/v1/control/captures/3d27c065-15a7-4f85-87ba-df14912a8098",
            "expires_at": 1234.0,
        }

    async def get_capture(self, local_url: str) -> tuple[bytes, str]:
        return b"\xff\xd8\xfftest\xff\xd9", "image/jpeg"


class RichStatusControlClient(FakeControlClient):
    async def get_touch_state(self, device_id: str) -> dict[str, Any]:
        self.touch_requests.append(device_id)
        return {"touch": {"name": "touch.tap", "data": {"x": 120, "y": 80}}}

    async def command(
        self,
        device_id: str,
        name: str,
        args: dict[str, object],
        *,
        turn_id: str | None = None,
    ) -> dict[str, Any]:
        self.commands.append((device_id, name, args, turn_id))
        if name == "device.get_status":
            return {
                "ok": True,
                "result": {
                    "touch": {"name": "touch.tap", "x": 120, "y": 80},
                    "volume": 42,
                },
            }
        return {"ok": True, "result": args}


class FallbackPhotoControlClient(FakePhotoControlClient):
    def __init__(self) -> None:
        super().__init__()
        self.vision_calls: list[tuple[str, str, int]] = []

    async def get_capture(self, local_url: str) -> tuple[bytes, str]:
        raise ToolError("IMAGE_UNAVAILABLE")

    async def vision(
        self,
        device_id: str,
        *,
        question: str,
        quality: int,
    ) -> dict[str, Any]:
        self.vision_calls.append((device_id, question, quality))
        return {
            "turn_id": "a74e6e0a-dc71-4828-a274-a9b6b21682d4",
            "state": "COMPLETED",
            "capture_id": "3d27c065-15a7-4f85-87ba-df14912a8098",
        }


@pytest.mark.asyncio
async def test_mcp_server_registers_safe_tools_and_maps_head_command() -> None:
    control = FakeControlClient()
    server = create_mcp_server(control)

    tools = await server.list_tools()
    result = await server.call_tool(
        "stackchan_set_head_angles",
        {"device_id": "sim-001", "yaw": 15, "pitch": 40, "speed": 30},
    )

    assert {tool.name for tool in tools} == {
        "stackchan_get_status",
        "stackchan_take_photo",
        "stackchan_set_head_angles",
        "stackchan_home_head",
        "stackchan_set_expression",
        "stackchan_set_leds",
        "stackchan_display_text",
        "stackchan_set_volume",
        "stackchan_cancel_speech",
        "stackchan_get_touch_state",
        "stackchan_speak",
        "stackchan_get_speech_status",
    }
    assert control.commands == [
        (
            "sim-001",
            "head.set_angles",
            {"yaw": 15.0, "pitch": 40.0, "speed": 30},
            None,
        )
    ]
    assert result.is_error is False
    assert result.structured_content == {
        "ok": True,
        "result": {"yaw": 15.0, "pitch": 40.0, "speed": 30},
    }


@pytest.mark.asyncio
async def test_mcp_speech_tools_expose_bounded_text_and_return_background_status() -> None:
    control = FakeControlClient()
    server = create_mcp_server(control)
    tools = {tool.name: tool for tool in await server.list_tools()}
    assert tools["stackchan_speak"].input_schema["properties"]["text"]["maxLength"] == 1000
    result = await server.call_tool(
        "stackchan_speak", {"device_id": "sim-001", "text": " 通知です。 "}
    )
    assert result.structured_content["state"] == "ACCEPTED"
    assert control.speeches == [("sim-001", "通知です。")]
    status = await server.call_tool(
        "stackchan_get_speech_status",
        {
            "device_id": "sim-001",
            "turn_id": result.structured_content["turn_id"],
        },
    )
    assert status.structured_content["state"] == "COMPLETED"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "arguments",
    [
        {"device_id": "sim-001", "text": " \n"},
        {"device_id": "sim-001", "text": "あ" * 1001},
        {"device_id": "../bad", "text": "通知"},
    ],
    ids=["blank", "too-long", "invalid-device"],
)
async def test_mcp_rejects_invalid_speech_before_control_call(arguments: dict[str, object]) -> None:
    control = FakeControlClient()
    server = create_mcp_server(control)
    with pytest.raises((ToolError, ValueError)):
        await server.call_tool("stackchan_speak", arguments)
    assert control.speeches == []


@pytest.mark.asyncio
async def test_mcp_rejects_invalid_speech_status_turn() -> None:
    with pytest.raises((ToolError, ValueError)):
        await create_mcp_server(FakeControlClient()).call_tool(
            "stackchan_get_speech_status", {"device_id": "sim-001", "turn_id": "bad"}
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool_name", "arguments"),
    [
        (
            "stackchan_set_head_angles",
            {"device_id": "sim-001", "yaw": -45.1, "pitch": 45, "speed": 15},
        ),
        (
            "stackchan_set_head_angles",
            {"device_id": "sim-001", "yaw": 45.1, "pitch": 45, "speed": 15},
        ),
        (
            "stackchan_set_head_angles",
            {"device_id": "sim-001", "yaw": 0, "pitch": 4.9, "speed": 15},
        ),
        (
            "stackchan_set_head_angles",
            {"device_id": "sim-001", "yaw": 0, "pitch": 85.1, "speed": 15},
        ),
        (
            "stackchan_set_head_angles",
            {"device_id": "sim-001", "yaw": 0, "pitch": 45, "speed": 31},
        ),
        ("stackchan_home_head", {"device_id": "sim-001", "speed": 31}),
    ],
)
async def test_mcp_head_tools_reject_values_outside_the_k151_profile(
    tool_name: str,
    arguments: dict[str, object],
) -> None:
    control = FakeControlClient()
    server = create_mcp_server(control)

    with pytest.raises(ToolError):
        await server.call_tool(tool_name, arguments)

    assert control.commands == []


@pytest.mark.asyncio
async def test_mcp_led_array_rejects_more_colors_than_the_connected_device() -> None:
    class TwoLedControlClient(FakeControlClient):
        async def get_device(self, device_id: str) -> dict[str, Any]:
            return {"device_id": device_id, "capabilities": {"led_count": 2}}

    control = TwoLedControlClient()
    server = create_mcp_server(control)

    with pytest.raises(ToolError, match="connected device LED count"):
        await server.call_tool(
            "stackchan_set_leds",
            {
                "device_id": "sim-001",
                "mode": "array",
                "colors": [
                    {"r": 1, "g": 2, "b": 3},
                    {"r": 4, "g": 5, "b": 6},
                    {"r": 7, "g": 8, "b": 9},
                ],
            },
        )

    assert control.commands == []


@pytest.mark.asyncio
async def test_mcp_led_array_stops_and_reports_a_negative_device_result() -> None:
    class RejectingLedControlClient(FakeControlClient):
        async def command(
            self,
            device_id: str,
            name: str,
            args: dict[str, object],
            *,
            turn_id: str | None = None,
        ) -> dict[str, Any]:
            result = await super().command(
                device_id,
                name,
                args,
                turn_id=turn_id,
            )
            if name == "led.set" and args.get("index") == 1:
                return {"ok": False, "error": {"code": "INVALID_ARGUMENT"}}
            return result

    control = RejectingLedControlClient()
    server = create_mcp_server(control)

    result = await server.call_tool(
        "stackchan_set_leds",
        {
            "device_id": "sim-001",
            "mode": "array",
            "colors": [
                {"r": 1, "g": 2, "b": 3},
                {"r": 4, "g": 5, "b": 6},
                {"r": 7, "g": 8, "b": 9},
            ],
        },
    )

    assert result.structured_content is not None
    assert result.structured_content["ok"] is False
    assert [command[2]["index"] for command in control.commands] == [0, 1]


@pytest.mark.asyncio
async def test_mcp_photo_returns_metadata_and_image_while_offline_is_typed_error() -> None:
    server = create_mcp_server(FakePhotoControlClient())

    photo = await server.call_tool(
        "stackchan_take_photo",
        {"device_id": "sim-001", "quality": 75},
    )
    with pytest.raises(ToolError) as offline:
        await server.call_tool(
            "stackchan_get_status",
            {"device_id": "offline"},
        )

    assert photo.is_error is False
    assert [item.type for item in photo.content] == ["text", "image"]
    assert photo.content[1].mime_type == "image/jpeg"  # type: ignore[union-attr]
    assert "DEVICE_NOT_CONNECTED" in str(offline.value)


@pytest.mark.asyncio
async def test_mcp_server_maps_all_non_destructive_body_and_status_tools() -> None:
    control = RichStatusControlClient()
    server = create_mcp_server(control)
    turn_id = "0819e40d-71f3-4d44-9a31-928358122a83"

    status = await server.call_tool("stackchan_get_status", {"device_id": "sim-001"})
    touch = await server.call_tool("stackchan_get_touch_state", {"device_id": "sim-001"})
    await server.call_tool("stackchan_home_head", {"device_id": "sim-001", "speed": 20})
    await server.call_tool(
        "stackchan_set_expression",
        {"device_id": "sim-001", "expression": "thinking"},
    )
    await server.call_tool(
        "stackchan_set_leds",
        {"device_id": "sim-001", "mode": "all", "r": 1, "g": 2, "b": 3},
    )
    await server.call_tool(
        "stackchan_set_leds",
        {
            "device_id": "sim-001",
            "mode": "single",
            "index": 2,
            "r": 4,
            "g": 5,
            "b": 6,
        },
    )
    await server.call_tool(
        "stackchan_set_leds",
        {
            "device_id": "sim-001",
            "mode": "array",
            "colors": [{"r": 7, "g": 8, "b": 9}, {"r": 10, "g": 11, "b": 12}],
        },
    )
    await server.call_tool(
        "stackchan_set_leds",
        {"device_id": "sim-001", "mode": "clear"},
    )
    await server.call_tool(
        "stackchan_display_text",
        {"device_id": "sim-001", "text": "こんにちは", "duration_ms": 2_000, "priority": 1},
    )
    await server.call_tool(
        "stackchan_set_volume",
        {"device_id": "sim-001", "volume": 42},
    )
    await server.call_tool(
        "stackchan_cancel_speech",
        {"device_id": "sim-001", "turn_id": turn_id},
    )

    assert status.structured_content is not None
    assert status.structured_content["status"]["volume"] == 42
    assert touch.structured_content == {"touch": {"name": "touch.tap", "data": {"x": 120, "y": 80}}}
    assert [call[1] for call in control.commands] == [
        "device.get_status",
        "head.home",
        "avatar.set_expression",
        "led.set_all",
        "led.set",
        "led.set",
        "led.set",
        "led.clear",
        "display.show_text",
        "audio.set_volume",
    ]
    assert control.touch_requests == ["sim-001"]
    assert control.speech_cancellations == [("sim-001", turn_id)]


@pytest.mark.asyncio
async def test_mcp_photo_returns_explicit_fallback_when_image_block_is_unavailable() -> None:
    control = FallbackPhotoControlClient()
    server = create_mcp_server(control)

    photo = await server.call_tool(
        "stackchan_take_photo",
        {"device_id": "sim-001", "quality": 75, "question": "何が見えますか"},
    )

    assert [item.type for item in photo.content] == ["text"]
    assert "image_fallback" in photo.content[0].text  # type: ignore[union-attr]
    assert "何が見えますか" in photo.content[0].text  # type: ignore[union-attr]
    assert '"state": "COMPLETED"' in photo.content[0].text  # type: ignore[union-attr]
    assert control.vision_calls == [("sim-001", "何が見えますか", 75)]
