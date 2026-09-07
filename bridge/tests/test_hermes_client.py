from __future__ import annotations

import base64
import json
from asyncio import sleep, wait_for
from collections.abc import AsyncIterator

import httpx
import pytest
from pydantic import SecretStr
from stackchan_bridge.hermes.client import HermesClient, HermesClientConfig
from stackchan_bridge.hermes.errors import (
    HermesAuthenticationError,
    HermesEndpointError,
    HermesProtocolError,
    HermesRateLimitError,
    HermesResponseError,
    HermesServerError,
    HermesTimeoutError,
    HermesTransportError,
)
from stackchan_simulator.fixtures import generate_synthetic_jpeg
from stackchan_simulator.mock_hermes import MockHermesConfig, create_mock_hermes_app


class KeepAliveResponseStream(httpx.AsyncByteStream):
    async def __aiter__(self) -> AsyncIterator[bytes]:
        while True:
            await sleep(0.005)
            yield b": keep-alive\n\n"

    async def aclose(self) -> None:
        return None


class ChunkedResponseStream(httpx.AsyncByteStream):
    def __init__(self, chunks: tuple[bytes, ...]) -> None:
        self._chunks = chunks
        self.chunks_read = 0

    async def __aiter__(self) -> AsyncIterator[bytes]:
        for chunk in self._chunks:
            self.chunks_read += 1
            yield chunk

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_hermes_client_probes_required_capabilities_and_streams_text() -> None:
    api_key = "test-hermes-token"  # pragma: allowlist secret
    app = create_mock_hermes_app(MockHermesConfig(api_key=api_key, response_text="こんにちは。"))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://mock-hermes",
    ) as http_client:
        client = HermesClient(
            http_client,
            HermesClientConfig(
                api_key=SecretStr(api_key),
                profile="default",
                model="hermes-agent",
            ),
        )
        readiness = await client.probe()
        events = [
            event
            async for event in client.stream_text_response(
                device_id="sim-001",
                transcript="こんにちは",
            )
        ]

    assert readiness.ready is True
    assert readiness.capabilities.responses_api is True
    assert readiness.capabilities.streaming is True
    assert readiness.capabilities.session_key_header is True
    assert readiness.capabilities.input_image is True
    assert [event.type for event in events] == [
        "response.created",
        "response.output_text.delta",
        "response.completed",
    ]
    assert events[1].delta == "こんにちは。"
    assert events[0].response_id == events[-1].response_id
    assert api_key not in repr(client)


@pytest.mark.asyncio
async def test_hermes_client_accepts_v020_nested_capabilities() -> None:
    async def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        return httpx.Response(
            200,
            json={
                "object": "hermes.api_server.capabilities",
                "platform": "hermes-agent",
                "model": "hermes-agent",
                "auth": {"type": "bearer", "required": True},
                "features": {
                    "responses_api": True,
                    "responses_streaming": True,
                    "session_key_header": "X-Hermes-Session-Key",
                    "skills_api": True,
                },
                "endpoints": {
                    "responses": {"method": "POST", "path": "/v1/responses"},
                    "skills": {"method": "GET", "path": "/v1/skills"},
                    "toolsets": {"method": "GET", "path": "/v1/toolsets"},
                },
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handle),
        base_url="http://mock-hermes",
    ) as http_client:
        client = HermesClient(
            http_client,
            HermesClientConfig(
                api_key=SecretStr("test-hermes-token"),  # pragma: allowlist secret
            ),
        )
        readiness = await client.probe()

    assert readiness.ready is True
    assert readiness.capabilities.responses_api is True
    assert readiness.capabilities.streaming is True
    assert readiness.capabilities.session_key_header is True
    assert readiness.capabilities.input_image is True
    assert readiness.capabilities.models == ["hermes-agent"]
    assert readiness.capabilities.skills_endpoint == "/v1/skills"
    assert readiness.capabilities.toolsets_endpoint == "/v1/toolsets"


@pytest.mark.asyncio
@pytest.mark.parametrize("slow_path", ["/health", "/v1/capabilities"])
async def test_hermes_probe_bounds_the_total_time_of_slow_readiness_responses(
    slow_path: str,
) -> None:
    class SlowReadinessStream(httpx.AsyncByteStream):
        closed = False

        async def __aiter__(self) -> AsyncIterator[bytes]:
            while True:
                await sleep(0.005)
                yield b" "

        async def aclose(self) -> None:
            self.closed = True

    stream = SlowReadinessStream()

    async def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path == slow_path:
            return httpx.Response(200, stream=stream)
        return httpx.Response(200, json={"status": "ok"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handle), base_url="http://mock-hermes", timeout=0.01
    ) as http_client:
        client = HermesClient(
            http_client,
            HermesClientConfig(
                api_key=SecretStr("test-hermes-token"),  # pragma: allowlist secret
                timeout_seconds=0.02,
            ),
        )
        readiness = await wait_for(client.probe(), timeout=0.2)

    assert readiness.ready is False
    assert readiness.error == "TimeoutError"
    assert stream.closed


