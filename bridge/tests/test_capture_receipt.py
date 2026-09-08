from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from stackchan_bridge.captures.store import CaptureStore
from stackchan_bridge.device_gateway import application as gateway
from stackchan_simulator.fixtures import generate_synthetic_jpeg


async def test_receipt_recovers_lost_ack_without_spending_upload_quota(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(gateway, "verify_device_token", lambda *_: True)
    store = CaptureStore(directory=tmp_path, ttl_seconds=600, max_bytes=2097152)
    app = gateway.create_device_gateway_app(
        gateway.DeviceGatewayConfig(
            device_token_hashes={"sim-001": "synthetic"},
            capture_rate_burst=1,
        ),
        capture_store=store,
    )
    capture = store.reserve("sim-001")
    headers = {"Authorization": "Bearer synthetic", "X-StackChan-Device-Id": "sim-001"}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test", headers=headers
    ) as client:
        unknown = await client.post(f"/v1/device/captures/{uuid4()}", content=b"not read")
        assert unknown.status_code == 404
        status = await client.get(f"/v1/device/captures/{capture.capture_id}/status")
        assert status.status_code == 200
        assert status.json()["state"] == "reserved"
        assert 0 < status.json()["remaining_ms"] <= 10000
        upload = await client.post(
            f"/v1/device/captures/{capture.capture_id}",
            files={"file": ("capture.jpg", generate_synthetic_jpeg(), "image/jpeg")},
        )
        assert upload.status_code == 201
        receipt = await client.get(f"/v1/device/captures/{capture.capture_id}/status")
        assert receipt.status_code == 200
        assert receipt.json()["sha256"] == upload.json()["sha256"]
        assert receipt.json()["state"] == "image_saved"


@pytest.mark.parametrize("cancel", [False, True])
async def test_transaction_expiry_interrupts_streaming_body(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cancel: bool
) -> None:
    monkeypatch.setattr(gateway, "verify_device_token", lambda *_: True)
    store = CaptureStore(directory=tmp_path, ttl_seconds=600, max_bytes=2097152)
    capture = store.reserve("sim-001", timeout_seconds=10 if cancel else 0.03)
    app = gateway.create_device_gateway_app(
        gateway.DeviceGatewayConfig(device_token_hashes={"sim-001": "synthetic"}),
        capture_store=store,
    )

    async def body():
        yield b"--boundary\r\n"
        if cancel:
            store.cancel(capture.capture_id)
        await asyncio.sleep(1)
        yield b"x"

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await asyncio.wait_for(
            client.post(
                f"/v1/device/captures/{capture.capture_id}",
                headers={
                    "Authorization": "Bearer synthetic",
                    "X-StackChan-Device-Id": "sim-001",
                    "Content-Type": "multipart/form-data; boundary=boundary",
                },
                content=body(),
            ),
            0.2,
        )
    assert response.status_code == (404 if cancel else 408)
    assert store.get(capture.capture_id) is None
