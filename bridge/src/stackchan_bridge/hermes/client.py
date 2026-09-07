"""Client for HermesAgent's public health, capabilities, and Responses API."""

from __future__ import annotations

import base64
import builtins
import json
from asyncio import Lock, timeout
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Annotated, Any

import httpx
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    StringConstraints,
    TypeAdapter,
    ValidationError,
)

from stackchan_bridge.hermes.errors import (
    HermesAuthenticationError,
    HermesEndpointError,
    HermesError,
    HermesProtocolError,
    HermesRateLimitError,
    HermesResponseError,
    HermesServerError,
    HermesTimeoutError,
    HermesTransportError,
)
from stackchan_bridge.protocol.models import DeviceId

_MAX_SSE_EVENT_BYTES = 65_536
_MAX_READINESS_RESPONSE_BYTES = 65_536
_DEVICE_ID_ADAPTER: TypeAdapter[str] = TypeAdapter(DeviceId)
_PublicPath = Annotated[str, StringConstraints(pattern=r"^/", max_length=128)]


class HermesCapabilities(BaseModel):
    model_config = ConfigDict(extra="ignore")

    responses_api: bool = False
    streaming: bool = False
    session_key_header: bool = False
    input_image: bool = False
    models: list[str] = Field(default_factory=list, max_length=128)
    skills_endpoint: _PublicPath | None = None
    toolsets_endpoint: _PublicPath | None = None


def parse_hermes_capabilities(payload: object) -> HermesCapabilities:
    """Normalize supported public Hermes capability document versions."""

    if not isinstance(payload, dict) or not _is_current_capability_document(payload):
        return HermesCapabilities.model_validate(payload)

    features = payload.get("features")
    endpoints = payload.get("endpoints")
    if not isinstance(features, dict):
        features = {}

    responses_path = _capability_endpoint_path(endpoints, "responses", "POST")
    skills_path = _capability_endpoint_path(endpoints, "skills", "GET")
    toolsets_path = _capability_endpoint_path(endpoints, "toolsets", "GET")
    model = payload.get("model")
    models = [model] if isinstance(model, str) and model.strip() else []
    return HermesCapabilities.model_validate(
        {
            "responses_api": features.get("responses_api") is True and responses_path is not None,
            "streaming": features.get("responses_streaming") is True,
            "session_key_header": features.get("session_key_header") == "X-Hermes-Session-Key",
            "input_image": responses_path == "/v1/responses",
            "models": models,
            "skills_endpoint": skills_path if features.get("skills_api") is True else None,
            "toolsets_endpoint": toolsets_path,
        }
    )


def _is_current_capability_document(payload: dict[object, object]) -> bool:
    auth = payload.get("auth")
    return (
        payload.get("object") == "hermes.api_server.capabilities"
        and payload.get("platform") == "hermes-agent"
        and isinstance(auth, dict)
        and auth.get("type") == "bearer"
        and auth.get("required") is True
    )


def _capability_endpoint_path(
    endpoints: object,
    name: str,
    method: str,
) -> str | None:
    if not isinstance(endpoints, dict):
        return None
    endpoint = endpoints.get(name)
    if not isinstance(endpoint, dict) or endpoint.get("method") != method:
        return None
    path = endpoint.get("path")
    return path if isinstance(path, str) else None


@dataclass(frozen=True, slots=True)
class HermesReadiness:
    ready: bool
    capabilities: HermesCapabilities
    error: str | None = None


@dataclass(frozen=True, slots=True)
class HermesEvent:
    type: str
    response_id: str | None = None
    delta: str | None = None
    item: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class HermesClientConfig:
    api_key: SecretStr = field(repr=False)
    profile: str = "default"
    model: str | None = None
    responses_path: str = "/v1/responses"
    health_path: str = "/health"
    capabilities_path: str = "/v1/capabilities"
    session_key_prefix: str | None = None
    timeout_seconds: float = 120
    instructions: str = (
        "これはStackChanを介した日本語の音声会話です。自然で簡潔に答えてください。"
        "原則2文以内とし、冗長な列挙を避けてください。"
        "必要な場合は利用可能なMCPやSkillsを使用してください。"
    )

    def __post_init__(self) -> None:
        if not self.profile or len(self.profile) > 64:
            raise ValueError("Hermes profile must contain 1 to 64 characters")
        if self.timeout_seconds <= 0:
            raise ValueError("Hermes timeout must be positive")
        for path in (self.responses_path, self.health_path, self.capabilities_path):
            if not path.startswith("/") or len(path) > 128:
                raise ValueError("Hermes endpoint paths must be bounded absolute paths")


