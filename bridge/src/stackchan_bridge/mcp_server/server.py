"""Safe MCP tools backed only by the loopback Control API interface."""

from __future__ import annotations

import base64
import json
from typing import Annotated, Any, Literal, Protocol
from uuid import UUID

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ImageContent, TextContent
from pydantic import BaseModel, ConfigDict, Field

from stackchan_bridge.motion import K151_MOTION_SAFETY
from stackchan_bridge.protocol.models import DeviceId
from stackchan_bridge.speech_models import SpeechText


class StackChanControl(Protocol):
    async def get_device(self, device_id: str) -> dict[str, Any]: ...

    async def command(
        self,
        device_id: str,
        name: str,
        args: dict[str, object],
        *,
        turn_id: str | None = None,
    ) -> dict[str, Any]: ...

    async def cancel_speech(self, device_id: str, *, turn_id: str) -> dict[str, Any]: ...

    async def speak(self, device_id: str, *, text: str) -> dict[str, Any]: ...

    async def get_speech_status(self, device_id: str, *, turn_id: str) -> dict[str, Any]: ...

    async def get_touch_state(self, device_id: str) -> dict[str, Any]: ...

    async def take_photo(self, device_id: str, *, quality: int) -> dict[str, Any]: ...

    async def get_capture(self, local_url: str) -> tuple[bytes, str]: ...

    async def vision(
        self,
        device_id: str,
        *,
        question: str,
        quality: int,
    ) -> dict[str, Any]: ...


