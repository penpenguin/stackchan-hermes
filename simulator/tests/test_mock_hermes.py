from __future__ import annotations

from time import monotonic

import httpx
import pytest
from stackchan_simulator.mock_hermes import MockHermesConfig, create_mock_hermes_app


@pytest.mark.asyncio
async def test_mock_hermes_health_capabilities_and_responses_stream() -> None:
    app = create_mock_hermes_app(
        MockHermesConfig(
            api_key="test-hermes-token",  # pragma: allowlist secret
            response_text="こんにちは。",
        )
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://mock-hermes") as client:
        health = await client.get("/health")
        capabilities = await client.get(
            "/v1/capabilities",
            headers={"Authorization": "Bearer test-hermes-token"},
        )
        response = await client.post(
            "/v1/responses",
            headers={
                "Authorization": "Bearer test-hermes-token",
                "X-Hermes-Session-Key": "agent:default:stackchan:sim-001",
                "Accept": "text/event-stream",
            },
            json={
                "model": "hermes-agent",
                "conversation": "stackchan:sim-001",
                "input": [
                    {
                        "role": "user",
                        "content": [{"type": "input_text", "text": "こんにちは"}],
                    }
                ],
                "stream": True,
            },
        )

    assert health.json() == {"status": "ok"}
    assert capabilities.json()["responses_api"] is True
    assert capabilities.json()["streaming"] is True
    assert capabilities.json()["session_key_header"] is True
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: response.created" in response.text
    assert '"delta":"こんにちは。"' in response.text
    assert "event: response.completed" in response.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("scenario", "expected_status"), [("rate_limit", 429), ("server_error", 500)]
)
async def test_mock_hermes_reproduces_http_fault_statuses(
    scenario: str,
    expected_status: int,
) -> None:
    app = create_mock_hermes_app(
        MockHermesConfig(api_key="test-hermes-token")  # pragma: allowlist secret
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://mock-hermes") as client:
        response = await client.post(
            "/v1/responses",
            headers={
                "Authorization": "Bearer test-hermes-token",
                "X-Hermes-Session-Key": "agent:default:stackchan:sim-001",
                "X-Mock-Hermes-Scenario": scenario,
            },
            json={"stream": True},
        )

    assert response.status_code == expected_status


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("scenario", "expected_fragment"),
    [
        ("tool_progress", "event: response.output_item.added"),
        ("malformed_sse", "data: {not-json"),
    ],
)
async def test_mock_hermes_reproduces_stream_variants(
    scenario: str,
    expected_fragment: str,
) -> None:
    app = create_mock_hermes_app(
        MockHermesConfig(api_key="test-hermes-token")  # pragma: allowlist secret
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://mock-hermes") as client:
        response = await client.post(
            "/v1/responses",
            headers={
                "Authorization": "Bearer test-hermes-token",
                "X-Hermes-Session-Key": "agent:default:stackchan:sim-001",
                "X-Mock-Hermes-Scenario": scenario,
            },
            json={"stream": True},
        )

    assert response.status_code == 200
    assert expected_fragment in response.text


@pytest.mark.asyncio
async def test_mock_hermes_reproduces_delay_and_early_disconnect() -> None:
    app = create_mock_hermes_app(
        MockHermesConfig(
            api_key="test-hermes-token",  # pragma: allowlist secret
            delay_seconds=0.02,
        )
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://mock-hermes") as client:
        started = monotonic()
        delayed = await client.post(
            "/v1/responses",
            headers={
                "Authorization": "Bearer test-hermes-token",
                "X-Hermes-Session-Key": "agent:default:stackchan:sim-001",
                "X-Mock-Hermes-Scenario": "delayed",
            },
            json={"stream": True},
        )
        elapsed = monotonic() - started
        disconnected = await client.post(
            "/v1/responses",
            headers={
                "Authorization": "Bearer test-hermes-token",
                "X-Hermes-Session-Key": "agent:default:stackchan:sim-001",
                "X-Mock-Hermes-Scenario": "disconnect",
            },
            json={"stream": True},
        )

    assert delayed.status_code == 200
    assert elapsed >= 0.02
    assert "event: response.created" in disconnected.text
    assert "event: response.completed" not in disconnected.text