class HermesClient:
    """Use only the documented OpenAI-compatible Hermes HTTP surfaces."""

    def __init__(self, client: httpx.AsyncClient, config: HermesClientConfig) -> None:
        self._client = client
        self._config = config
        self._selected_model = config.model
        self._model_selection_lock = Lock()
        self._conversation_generations: dict[str, int] = {}

    def __repr__(self) -> str:
        return f"HermesClient(profile={self._config.profile!r}, model={self._selected_model!r})"

    async def probe(self) -> HermesReadiness:
        empty = HermesCapabilities()
        try:
            async with timeout(self._config.timeout_seconds):
                health = await self._get_readiness_json(self._config.health_path)
                if not isinstance(health, dict) or health.get("status") != "ok":
                    raise HermesProtocolError("Hermes health response is invalid")
                capabilities = parse_hermes_capabilities(
                    await self._get_readiness_json(self._config.capabilities_path)
                )
        except (
            builtins.TimeoutError,
            HermesError,
            httpx.HTTPError,
            ValueError,
            ValidationError,
        ) as error:
            return HermesReadiness(ready=False, capabilities=empty, error=type(error).__name__)
        ready = all(
            (
                capabilities.responses_api,
                capabilities.streaming,
                capabilities.session_key_header,
                capabilities.input_image,
                capabilities.skills_endpoint is not None,
                capabilities.toolsets_endpoint is not None,
            )
        )
        if self._selected_model is None and capabilities.models:
            self._selected_model = capabilities.models[0]
        if self._selected_model is None:
            ready = False
        return HermesReadiness(
            ready=ready,
            capabilities=capabilities,
            error=None if ready else "required capabilities or model are unavailable",
        )

    async def _get_readiness_json(self, path: str) -> object:
        async with self._client.stream(
            "GET",
            path,
            headers=self._authorization_headers(),
        ) as response:
            _raise_for_status(response)
            body = bytearray()
            async for chunk in response.aiter_bytes():
                if len(body) + len(chunk) > _MAX_READINESS_RESPONSE_BYTES:
                    raise HermesProtocolError("Hermes readiness response exceeds the size limit")
                body.extend(chunk)
        try:
            return json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise HermesProtocolError("Hermes readiness response is malformed JSON") from error

    async def stream_text_response(
        self,
        *,
        device_id: str,
        transcript: str,
    ) -> AsyncIterator[HermesEvent]:
        validated_device_id = _DEVICE_ID_ADAPTER.validate_python(device_id)
        if not transcript.strip():
            raise ValueError("Hermes transcript cannot be empty")
        async for event in self._stream_content(
            validated_device_id,
            [{"type": "input_text", "text": transcript}],
        ):
            yield event

    async def stream_vision_response(
        self,
        *,
        device_id: str,
        question: str,
        jpeg: bytes,
    ) -> AsyncIterator[HermesEvent]:
        validated_device_id = _DEVICE_ID_ADAPTER.validate_python(device_id)
        if not question.strip() or len(question) > 1_000:
            raise ValueError("Hermes vision question must contain 1 to 1000 characters")
        if (
            len(jpeg) < 5
            or len(jpeg) > 16_777_216
            or not jpeg.startswith(b"\xff\xd8\xff")
            or not jpeg.endswith(b"\xff\xd9")
        ):
            raise ValueError("Hermes vision input must be a bounded JPEG")
        image_url = "data:image/jpeg;base64," + base64.b64encode(jpeg).decode("ascii")
        async for event in self._stream_content(
            validated_device_id,
            [
                {"type": "input_text", "text": question},
                {"type": "input_image", "image_url": image_url},
            ],
        ):
            yield event

    def reset_conversation(self, device_id: str) -> str:
        """Start a fresh transcript scope while preserving the stable memory session key."""

        validated_device_id = _DEVICE_ID_ADAPTER.validate_python(device_id)
        generation = self._conversation_generations.get(validated_device_id, 0) + 1
        self._conversation_generations[validated_device_id] = generation
        return self._conversation_name(validated_device_id)

    async def _stream_content(
        self,
        device_id: str,
        content: list[dict[str, str]],
    ) -> AsyncIterator[HermesEvent]:
        model = await self._ensure_selected_model()
        headers = {
            **self._authorization_headers(),
            "Accept": "text/event-stream",
            "X-Hermes-Session-Key": self._session_key(device_id),
        }
        body = {
            "model": model,
            "conversation": self._conversation_name(device_id),
            "instructions": self._config.instructions,
            "input": [
                {
                    "role": "user",
                    "content": content,
                }
            ],
            "store": True,
            "stream": True,
        }
        try:
            async with timeout(self._config.timeout_seconds):
                async with self._client.stream(
                    "POST",
                    self._config.responses_path,
                    headers=headers,
                    json=body,
                ) as response:
                    _raise_for_status(response)
                    completed = False
                    lines = _iter_bounded_sse_lines(response.aiter_bytes())
                    async for event in _iter_hermes_events(lines):
                        yield event
                        if event.type == "response.completed":
                            completed = True
                            break
                    if not completed:
                        raise HermesProtocolError("Hermes SSE closed before response.completed")
        except HermesError:
            raise
        except builtins.TimeoutError as error:
            raise HermesTimeoutError("Hermes request timed out") from error
        except httpx.TimeoutException as error:
            raise HermesTimeoutError("Hermes request timed out") from error
        except httpx.HTTPError as error:
            raise HermesTransportError("Hermes transport failed") from error

    async def _ensure_selected_model(self) -> str:
        if self._selected_model is not None:
            return self._selected_model
        async with self._model_selection_lock:
            if self._selected_model is None:
                await self.probe()
            if self._selected_model is None:
                raise HermesProtocolError("Hermes model has not been selected")
            return self._selected_model

    def _authorization_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._config.api_key.get_secret_value()}"}

    def _session_key(self, device_id: str) -> str:
        prefix = self._config.session_key_prefix or f"agent:{self._config.profile}:stackchan"
        value = f"{prefix}:{device_id}"
        if len(value) > 256 or any(ord(character) < 32 for character in value):
            raise ValueError("Hermes session key is invalid")
        return value

    def _conversation_name(self, device_id: str) -> str:
        generation = self._conversation_generations.get(device_id, 0)
        base = f"stackchan:{device_id}"
        return base if generation == 0 else f"{base}:reset-{generation}"