class RgbColor(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    r: Annotated[int, Field(ge=0, le=255)]
    g: Annotated[int, Field(ge=0, le=255)]
    b: Annotated[int, Field(ge=0, le=255)]


def create_mcp_server(control: StackChanControl) -> MCPServer[None]:
    """Register the initial non-destructive StackChan tool set."""

    server: MCPServer[None] = MCPServer(
        "stackchan-hermes",
        instructions="Control an authenticated StackChan through its loopback Bridge API.",
    )

    @server.tool()
    async def stackchan_get_status(device_id: str) -> dict[str, Any]:
        device = await control.get_device(device_id)
        status = await control.command(device_id, "device.get_status", {})
        return {**device, "status": status.get("result", {})}

    @server.tool()
    async def stackchan_take_photo(
        device_id: str,
        question: Annotated[str | None, Field(max_length=1_000)] = None,
        quality: Annotated[int, Field(ge=10, le=95)] = 80,
    ) -> list[TextContent | ImageContent]:
        metadata = await control.take_photo(device_id, quality=quality)
        if question:
            metadata = {**metadata, "question": question}
        local_url = metadata.get("local_url")
        content: list[TextContent | ImageContent] = [
            TextContent(text=json.dumps(metadata, ensure_ascii=False, sort_keys=True))
        ]
        if isinstance(local_url, str):
            try:
                image, mime_type = await control.get_capture(local_url)
            except ToolError:
                fallback: dict[str, Any] = {
                    **metadata,
                    "image_fallback": "Use the loopback local_url.",
                }
                if question:
                    try:
                        fallback["vision"] = await control.vision(
                            device_id,
                            question=question,
                            quality=quality,
                        )
                    except ToolError as error:
                        fallback["vision_fallback_error"] = str(error)
                content[0] = TextContent(
                    text=json.dumps(
                        fallback,
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                )
            else:
                content.append(
                    ImageContent(
                        data=base64.b64encode(image).decode("ascii"),
                        mime_type=mime_type,
                    )
                )
        return content

    @server.tool()
    async def stackchan_set_head_angles(
        device_id: str,
        yaw: Annotated[
            float,
            Field(
                ge=K151_MOTION_SAFETY.yaw_minimum_degrees,
                le=K151_MOTION_SAFETY.yaw_maximum_degrees,
            ),
        ],
        pitch: Annotated[
            float,
            Field(
                ge=K151_MOTION_SAFETY.pitch_minimum_degrees,
                le=K151_MOTION_SAFETY.pitch_maximum_degrees,
            ),
        ],
        speed: Annotated[
            int | None,
            Field(
                ge=K151_MOTION_SAFETY.speed_minimum,
                le=K151_MOTION_SAFETY.speed_maximum,
            ),
        ] = None,
    ) -> dict[str, Any]:
        args: dict[str, object] = {"yaw": yaw, "pitch": pitch}
        if speed is not None:
            args["speed"] = speed
        return await control.command(device_id, "head.set_angles", args)

    @server.tool()
    async def stackchan_home_head(
        device_id: str,
        speed: Annotated[
            int | None,
            Field(
                ge=K151_MOTION_SAFETY.speed_minimum,
                le=K151_MOTION_SAFETY.speed_maximum,
            ),
        ] = None,
    ) -> dict[str, Any]:
        return await control.command(
            device_id,
            "head.home",
            {} if speed is None else {"speed": speed},
        )

    @server.tool()
    async def stackchan_set_expression(
        device_id: str,
        expression: Literal["idle", "happy", "thinking", "sad", "surprised", "embarrassed"],
    ) -> dict[str, Any]:
        return await control.command(
            device_id,
            "avatar.set_expression",
            {"expression": expression},
        )

    @server.tool()
    async def stackchan_set_leds(
        device_id: str,
        mode: Literal["all", "single", "array", "clear"],
        r: Annotated[int | None, Field(ge=0, le=255)] = None,
        g: Annotated[int | None, Field(ge=0, le=255)] = None,
        b: Annotated[int | None, Field(ge=0, le=255)] = None,
        index: Annotated[int | None, Field(ge=0, le=255)] = None,
        colors: Annotated[list[RgbColor] | None, Field(max_length=256)] = None,
    ) -> dict[str, Any]:
        if mode == "clear":
            return await control.command(device_id, "led.clear", {})
        if mode == "array":
            if not colors:
                raise ToolError("INVALID_ARGUMENT: colors are required for array mode")
            device = await control.get_device(device_id)
            capabilities = device.get("capabilities")
            led_count = capabilities.get("led_count") if isinstance(capabilities, dict) else None
            if (
                not isinstance(led_count, int)
                or isinstance(led_count, bool)
                or len(colors) > led_count
            ):
                raise ToolError("INVALID_ARGUMENT: colors exceed connected device LED count")
            results = []
            for color_index, color in enumerate(colors):
                result = await control.command(
                    device_id,
                    "led.set",
                    {"index": color_index, **color.model_dump()},
                )
                results.append(result)
                if result.get("ok") is not True:
                    return {"ok": False, "results": results}
            return {"ok": True, "results": results}
        if r is None or g is None or b is None:
            raise ToolError("INVALID_ARGUMENT: r, g, and b are required")
        if mode == "all":
            return await control.command(device_id, "led.set_all", {"r": r, "g": g, "b": b})
        if index is None:
            raise ToolError("INVALID_ARGUMENT: index is required for single mode")
        return await control.command(
            device_id,
            "led.set",
            {"index": index, "r": r, "g": g, "b": b},
        )

    @server.tool()
    async def stackchan_display_text(
        device_id: str,
        text: Annotated[str, Field(min_length=1, max_length=256)],
        duration_ms: Annotated[int, Field(ge=100, le=30_000)] = 5_000,
        priority: Annotated[int, Field(ge=0, le=10)] = 0,
    ) -> dict[str, Any]:
        return await control.command(
            device_id,
            "display.show_text",
            {"text": text, "duration_ms": duration_ms, "priority": priority},
        )

    @server.tool()
    async def stackchan_set_volume(
        device_id: str,
        volume: Annotated[int, Field(ge=0, le=100)],
    ) -> dict[str, Any]:
        return await control.command(device_id, "audio.set_volume", {"volume": volume})

    @server.tool()
    async def stackchan_speak(device_id: DeviceId, text: SpeechText) -> dict[str, Any]:
        """Speak up to 1000 characters verbatim using the Bridge's configured voice.

        Returns ACCEPTED and turn_id immediately, before synthesis or playback completes.
        Rejects with TURN_BUSY during any active voice, vision, or speech turn, including
        a voice conversation awaiting this tool. Use stackchan_get_speech_status to check
        completion or failure, and stackchan_cancel_speech to stop the returned turn_id.
        """
        return await control.speak(device_id, text=text)

    @server.tool()
    async def stackchan_get_speech_status(device_id: DeviceId, turn_id: str) -> dict[str, Any]:
        """Check a direct speech request, including its terminal state and error_code.

        Completion means Bridge streaming and playback grace time ended. Results remain
        available after device disconnect; history holds at most 128 completed requests
        for 10 minutes and is lost on Bridge restart.
        """
        try:
            validated_turn_id = str(UUID(turn_id))
        except ValueError as error:
            raise ToolError("INVALID_ARGUMENT: turn_id must be a UUID") from error
        return await control.get_speech_status(device_id, turn_id=validated_turn_id)

    @server.tool()
    async def stackchan_cancel_speech(device_id: str, turn_id: str) -> dict[str, Any]:
        try:
            validated_turn_id = str(UUID(turn_id))
        except ValueError as error:
            raise ToolError("INVALID_ARGUMENT: turn_id must be a UUID") from error
        return await control.cancel_speech(device_id, turn_id=validated_turn_id)

    @server.tool()
    async def stackchan_get_touch_state(device_id: str) -> dict[str, Any]:
        return await control.get_touch_state(device_id)

    return server
