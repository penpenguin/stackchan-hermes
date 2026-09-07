from __future__ import annotations

import os
from hashlib import sha256
from pathlib import Path

import pytest
from stackchan_bridge.captures.store import CaptureStore, CaptureValidationError
from stackchan_simulator.fixtures import generate_synthetic_jpeg


def jpeg_header_only(*, width: int, height: int) -> bytes:
    return (
        b"\xff\xd8"
        b"\xff\xc0\x00\x07\x08" + height.to_bytes(2, "big") + width.to_bytes(2, "big") + b"\xff\xd9"
    )


def test_capture_store_validates_and_expires_an_owned_synthetic_jpeg(tmp_path: Path) -> None:
    now = [1_000.0]
    capture_directory = tmp_path / "captures"
    store = CaptureStore(
        directory=capture_directory,
        ttl_seconds=600,
        max_bytes=2_097_152,
        clock=lambda: now[0],
    )
    reservation = store.reserve("sim-001")
    jpeg = generate_synthetic_jpeg()

    record = store.save(
        reservation.capture_id,
        device_id="sim-001",
        content_type="image/jpeg",
        body=jpeg,
    )

    assert record.device_id == "sim-001"
    assert record.size_bytes == len(jpeg)
    assert record.sha256 == sha256(jpeg).hexdigest()
    assert (record.width, record.height) == (320, 240)
    assert record.path.parent == store.directory
    assert record.path.name == f"{reservation.capture_id.hex}.jpg"
    assert record.path.read_bytes() == jpeg
    assert capture_directory.stat().st_mode & 0o777 == 0o700
    assert record.path.stat().st_mode & 0o777 == 0o600
    assert store.get(reservation.capture_id) == record

    now[0] = 1_601.0
    assert store.purge_expired() == 1
    assert store.get(reservation.capture_id) is None
    assert not record.path.exists()


def test_capture_store_does_not_return_an_expired_capture(tmp_path: Path) -> None:
    now = [1_000.0]
    store = CaptureStore(
        directory=tmp_path,
        ttl_seconds=600,
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

    now[0] = record.expires_at

    assert store.get(record.capture_id) is None
    assert not record.path.exists()


@pytest.mark.parametrize(
    ("device_id", "content_type", "body", "code"),
    [
        ("other-device", "image/jpeg", b"\xff\xd8\xff\xd9", "CAPTURE_OWNERSHIP"),
        ("sim-001", "text/plain", b"\xff\xd8\xff\xd9", "INVALID_CONTENT_TYPE"),
        ("sim-001", "image/jpeg", b"not-a-jpeg", "INVALID_JPEG"),
        ("sim-001", "image/jpeg", b"\xff\xd8\xff" + b"x" * 32, "CAPTURE_TOO_LARGE"),
    ],
)
def test_capture_store_rejects_untrusted_uploads_without_writing(
    tmp_path: Path,
    device_id: str,
    content_type: str,
    body: bytes,
    code: str,
) -> None:
    store = CaptureStore(
        directory=tmp_path,
        ttl_seconds=600,
        max_bytes=16,
    )
    reservation = store.reserve("sim-001")

    with pytest.raises(CaptureValidationError) as error:
        store.save(
            reservation.capture_id,
            device_id=device_id,
            content_type=content_type,
            body=body,
        )

    assert error.value.code == code
    assert list(store.directory.iterdir()) == []


@pytest.mark.parametrize(
    "body",
    [
        jpeg_header_only(width=320, height=240),
        jpeg_header_only(width=65_535, height=65_535),
    ],
)
def test_capture_store_rejects_undecodable_or_oversized_jpeg_dimensions(
    tmp_path: Path,
    body: bytes,
) -> None:
    store = CaptureStore(directory=tmp_path, ttl_seconds=600, max_bytes=2_097_152)
    reservation = store.reserve("sim-001")

    with pytest.raises(CaptureValidationError) as error:
        store.save(
            reservation.capture_id,
            device_id="sim-001",
            content_type="image/jpeg",
            body=body,
        )

    assert error.value.code == "INVALID_JPEG"
    assert list(store.directory.iterdir()) == []


def test_capture_store_purges_only_expired_generated_files_after_restart(
    tmp_path: Path,
) -> None:
    expired = tmp_path / "11111111111111111111111111111111.jpg"
    active = tmp_path / "22222222222222222222222222222222.jpg"
    unknown = tmp_path / "keep-me.jpg"
    linked = tmp_path / "33333333333333333333333333333333.jpg"
    for path in (expired, active, unknown):
        path.write_bytes(b"jpeg")
    linked.symlink_to(unknown)
    os.utime(expired, (80, 80))
    os.utime(active, (95, 95))

    CaptureStore(
        directory=tmp_path,
        ttl_seconds=10,
        max_bytes=2_097_152,
        clock=lambda: 100,
    )

    assert not expired.exists()
    assert active.exists()
    assert unknown.exists()
    assert linked.is_symlink()


def test_capture_store_retains_expired_media_only_with_explicit_persistence(
    tmp_path: Path,
) -> None:
    now = [1_000.0]
    store = CaptureStore(
        directory=tmp_path,
        ttl_seconds=10,
        max_bytes=2_097_152,
        persist=True,
        clock=lambda: now[0],
    )
    reservation = store.reserve("sim-001")
    record = store.save(
        reservation.capture_id,
        device_id="sim-001",
        content_type="image/jpeg",
        body=generate_synthetic_jpeg(),
    )

    now[0] = record.expires_at

    assert store.get(record.capture_id) is None
    assert record.path.exists()


def test_capture_store_never_overwrites_a_preexisting_capture_path(tmp_path: Path) -> None:
    store = CaptureStore(
        directory=tmp_path,
        ttl_seconds=600,
        max_bytes=2_097_152,
    )
    reservation = store.reserve("sim-001")
    destination = tmp_path / f"{reservation.capture_id.hex}.jpg"
    destination.write_bytes(b"operator-owned")

    with pytest.raises(FileExistsError):
        store.save(
            reservation.capture_id,
            device_id="sim-001",
            content_type="image/jpeg",
            body=generate_synthetic_jpeg(),
        )

    assert destination.read_bytes() == b"operator-owned"


def test_capture_failure_event_cannot_cancel_another_devices_reservation(
    tmp_path: Path,
) -> None:
    store = CaptureStore(directory=tmp_path, ttl_seconds=600, max_bytes=2_097_152)
    reservation = store.reserve("sim-001")

    assert store.fail(reservation.capture_id, device_id="other-device") is False

    record = store.save(
        reservation.capture_id,
        device_id="sim-001",
        content_type="image/jpeg",
        body=generate_synthetic_jpeg(),
    )
    assert record.device_id == "sim-001"