@pytest.mark.asyncio
@pytest.mark.parametrize("oversized_path", ["/health", "/v1/capabilities"])
async def test_hermes_probe_bounds_readiness_json_while_streaming(
    monkeypatch: pytest.MonkeyPatch,
    oversized_path: str,
) -> None:
    monkeypatch.setattr("stackchan_bridge.hermes.client._MAX_READINESS_RESPONSE_BYTES", 16)
    stream = ChunkedResponseStream((b'{"response', b's_api":', b"true}"))

    async def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path == oversized_path:
            return httpx.Response(200, stream=stream)
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        return httpx.Response(
            200,
            json={
                "responses_api": True,
                "streaming": True,
                "session_key_header": True,
                "input_image": True,
                "models": ["hermes-agent"],
                "skills_endpoint": "/v1/skills",
                "toolsets_endpoint": "/v1/toolsets",
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handle),
        base_url="http://mock-hermes",
    ) as http_client:
        client = HermesClient(
            http_client,
            HermesClientConfig(
                api_key=SecretStr("test-hermes-token"),  # pragma: allowlist secret
            ),
        )
        readiness = await client.probe()

    assert readiness.ready is False
    assert readiness.error == "HermesProtocolError"
    assert stream.chunks_read == 2


@pytest.mark.asyncio
async def test_hermes_client_selects_the_default_model_before_the_first_turn() -> None:
    requested_paths: list[str] = []
    response_body: dict[str, object] = {}

    async def handle(request: httpx.Request) -> httpx.Response:
        requested_paths.append(request.url.path)
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        if request.url.path == "/v1/capabilities":
            return httpx.Response(
                200,
                json={
                    "responses_api": True,
                    "streaming": True,
                    "session_key_header": True,
                    "input_image": True,
                    "models": ["default-hermes-model"],
                    "skills_endpoint": "/v1/skills",
                    "toolsets_endpoint": "/v1/toolsets",
                },
            )
        response_body.update(json.loads(await request.aread()))
        return httpx.Response(
            200,
            headers={"Content-Type": "text/event-stream"},
            content=(
                'event: response.created\ndata: {"type":"response.created",'
                '"response":{"id":"resp_default_1"}}\n\n'
                'event: response.output_text.delta\ndata: {"type":"response.output_text.delta",'
                '"response_id":"resp_default_1","delta":"はい。"}\n\n'
                'event: response.completed\ndata: {"type":"response.completed",'
                '"response":{"id":"resp_default_1"}}\n\n'
            ).encode(),
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handle),
        base_url="http://mock-hermes",
    ) as http_client:
        client = HermesClient(
            http_client,
            HermesClientConfig(
                api_key=SecretStr("test-hermes-token"),  # pragma: allowlist secret
            ),
        )
        events = [
            event
            async for event in client.stream_text_response(
                device_id="sim-001",
                transcript="こんにちは",
            )
        ]

    assert requested_paths == ["/health", "/v1/capabilities", "/v1/responses"]
    assert response_body["model"] == "default-hermes-model"
    assert events[-1].type == "response.completed"


@pytest.mark.asyncio
async def test_hermes_readiness_requires_skills_and_toolsets_discovery_surfaces() -> None:
    async def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        return httpx.Response(
            200,
            json={
                "responses_api": True,
                "streaming": True,
                "session_key_header": True,
                "input_image": True,
                "models": ["hermes-agent"],
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handle),
        base_url="http://mock-hermes",
    ) as http_client:
        client = HermesClient(
            http_client,
            HermesClientConfig(
                api_key=SecretStr("test-hermes-token"),  # pragma: allowlist secret
            ),
        )
        readiness = await client.probe()

    assert readiness.ready is False
    assert readiness.error == "required capabilities or model are unavailable"


@pytest.mark.asyncio
async def test_hermes_client_maps_an_sse_error_without_reflecting_provider_text() -> None:
    private_message = "provider-private-diagnostic"

    async def error_response(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"Content-Type": "text/event-stream"},
            content=(
                "event: error\n"
                f'data: {{"type":"error","error":{{"code":"provider_error",'
                f'"message":"{private_message}"}}}}\n\n'
            ).encode(),
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(error_response),
        base_url="http://mock-hermes",
    ) as http_client:
        client = HermesClient(
            http_client,
            HermesClientConfig(
                api_key=SecretStr("test-hermes-token"),  # pragma: allowlist secret
                model="hermes-agent",
            ),
        )
        with pytest.raises(HermesResponseError) as error:
            _ = [
                event
                async for event in client.stream_text_response(
                    device_id="sim-001",
                    transcript="こんにちは",
                )
            ]

    assert error.value.code == "provider_error"
    assert private_message not in str(error.value)


