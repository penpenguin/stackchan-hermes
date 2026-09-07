from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path
from typing import BinaryIO

import httpx
import pytest
import starlette.formparsers
from stackchan_bridge.captures.store import CaptureStore
from stackchan_bridge.device_gateway.application import (
    DeviceGatewayConfig,
    create_device_gateway_app,
)
from stackchan_bridge.security.tokens import hash_device_token
from stackchan_simulator.fixtures import generate_synthetic_jpeg
from starlette.datastructures import UploadFile


@pytest.mark.asyncio
async def test_authenticated_device_uploads_its_reserved_jpeg(tmp_path: Path) -> None:
    token = "simulator-device-token"  # pragma: allowlist secret
    store = CaptureStore(directory=tmp_path, ttl_seconds=600, max_bytes=2_097_152)
    reservation = store.reserve("sim-001")
    app = create_device_gateway_app(
        DeviceGatewayConfig(
            device_token_hashes={"sim-001": hash_device_token(token, salt=b"0123456789abcdef")}
        ),
        capture_store=store,
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://gateway") as client:
        response = await client.post(
            f"/v1/device/captures/{reservation.capture_id}",
            headers={
                "Authorization": f"Bearer {token}",
                "X-StackChan-Device-Id": "sim-001",
            },
            files={"file": ("ignored-device-name.jpg", generate_synthetic_jpeg(), "image/jpeg")},
        )

    assert response.status_code == 201
    assert response.json()["capture_id"] == str(reservation.capture_id)
    assert response.json()["mime_type"] == "image/jpeg"
    assert (response.json()["width"], response.json()["height"]) == (320, 240)
    assert len(response.json()["sha256"]) == 64
    assert "path" not in response.json()
    assert store.get(reservation.capture_id) is not None


@pytest.mark.asyncio
@pytest.mark.parametrize("slow_stage", ["headers", "body", "file_read"])
async def test_capture_upload_has_one_deadline_and_closes_partial_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    slow_stage: str,
) -> None:
    token = "simulator-device-token"  # pragma: allowlist secret
    store = CaptureStore(directory=tmp_path, ttl_seconds=600, max_bytes=2_097_152)
    reservation = store.reserve("sim-001")
    app = create_device_gateway_app(
        DeviceGatewayConfig(
            device_token_hashes={"sim-001": hash_device_token(token, salt=b"0123456789abcdef")}
        ),
        capture_store=store,
    )
    monkeypatch.setattr(
        "stackchan_bridge.device_gateway.application._CAPTURE_UPLOAD_TIMEOUT_SECONDS",
        0.02,
        raising=False,
    )
    original_spooled_file = starlette.formparsers.SpooledTemporaryFile
    spooled_files: list[BinaryIO] = []

    def track_spooled_file(*args: object, **kwargs: object) -> object:
        file = original_spooled_file(*args, **kwargs)
        spooled_files.append(file)
        return file

    monkeypatch.setattr(starlette.formparsers, "SpooledTemporaryFile", track_spooled_file)

    async def slow_body() -> AsyncIterator[bytes]:
        yield b"--test-boundary\r\n"
        if slow_stage == "body":
            yield (
                b'Content-Disposition: form-data; name="file"; filename="capture.jpg"\r\n'
                b"Content-Type: image/jpeg\r\n\r\n"
            )
        while True:
            await asyncio.sleep(0.005)
            yield b"x"

    async def slow_read(_upload: UploadFile, _size: int = -1) -> bytes:
        await asyncio.sleep(0.005)
        return b"x"

    headers = {"Authorization": f"Bearer {token}", "X-StackChan-Device-Id": "sim-001"}
    url = f"/v1/device/captures/{reservation.capture_id}"
    jpeg = generate_synthetic_jpeg()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://gateway"
    ) as client:
        with monkeypatch.context() as slow_patch:
            if slow_stage == "file_read":
                slow_patch.setattr(UploadFile, "read", slow_read)
                request = client.post(
                    url, headers=headers, files={"file": ("capture.jpg", jpeg, "image/jpeg")}
                )
            else:
                request = client.post(
                    url,
                    headers={
                        **headers,
                        "Content-Type": "multipart/form-data; boundary=test-boundary",
                    },
                    content=slow_body(),
                )
            response = await asyncio.wait_for(request, timeout=0.5)
        assert response.status_code == 408
        assert response.json()["error"]["code"] == "CAPTURE_UPLOAD_TIMEOUT"
        assert store.get(reservation.capture_id) is None
        assert len(spooled_files) == (0 if slow_stage == "headers" else 1)
        assert all(file.closed for file in spooled_files)
        retry = await client.post(
            url, headers=headers, files={"file": ("capture.jpg", jpeg, "image/jpeg")}
        )
    assert retry.status_code == 201
    assert all(file.closed for file in spooled_files)


