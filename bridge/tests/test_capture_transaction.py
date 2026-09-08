from __future__ import annotations

import asyncio
from hashlib import sha256
from pathlib import Path

import pytest
from stackchan_bridge.captures.store import CaptureStore, CaptureValidationError
from stackchan_simulator.fixtures import generate_synthetic_jpeg


@pytest.mark.parametrize("completion_first", [False, True])
async def test_transaction_requires_matching_image_and_released_firmware(
    tmp_path: Path, completion_first: bool
) -> None:
    store = CaptureStore(directory=tmp_path, ttl_seconds=600, max_bytes=2097152)
    capture = store.reserve("sim-001", timeout_seconds=1)
    jpeg = generate_synthetic_jpeg()
    waiter = asyncio.create_task(store.wait_for_completion(capture.capture_id))
    await asyncio.sleep(0)

    def complete() -> None:
        assert store.complete(
            capture.capture_id,
            device_id="sim-001",
            ok=True,
            digest=sha256(jpeg).hexdigest(),
            size_bytes=len(jpeg),
        )

    def save() -> None:
        store.save(capture.capture_id, device_id="sim-001", content_type="image/jpeg", body=jpeg)

    (complete if completion_first else save)()
    await asyncio.sleep(0)
    assert not waiter.done()
    (save if completion_first else complete)()
    record = await asyncio.wait_for(waiter, 0.2)
    assert record.sha256 == sha256(jpeg).hexdigest()
    assert store.status(capture.capture_id, device_id="sim-001")["state"] == "succeeded"
    assert not store.fail(capture.capture_id, device_id="sim-001")
    assert not store.cancel(capture.capture_id)
    assert store.get(capture.capture_id) == record


def test_duplicate_upload_is_owned_identical_and_does_not_extend_lifetime(tmp_path: Path) -> None:
    now = [0.0]
    store = CaptureStore(
        directory=tmp_path, ttl_seconds=600, max_bytes=2097152, monotonic_clock=lambda: now[0]
    )
    capture = store.reserve("sim-001", timeout_seconds=10)
    jpeg = generate_synthetic_jpeg()
    record = store.save(
        capture.capture_id, device_id="sim-001", content_type="image/jpeg", body=jpeg
    )
    assert (
        store.save(capture.capture_id, device_id="sim-001", content_type="image/jpeg", body=jpeg)
        == record
    )
    for owner, body, code in [
        ("other", jpeg, "CAPTURE_OWNERSHIP"),
        ("sim-001", jpeg + b"different", "CAPTURE_CONTENT_MISMATCH"),
    ]:
        with pytest.raises(CaptureValidationError) as error:
            store.save(capture.capture_id, device_id=owner, content_type="image/jpeg", body=body)
        assert error.value.code == code
    now[0] = 10
    with pytest.raises(CaptureValidationError, match="expired"):
        store.save(capture.capture_id, device_id="sim-001", content_type="image/jpeg", body=jpeg)
    assert store.status(capture.capture_id, device_id="sim-001")["state"] == "expired"
    assert store.get(capture.capture_id) == record
    assert not store.complete(
        capture.capture_id,
        device_id="sim-001",
        ok=True,
        digest=record.sha256,
        size_bytes=record.size_bytes,
    )


@pytest.mark.parametrize("deadline_already_elapsed", [False, True])
async def test_saved_image_without_completion_reports_completion_timeout(
    tmp_path: Path, deadline_already_elapsed: bool
) -> None:
    now = [0.0]
    store = CaptureStore(
        directory=tmp_path, ttl_seconds=600, max_bytes=2097152, monotonic_clock=lambda: now[0]
    )
    capture = store.reserve("sim-001", timeout_seconds=0.02)
    store.save(
        capture.capture_id,
        device_id="sim-001",
        content_type="image/jpeg",
        body=generate_synthetic_jpeg(),
    )
    assert store.status(capture.capture_id, device_id="sim-001")["state"] == "image_saved"
    if deadline_already_elapsed:
        now[0] = 0.02
    with pytest.raises(CaptureValidationError) as error:
        await store.wait_for_completion(capture.capture_id)
    assert error.value.code == "CAPTURE_COMPLETION_TIMEOUT"
    assert store.get(capture.capture_id) is not None


def test_completion_cannot_claim_a_different_image_or_owner(tmp_path: Path) -> None:
    store = CaptureStore(directory=tmp_path, ttl_seconds=600, max_bytes=2097152)
    capture = store.reserve("sim-001")
    record = store.save(
        capture.capture_id,
        device_id="sim-001",
        content_type="image/jpeg",
        body=generate_synthetic_jpeg(),
    )
    assert not store.complete(
        capture.capture_id,
        device_id="other",
        ok=True,
        digest=record.sha256,
        size_bytes=record.size_bytes,
    )
    assert not store.complete(
        capture.capture_id,
        device_id="sim-001",
        ok=True,
        digest="0" * 64,
        size_bytes=record.size_bytes,
    )
    assert store.status(capture.capture_id, device_id="sim-001")["state"] == "image_saved"


def test_deleting_saved_image_never_reopens_upload(tmp_path: Path) -> None:
    store = CaptureStore(directory=tmp_path, ttl_seconds=600, max_bytes=2097152)
    capture = store.reserve("sim-001")
    jpeg = generate_synthetic_jpeg()
    record = store.save(
        capture.capture_id, device_id="sim-001", content_type="image/jpeg", body=jpeg
    )
    assert store.complete(
        capture.capture_id,
        device_id="sim-001",
        ok=True,
        digest=record.sha256,
        size_bytes=record.size_bytes,
    )
    assert store.delete(capture.capture_id)
    with pytest.raises(CaptureValidationError):
        store.save(capture.capture_id, device_id="sim-001", content_type="image/jpeg", body=jpeg)
    assert not record.path.exists()


def test_receipt_evidence_is_recorded_only_for_the_authenticated_owner(tmp_path: Path) -> None:
    store = CaptureStore(directory=tmp_path, ttl_seconds=600, max_bytes=2097152)
    capture = store.reserve("sim-001")
    assert not store.has_device_contact(capture.capture_id)
    with pytest.raises(CaptureValidationError):
        store.observe_device(capture.capture_id, device_id="other")
    assert not store.has_device_contact(capture.capture_id)
    store.observe_device(capture.capture_id, device_id="sim-001")
    assert store.has_device_contact(capture.capture_id)


def test_failed_transaction_notifications_are_reclaimed_with_retention(tmp_path: Path) -> None:
    wall = [0.0]
    store = CaptureStore(
        directory=tmp_path, ttl_seconds=600, max_bytes=2097152, clock=lambda: wall[0]
    )
    for _ in range(20):
        capture = store.reserve("sim-001")
        store.fail(capture.capture_id, device_id="sim-001")
    wall[0] = 601
    store.purge_expired()
    assert not store._completion_events
    assert not store._transactions
    assert not store._failures
