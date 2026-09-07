"""Deterministic public-API Mock Hermes server for host tests."""

from __future__ import annotations

import json
from asyncio import sleep
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from hmac import compare_digest
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import StreamingResponse


@dataclass(frozen=True, slots=True)
class MockHermesConfig:
    """Mock authentication and deterministic response content."""

    api_key: str = field(repr=False)
    response_text: str = "これはMock Hermesの応答です。"
    delay_seconds: float = 0.0


def create_mock_hermes_app(config: MockHermesConfig) -> FastAPI:
    """Create an in-process server exposing only documented Hermes surfaces."""

    app = FastAPI(title="Mock Hermes", docs_url=None, redoc_url=None, openapi_url=None)

    def require_auth(request: Request) -> None:
        expected = f"Bearer {config.api_key}"
        provided = request.headers.get("Authorization", "")
        if not compare_digest(provided, expected):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/capabilities")
    async def capabilities(request: Request) -> dict[str, object]:
        require_auth(request)
        return {
            "responses_api": True,
            "streaming": True,
            "session_key_header": True,
            "input_image": True,
            "models": ["hermes-agent"],
            "skills_endpoint": "/v1/skills",
            "toolsets_endpoint": "/v1/toolsets",
        }

    @app.post("/v1/responses")
    async def responses(request: Request) -> StreamingResponse:
        require_auth(request)
        if not request.headers.get("X-Hermes-Session-Key"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="missing session key"
            )
        scenario = request.headers.get("X-Mock-Hermes-Scenario", "success")
        if scenario == "rate_limit":
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="rate limited"
            )
        if scenario == "server_error":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="mock server error",
            )
        body = await request.json()
        if not isinstance(body, dict) or body.get("stream") is not True:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="stream=true required"
            )

        response_id = f"resp_{uuid4().hex}"

        async def events() -> AsyncIterator[bytes]:
            if scenario == "delayed":
                await sleep(config.delay_seconds)
            yield _sse_event(
                "response.created",
                {"type": "response.created", "response": {"id": response_id}},
            )
            if scenario == "disconnect":
                return
            if scenario == "malformed_sse":
                yield b"event: response.output_text.delta\ndata: {not-json\n\n"
                return
            if scenario == "tool_progress":
                tool_item = {
                    "id": "call_mock_status",
                    "type": "function_call",
                    "name": "stackchan_get_status",
                }
                yield _sse_event(
                    "response.output_item.added",
                    {"type": "response.output_item.added", "item": tool_item},
                )
                yield _sse_event(
                    "response.output_item.done",
                    {"type": "response.output_item.done", "item": tool_item},
                )
            yield _sse_event(
                "response.output_text.delta",
                {
                    "type": "response.output_text.delta",
                    "response_id": response_id,
                    "delta": config.response_text,
                },
            )
            yield _sse_event(
                "response.completed",
                {"type": "response.completed", "response": {"id": response_id}},
            )

        return StreamingResponse(events(), media_type="text/event-stream")

    return app


def _sse_event(name: str, payload: dict[str, object]) -> bytes:
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"event: {name}\ndata: {data}\n\n".encode()