@pytest.mark.asyncio
async def test_capture_upload_rejects_wrong_token_before_reading_media(tmp_path: Path) -> None:
    store = CaptureStore(directory=tmp_path, ttl_seconds=600, max_bytes=2_097_152)
    reservation = store.reserve("sim-001")
    app = create_device_gateway_app(
        DeviceGatewayConfig(
            device_token_hashes={
                "sim-001": hash_device_token(
                    "simulator-device-token",  # pragma: allowlist secret
                    salt=b"0123456789abcdef",
                )
            }
        ),
        capture_store=store,
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://gateway") as client:
        response = await client.post(
            f"/v1/device/captures/{reservation.capture_id}",
            headers={
                "Authorization": "Bearer wrong-device-token",
                "X-StackChan-Device-Id": "sim-001",
            },
            files={"file": ("capture.jpg", b"not-read-as-a-jpeg", "image/jpeg")},
        )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"
    assert store.get(reservation.capture_id) is None


@pytest.mark.asyncio
async def test_capture_upload_shares_the_bounded_authentication_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verified_tokens: list[str] = []

    def reject_token(token: str, _encoded_hash: str) -> bool:
        verified_tokens.append(token)
        return False

    monkeypatch.setattr(
        "stackchan_bridge.device_gateway.application.verify_device_token",
        reject_token,
    )
    store = CaptureStore(directory=tmp_path, ttl_seconds=600, max_bytes=2_097_152)
    reservation = store.reserve("sim-001")
    app = create_device_gateway_app(
        DeviceGatewayConfig(
            device_token_hashes={"sim-001": "stored-token-hash"},
            authentication_rate_per_second=0.001,
            authentication_rate_burst=1,
        ),
        capture_store=store,
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://gateway") as client:
        responses = [
            await client.post(
                f"/v1/device/captures/{reservation.capture_id}",
                headers={
                    "Authorization": "Bearer wrong-device-token",
                    "X-StackChan-Device-Id": "sim-001",
                },
                files={"file": ("capture.jpg", b"not-read", "image/jpeg")},
            )
            for _ in range(2)
        ]

    assert [response.status_code for response in responses] == [401, 429]
    assert responses[1].json()["error"]["code"] == "AUTHENTICATION_RATE_LIMITED"
    assert responses[1].headers["retry-after"] == "1000"
    assert verified_tokens == ["wrong-device-token"]


@pytest.mark.asyncio
async def test_capture_upload_rejects_malformed_multipart(tmp_path: Path) -> None:
    token = "simulator-device-token"  # pragma: allowlist secret
    store = CaptureStore(directory=tmp_path, ttl_seconds=600, max_bytes=2_097_152)
    reservation = store.reserve("sim-001")
    app = create_device_gateway_app(
        DeviceGatewayConfig(
            device_token_hashes={"sim-001": hash_device_token(token, salt=b"0123456789abcdef")}
        ),
        capture_store=store,
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://gateway") as client:
        response = await client.post(
            f"/v1/device/captures/{reservation.capture_id}",
            headers={
                "Authorization": f"Bearer {token}",
                "X-StackChan-Device-Id": "sim-001",
                "Content-Type": "multipart/form-data; boundary=missing",
            },
            content=b"this is not multipart data",
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_UPLOAD"
    assert store.get(reservation.capture_id) is None


@pytest.mark.asyncio
async def test_capture_upload_rate_limits_each_authenticated_device(tmp_path: Path) -> None:
    token = "simulator-device-token"  # pragma: allowlist secret
    store = CaptureStore(directory=tmp_path, ttl_seconds=600, max_bytes=2_097_152)
    first_reservation = store.reserve("sim-001")
    second_reservation = store.reserve("sim-001")
    app = create_device_gateway_app(
        DeviceGatewayConfig(
            device_token_hashes={"sim-001": hash_device_token(token, salt=b"0123456789abcdef")},
            capture_rate_per_minute=1,
            capture_rate_burst=1,
        ),
        capture_store=store,
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "X-StackChan-Device-Id": "sim-001",
    }
    jpeg = generate_synthetic_jpeg()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://gateway") as client:
        first = await client.post(
            f"/v1/device/captures/{first_reservation.capture_id}",
            headers=headers,
            files={"file": ("capture.jpg", jpeg, "image/jpeg")},
        )
        limited = await client.post(
            f"/v1/device/captures/{second_reservation.capture_id}",
            headers=headers,
            files={"file": ("capture.jpg", jpeg, "image/jpeg")},
        )

    assert first.status_code == 201
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "CAPTURE_RATE_LIMITED"
    assert limited.headers["retry-after"] == "60"
    assert store.get(second_reservation.capture_id) is None


@pytest.mark.asyncio
async def test_capture_upload_stops_before_spooling_file_data_over_the_limit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = "simulator-device-token"  # pragma: allowlist secret
    max_bytes = 64
    store = CaptureStore(directory=tmp_path, ttl_seconds=600, max_bytes=max_bytes)
    reservation = store.reserve("sim-001")
    app = create_device_gateway_app(
        DeviceGatewayConfig(
            device_token_hashes={"sim-001": hash_device_token(token, salt=b"0123456789abcdef")}
        ),
        capture_store=store,
    )
    original_spooled_file = starlette.formparsers.SpooledTemporaryFile
    spooled_bytes: list[int] = []

    def tracking_spooled_file(*args: object, **kwargs: object) -> object:
        temporary_file = original_spooled_file(*args, **kwargs)
        original_write = temporary_file.write

        def write(data: bytes) -> int:
            spooled_bytes.append(len(data))
            return original_write(data)

        temporary_file.write = write
        return temporary_file

    monkeypatch.setattr(starlette.formparsers, "SpooledTemporaryFile", tracking_spooled_file)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://gateway") as client:
        response = await client.post(
            f"/v1/device/captures/{reservation.capture_id}",
            headers={
                "Authorization": f"Bearer {token}",
                "X-StackChan-Device-Id": "sim-001",
            },
            files={"file": ("capture.jpg", b"x" * (max_bytes + 1), "image/jpeg")},
        )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "CAPTURE_TOO_LARGE"
    assert sum(spooled_bytes) <= max_bytes


@pytest.mark.asyncio
async def test_gateway_periodically_purges_unretrieved_expired_captures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = [0.0]
    store = CaptureStore(
        directory=tmp_path,
        ttl_seconds=1,
        max_bytes=2_097_152,
        clock=lambda: now[0],
    )
    reservation = store.reserve("sim-001")
    record = store.save(
        reservation.capture_id,
        device_id="sim-001",
        content_type="image/jpeg",
        body=generate_synthetic_jpeg(),
    )
    now[0] = 2.0
    monkeypatch.setattr(
        "stackchan_bridge.device_gateway.application._CAPTURE_CLEANUP_INTERVAL_SECONDS",
        0.01,
        raising=False,
    )
    app = create_device_gateway_app(DeviceGatewayConfig(), capture_store=store)

    async with app.router.lifespan_context(app):
        await asyncio.sleep(0.03)

    assert not record.path.exists()
    assert store.purge_expired() == 0