async def _iter_hermes_events(lines: AsyncIterator[str]) -> AsyncIterator[HermesEvent]:
    event_name: str | None = None
    data_lines: list[str] = []
    data_bytes = 0
    async for line in lines:
        if not line:
            if data_lines:
                yield _parse_event(event_name, "\n".join(data_lines))
            event_name = None
            data_lines = []
            data_bytes = 0
            continue
        if line.startswith(":"):
            continue
        field_name, separator, value = line.partition(":")
        if separator and value.startswith(" "):
            value = value[1:]
        if field_name == "event":
            event_name = value
        elif field_name == "data":
            data_bytes += len(value.encode("utf-8"))
            if data_bytes > _MAX_SSE_EVENT_BYTES:
                raise HermesProtocolError("Hermes SSE event exceeds the size limit")
            data_lines.append(value)
    if data_lines:
        yield _parse_event(event_name, "\n".join(data_lines))


async def _iter_bounded_sse_lines(chunks: AsyncIterator[bytes]) -> AsyncIterator[str]:
    line = bytearray()
    event_bytes = 0
    skip_line_feed = False
    async for chunk in chunks:
        for value in chunk:
            if skip_line_feed:
                skip_line_feed = False
                if value == 0x0A:
                    continue
            if value in {0x0A, 0x0D}:
                event_bytes += len(line) + 1
                if event_bytes > _MAX_SSE_EVENT_BYTES:
                    raise HermesProtocolError("Hermes SSE event exceeds the size limit")
                decoded = _decode_sse_line(line)
                line.clear()
                yield decoded
                if not decoded:
                    event_bytes = 0
                skip_line_feed = value == 0x0D
                continue
            if event_bytes + len(line) >= _MAX_SSE_EVENT_BYTES:
                raise HermesProtocolError("Hermes SSE line exceeds the size limit")
            line.append(value)
    if line:
        yield _decode_sse_line(line)


def _decode_sse_line(line: bytearray) -> str:
    try:
        return line.decode("utf-8")
    except UnicodeDecodeError as error:
        raise HermesProtocolError("Hermes SSE line is not valid UTF-8") from error


def _parse_event(event_name: str | None, raw_data: str) -> HermesEvent:
    try:
        payload = json.loads(raw_data)
    except json.JSONDecodeError as error:
        raise HermesProtocolError("Hermes SSE data is malformed JSON") from error
    if not isinstance(payload, dict):
        raise HermesProtocolError("Hermes SSE data must be an object")
    payload_type = payload.get("type")
    if not isinstance(payload_type, str) or (event_name and event_name != payload_type):
        raise HermesProtocolError("Hermes SSE event type is invalid")
    if payload_type == "error":
        error_payload = payload.get("error")
        code = error_payload.get("code") if isinstance(error_payload, dict) else None
        safe_code = code if isinstance(code, str) and 1 <= len(code) <= 64 else "UNKNOWN"
        raise HermesResponseError(safe_code)
    response_id = payload.get("response_id")
    response = payload.get("response")
    if response_id is None and isinstance(response, dict):
        response_id = response.get("id")
    delta = payload.get("delta")
    item = payload.get("item")
    return HermesEvent(
        type=payload_type,
        response_id=response_id if isinstance(response_id, str) else None,
        delta=delta if isinstance(delta, str) else None,
        item=item if isinstance(item, dict) else None,
    )


def _raise_for_status(response: httpx.Response) -> None:
    status = response.status_code
    if status < 400:
        return
    if status == 401:
        raise HermesAuthenticationError("Hermes authentication failed")
    if status == 404:
        raise HermesEndpointError("Hermes public endpoint was not found")
    if status == 429:
        raise HermesRateLimitError("Hermes rate limit exceeded")
    if status >= 500:
        raise HermesServerError("Hermes returned a server error")
    raise HermesProtocolError(f"Hermes request failed with HTTP {status}")