@pytest.mark.asyncio
async def test_hermes_client_sends_jpeg_only_as_an_inline_vision_input() -> None:
    jpeg = generate_synthetic_jpeg()
    received_body: dict[str, object] = {}

    async def vision_response(request: httpx.Request) -> httpx.Response:
        received_body.update(json.loads(await request.aread()))
        return httpx.Response(
            200,
            headers={"Content-Type": "text/event-stream"},
            content=(
                'event: response.created\ndata: {"type":"response.created",'
                '"response":{"id":"resp_vision_1"}}\n\n'
                'event: response.output_text.delta\ndata: {"type":"response.output_text.delta",'
                '"response_id":"resp_vision_1","delta":"画像です。"}\n\n'
                'event: response.completed\ndata: {"type":"response.completed",'
                '"response":{"id":"resp_vision_1"}}\n\n'
            ).encode(),
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(vision_response),
        base_url="http://mock-hermes",
    ) as http_client:
        client = HermesClient(
            http_client,
            HermesClientConfig(
                api_key=SecretStr("test-hermes-token"),  # pragma: allowlist secret
                model="hermes-agent",
            ),
        )
        events = [
            event
            async for event in client.stream_vision_response(
                device_id="sim-001",
                question="この画像を説明してください",
                jpeg=jpeg,
            )
        ]

    input_items = received_body["input"]
    assert isinstance(input_items, list)
    content = input_items[0]["content"]
    assert content[0] == {"type": "input_text", "text": "この画像を説明してください"}
    assert content[1] == {
        "type": "input_image",
        "image_url": "data:image/jpeg;base64," + base64.b64encode(jpeg).decode("ascii"),
    }
    assert events[1].delta == "画像です。"


@pytest.mark.asyncio
async def test_hermes_conversation_reset_keeps_the_device_session_key() -> None:
    requests: list[tuple[str, str]] = []

    async def handle(request: httpx.Request) -> httpx.Response:
        body = json.loads(await request.aread())
        requests.append((body["conversation"], request.headers["x-hermes-session-key"]))
        return httpx.Response(
            200,
            headers={"Content-Type": "text/event-stream"},
            content=(
                'event: response.created\ndata: {"type":"response.created",'
                '"response":{"id":"resp_reset_1"}}\n\n'
                'event: response.output_text.delta\ndata: {"type":"response.output_text.delta",'
                '"response_id":"resp_reset_1","delta":"はい。"}\n\n'
                'event: response.completed\ndata: {"type":"response.completed",'
                '"response":{"id":"resp_reset_1"}}\n\n'
            ).encode(),
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handle),
        base_url="http://mock-hermes",
    ) as http_client:
        client = HermesClient(
            http_client,
            HermesClientConfig(
                api_key=SecretStr("test-hermes-token"),  # pragma: allowlist secret
                model="hermes-agent",
            ),
        )
        _ = [
            event
            async for event in client.stream_text_response(
                device_id="sim-001",
                transcript="最初の会話",
            )
        ]
        reset_name = client.reset_conversation("sim-001")
        _ = [
            event
            async for event in client.stream_text_response(
                device_id="sim-001",
                transcript="新しい会話",
            )
        ]

    assert reset_name == "stackchan:sim-001:reset-1"
    assert requests == [
        ("stackchan:sim-001", "agent:default:stackchan:sim-001"),
        ("stackchan:sim-001:reset-1", "agent:default:stackchan:sim-001"),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_code", "expected_error"),
    [
        (401, HermesAuthenticationError),
        (404, HermesEndpointError),
        (429, HermesRateLimitError),
        (500, HermesServerError),
        (503, HermesServerError),
    ],
)
async def test_hermes_client_maps_public_http_failures(
    status_code: int,
    expected_error: type[Exception],
) -> None:
    async def handle(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, content=b"provider-private-diagnostic")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handle),
        base_url="http://mock-hermes",
    ) as http_client:
        client = HermesClient(
            http_client,
            HermesClientConfig(
                api_key=SecretStr("test-hermes-token"),  # pragma: allowlist secret
                model="hermes-agent",
            ),
        )
        with pytest.raises(expected_error) as error:
            _ = [
                event
                async for event in client.stream_text_response(
                    device_id="sim-001",
                    transcript="こんにちは",
                )
            ]

    assert "provider-private-diagnostic" not in str(error.value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("transport_error", "expected_error"),
    [
        (httpx.ReadTimeout("Hermes timed out"), HermesTimeoutError),
        (httpx.ConnectError("Hermes disconnected"), HermesTransportError),
    ],
)
async def test_hermes_client_distinguishes_timeout_from_connection_failure(
    transport_error: httpx.HTTPError,
    expected_error: type[Exception],
) -> None:
    async def handle(_request: httpx.Request) -> httpx.Response:
        raise transport_error

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handle),
        base_url="http://mock-hermes",
    ) as http_client:
        client = HermesClient(
            http_client,
            HermesClientConfig(
                api_key=SecretStr("test-hermes-token"),  # pragma: allowlist secret
                model="hermes-agent",
            ),
        )
        with pytest.raises(expected_error):
            _ = [
                event
                async for event in client.stream_text_response(
                    device_id="sim-001",
                    transcript="こんにちは",
                )
            ]


