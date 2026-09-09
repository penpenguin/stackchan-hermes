"""Loopback-only HTTP client used by the standalone MCP process."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

import httpx
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import TypeAdapter, ValidationError

from stackchan_bridge.protocol.models import DeviceId
from stackchan_bridge.speech_models import SpeechRequest

_DEVICE_ID_ADAPTER: TypeAdapter[str] = TypeAdapter(DeviceId)
_SAFE_ERROR_CODE = re.compile(r"^[A-Z0-9][A-Z0-9_]{0,63}$")
_MAX_CAPTURE_RESPONSE_BYTES = 16_777_216
_COMMAND_READ_TIMEOUT_SECONDS = 35.0
_CAPTURE_READ_TIMEOUT_SECONDS = 155.0
# Covers maximum capture, Hermes, TTS, and ten sequential 120-second playback segments.
_VISION_READ_TIMEOUT_SECONDS = 2_100.0


@dataclass(slots=True)
class ControlApiClient:
    base_url: str
    timeout_seconds: float = 10
    transport: httpx.AsyncBaseTransport | None = field(default=None, repr=False)

    async def get_device(self, device_id: str) -> dict[str, Any]:
        selected_device = _validate_device_id(device_id)
        response = await self._request("GET", f"/v1/control/devices/{selected_device}")
        return _response_object(response)

    async def command(
        self,
        device_id: str,
        name: str,
        args: dict[str, object],
        *,
        turn_id: str | None = None,
    ) -> dict[str, Any]:
        selected_device = _validate_device_id(device_id)
        response = await self._request(
            "POST",
            f"/v1/control/devices/{selected_device}/commands",
            json={"name": name, "args": args, "turn_id": turn_id},
            read_timeout_seconds=_COMMAND_READ_TIMEOUT_SECONDS,
        )
        return _response_object(response)

    async def cancel_speech(self, device_id: str, *, turn_id: str) -> dict[str, Any]:
        selected_device = _validate_device_id(device_id)
        try:
            selected_turn_id = str(UUID(turn_id))
        except ValueError as error:
            raise ToolError("INVALID_TURN_ID") from error
        response = await self._request(
            "POST",
            f"/v1/control/devices/{selected_device}/speech/cancel",
            json={"turn_id": selected_turn_id},
            read_timeout_seconds=_COMMAND_READ_TIMEOUT_SECONDS,
        )
        return _response_object(response)

    async def speak(self, device_id: str, *, text: str) -> dict[str, Any]:
        selected_device = _validate_device_id(device_id)
        try:
            request = SpeechRequest(text=text)
        except ValidationError as error:
            raise ToolError("INVALID_ARGUMENT") from error
        response = await self._request(
            "POST",
            f"/v1/control/devices/{selected_device}/speech",
            json=request.model_dump(),
        )
        return _response_object(response)

    async def get_speech_status(self, device_id: str, *, turn_id: str) -> dict[str, Any]:
        selected_device = _validate_device_id(device_id)
        try:
            selected_turn_id = str(UUID(turn_id))
        except ValueError as error:
            raise ToolError("INVALID_TURN_ID") from error
        response = await self._request(
            "GET",
            f"/v1/control/devices/{selected_device}/speech/{selected_turn_id}",
        )
        return _response_object(response)

    async def get_touch_state(self, device_id: str) -> dict[str, Any]:
        selected_device = _validate_device_id(device_id)
        response = await self._request("GET", f"/v1/control/devices/{selected_device}/touch")
        return _response_object(response)

    async def take_photo(self, device_id: str, *, quality: int) -> dict[str, Any]:
        selected_device = _validate_device_id(device_id)
        response = await self._request(
            "POST",
            f"/v1/control/devices/{selected_device}/captures",
            json={"quality": quality},
            read_timeout_seconds=_CAPTURE_READ_TIMEOUT_SECONDS,
        )
        return _response_object(response)

    async def vision(
        self,
        device_id: str,
        *,
        question: str,
        quality: int,
    ) -> dict[str, Any]:
        selected_device = _validate_device_id(device_id)
        response = await self._request(
            "POST",
            f"/v1/control/devices/{selected_device}/vision",
            json={"question": question, "quality": quality},
            read_timeout_seconds=_VISION_READ_TIMEOUT_SECONDS,
        )
        return _response_object(response)

    async def get_capture(self, local_url: str) -> tuple[bytes, str]:
        prefix = "/v1/control/captures/"
        if not local_url.startswith(prefix):
            raise ToolError("INVALID_CAPTURE_URL")
        try:
            capture_id = UUID(local_url.removeprefix(prefix))
        except ValueError as error:
            raise ToolError("INVALID_CAPTURE_URL") from error
        canonical_path = f"{prefix}{capture_id}"
        if local_url != canonical_path:
            raise ToolError("INVALID_CAPTURE_URL")
        response = await self._request("GET", canonical_path)
        mime_type = response.headers.get("content-type", "").split(";", maxsplit=1)[0]
        if mime_type != "image/jpeg" or len(response.content) > _MAX_CAPTURE_RESPONSE_BYTES:
            raise ToolError("INVALID_CAPTURE_RESPONSE")
        return response.content, mime_type

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: object | None = None,
        read_timeout_seconds: float | None = None,
    ) -> httpx.Response:
        request_timeout = httpx.Timeout(
            self.timeout_seconds,
            read=read_timeout_seconds or self.timeout_seconds,
        )
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=request_timeout,
                transport=self.transport,
                trust_env=False,
            ) as client:
                response = await client.request(method, path, json=json)
        except httpx.HTTPError as error:
            raise ToolError("CONTROL_API_UNAVAILABLE") from error
        if response.status_code >= 400:
            raise _safe_tool_error(response)
        return response


def _validate_device_id(device_id: str) -> str:
    try:
        return _DEVICE_ID_ADAPTER.validate_python(device_id)
    except ValidationError as error:
        raise ToolError("INVALID_DEVICE_ID") from error


def _response_object(response: httpx.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError as error:
        raise ToolError("INVALID_CONTROL_RESPONSE") from error
    if not isinstance(payload, dict):
        raise ToolError("INVALID_CONTROL_RESPONSE")
    return payload


def _safe_tool_error(response: httpx.Response) -> ToolError:
    code = "CONTROL_API_ERROR"
    try:
        payload = response.json()
        error_payload = payload.get("error") if isinstance(payload, dict) else None
        candidate = error_payload.get("code") if isinstance(error_payload, dict) else None
        if isinstance(candidate, str) and _SAFE_ERROR_CODE.fullmatch(candidate):
            code = candidate
    except ValueError:
        pass
    return ToolError(f"{code} (HTTP {response.status_code})")