@pytest.mark.asyncio
@pytest.mark.parametrize("vision", [False, True])
async def test_hermes_client_closes_sse_after_completed_without_waiting_for_eof(
    vision: bool,
) -> None:
    class CompletedKeepAliveStream(KeepAliveResponseStream):
        closed = False
        reads_after_completion = 0

        async def __aiter__(self) -> AsyncIterator[bytes]:
            yield b'event: response.completed\ndata: {"type":"response.completed"}\n\n'
            async for chunk in super().__aiter__():
                self.reads_after_completion += 1
                yield chunk

        async def aclose(self) -> None:
            self.closed = True

    stream = CompletedKeepAliveStream()

    async def handle(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"Content-Type": "text/event-stream"}, stream=stream)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handle), base_url="http://mock-hermes"
    ) as http_client:
        client = HermesClient(
            http_client,
            HermesClientConfig(
                api_key=SecretStr("test-hermes-token"),  # pragma: allowlist secret
                model="hermes-agent",
                timeout_seconds=0.02,
            ),
        )
        events = (
            client.stream_vision_response(
                device_id="sim-001", question="何が見えますか", jpeg=generate_synthetic_jpeg()
            )
            if vision
            else client.stream_text_response(device_id="sim-001", transcript="こんにちは")
        )
        received = [event async for event in events]

    assert [event.type for event in received] == ["response.completed"]
    assert stream.reads_after_completion == 0
    assert stream.closed


@pytest.mark.asyncio
async def test_hermes_client_applies_a_wall_clock_deadline_to_keep_alive_sse() -> None:
    async def handle(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"Content-Type": "text/event-stream"},
            stream=KeepAliveResponseStream(),
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handle),
        base_url="http://mock-hermes",
    ) as http_client:
        client = HermesClient(
            http_client,
            HermesClientConfig(
                api_key=SecretStr("test-hermes-token"),  # pragma: allowlist secret
                model="hermes-agent",
                timeout_seconds=0.02,
            ),
        )
        with pytest.raises(HermesTimeoutError):
            await wait_for(
                anext(
                    event
                    async for event in client.stream_text_response(
                        device_id="sim-001",
                        transcript="こんにちは",
                    )
                ),
                timeout=0.2,
            )


@pytest.mark.asyncio
async def test_hermes_client_rejects_an_oversized_sse_line_while_streaming(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("stackchan_bridge.hermes.client._MAX_SSE_EVENT_BYTES", 8)
    stream = ChunkedResponseStream((b"event:", b"abcd", b"must-not-be-read"))

    async def handle(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"Content-Type": "text/event-stream"},
            stream=stream,
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handle),
        base_url="http://mock-hermes",
    ) as http_client:
        client = HermesClient(
            http_client,
            HermesClientConfig(
                api_key=SecretStr("test-hermes-token"),  # pragma: allowlist secret
                model="hermes-agent",
            ),
        )
        with pytest.raises(HermesProtocolError, match="size limit"):
            _ = [
                event
                async for event in client.stream_text_response(
                    device_id="sim-001",
                    transcript="こんにちは",
                )
            ]

    assert stream.chunks_read == 2


@pytest.mark.asyncio
async def test_hermes_client_bounds_comments_within_one_sse_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("stackchan_bridge.hermes.client._MAX_SSE_EVENT_BYTES", 16)
    stream = ChunkedResponseStream(
        (
            b": 12345\n",
            b": 67890\n",
            b": x\n",
            (b'\nevent: response.completed\ndata: {"type":"response.completed"}\n\n'),
        )
    )

    async def handle(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"Content-Type": "text/event-stream"},
            stream=stream,
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handle),
        base_url="http://mock-hermes",
    ) as http_client:
        client = HermesClient(
            http_client,
            HermesClientConfig(
                api_key=SecretStr("test-hermes-token"),  # pragma: allowlist secret
                model="hermes-agent",
            ),
        )
        with pytest.raises(HermesProtocolError, match="size limit"):
            _ = [
                event
                async for event in client.stream_text_response(
                    device_id="sim-001",
                    transcript="こんにちは",
                )
            ]

    assert stream.chunks_read == 3
