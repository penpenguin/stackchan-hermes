"""Device-owned, TTL-bounded JPEG reservation and storage."""

from __future__ import annotations

import os
import re
import stat
from asyncio import Event, wait_for
from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from time import time
from uuid import UUID, uuid4

from PIL import Image, UnidentifiedImageError

_GENERATED_CAPTURE_NAME = re.compile(r"^[0-9a-f]{32}\.jpg$")
_MAX_CAPTURE_WIDTH = 320
_MAX_CAPTURE_HEIGHT = 240
_MAX_CAPTURE_PIXELS = _MAX_CAPTURE_WIDTH * _MAX_CAPTURE_HEIGHT


class CaptureValidationError(ValueError):
    """An upload that cannot satisfy its capture reservation."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class CaptureReservation:
    capture_id: UUID
    device_id: str
    expires_at: float


@dataclass(frozen=True, slots=True)
class CaptureRecord:
    capture_id: UUID
    device_id: str
    content_type: str
    size_bytes: int
    sha256: str
    width: int
    height: int
    path: Path
    created_at: float
    expires_at: float


class CaptureStore:
    """Temporary generated-path JPEG store with explicit ownership and TTL."""

    def __init__(
        self,
        *,
        directory: Path,
        ttl_seconds: int,
        max_bytes: int,
        persist: bool = False,
        clock: Callable[[], float] = time,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("capture TTL must be positive")
        if max_bytes <= 0:
            raise ValueError("capture maximum must be positive")
        self.directory = directory.resolve()
        self._ttl_seconds = ttl_seconds
        self._max_bytes = max_bytes
        self._persist = persist
        self._clock = clock
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not self._persist:
            self._purge_expired_generated_files()
        self._reservations: dict[UUID, CaptureReservation] = {}
        self._records: dict[UUID, CaptureRecord] = {}
        self._failures: set[UUID] = set()
        self._completion_events: dict[UUID, Event] = {}

    def _purge_expired_generated_files(self) -> None:
        now = self._clock()
        for entry in self.directory.iterdir():
            if _GENERATED_CAPTURE_NAME.fullmatch(entry.name) is None:
                continue
            file_stat = entry.lstat()
            if not stat.S_ISREG(file_stat.st_mode):
                continue
            if file_stat.st_mtime + self._ttl_seconds <= now:
                entry.unlink()

    @property
    def max_bytes(self) -> int:
        return self._max_bytes

    @property
    def ttl_seconds(self) -> int:
        return self._ttl_seconds

    def reserve(self, device_id: str) -> CaptureReservation:
        now = self._clock()
        reservation = CaptureReservation(
            capture_id=uuid4(),
            device_id=device_id,
            expires_at=now + self._ttl_seconds,
        )
        self._reservations[reservation.capture_id] = reservation
        return reservation

    def save(
        self,
        capture_id: UUID,
        *,
        device_id: str,
        content_type: str,
        body: bytes,
    ) -> CaptureRecord:
        reservation = self._reservations.get(capture_id)
        if reservation is None:
            raise CaptureValidationError("CAPTURE_NOT_FOUND", "capture reservation was not found")
        if capture_id in self._failures:
            raise CaptureValidationError("CAPTURE_NOT_FOUND", "capture reservation was not found")
        now = self._clock()
        if reservation.expires_at <= now:
            del self._reservations[capture_id]
            raise CaptureValidationError("CAPTURE_EXPIRED", "capture reservation expired")
        if reservation.device_id != device_id:
            raise CaptureValidationError("CAPTURE_OWNERSHIP", "capture belongs to another device")
        if content_type.lower() != "image/jpeg":
            raise CaptureValidationError("INVALID_CONTENT_TYPE", "capture must be image/jpeg")
        if len(body) > self._max_bytes:
            raise CaptureValidationError(
                "CAPTURE_TOO_LARGE", "capture exceeds the configured limit"
            )
        if len(body) < 5 or not body.startswith(b"\xff\xd8\xff") or not body.endswith(b"\xff\xd9"):
            raise CaptureValidationError("INVALID_JPEG", "capture does not have JPEG markers")
        width, height = _validated_jpeg_dimensions(body)

        destination = self.directory / f"{capture_id.hex}.jpg"
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        created = False
        try:
            descriptor = os.open(destination, flags, 0o600)
            created = True
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "wb") as output:
                output.write(body)
        except Exception:
            if created:
                destination.unlink(missing_ok=True)
            raise
        record = CaptureRecord(
            capture_id=capture_id,
            device_id=device_id,
            content_type="image/jpeg",
            size_bytes=len(body),
            sha256=sha256(body).hexdigest(),
            width=width,
            height=height,
            path=destination,
            created_at=now,
            expires_at=now + self._ttl_seconds,
        )
        self._records[capture_id] = record
        del self._reservations[capture_id]
        completion = self._completion_events.get(capture_id)
        if completion is not None:
            completion.set()
        return record

    def fail(self, capture_id: UUID, *, device_id: str) -> bool:
        reservation = self._reservations.get(capture_id)
        if reservation is None or reservation.device_id != device_id:
            return False
        self._failures.add(capture_id)
        self._completion_events.setdefault(capture_id, Event()).set()
        return True

    def get(self, capture_id: UUID) -> CaptureRecord | None:
        record = self._records.get(capture_id)
        if record is not None and record.expires_at <= self._clock():
            self._records.pop(capture_id)
            if not self._persist:
                record.path.unlink(missing_ok=True)
            return None
        return record

    def delete(self, capture_id: UUID) -> bool:
        record = self._records.pop(capture_id, None)
        if record is None:
            return False
        record.path.unlink(missing_ok=True)
        return True

    def cancel(self, capture_id: UUID) -> bool:
        removed = self._reservations.pop(capture_id, None) is not None
        failed = capture_id in self._failures
        self._failures.discard(capture_id)
        return removed or failed

    async def wait_for(self, capture_id: UUID, *, timeout_seconds: float) -> CaptureRecord:
        completion = self._completion_events.setdefault(capture_id, Event())
        record = self.get(capture_id)
        if record is not None:
            self._completion_events.pop(capture_id, None)
            return record
        if capture_id in self._failures:
            self._completion_events.pop(capture_id, None)
            raise CaptureValidationError("CAPTURE_FAILED", "device capture failed")
        try:
            await wait_for(completion.wait(), timeout=timeout_seconds)
        finally:
            if self._completion_events.get(capture_id) is completion:
                del self._completion_events[capture_id]
        if capture_id in self._failures:
            raise CaptureValidationError("CAPTURE_FAILED", "device capture failed")
        record = self.get(capture_id)
        if record is None:
            raise CaptureValidationError("CAPTURE_NOT_FOUND", "capture was not stored")
        return record

    def purge_expired(self) -> int:
        now = self._clock()
        expired_reservations = [
            capture_id
            for capture_id, reservation in self._reservations.items()
            if reservation.expires_at <= now
        ]
        for capture_id in expired_reservations:
            del self._reservations[capture_id]
            self._failures.discard(capture_id)

        expired_records = [
            capture_id for capture_id, record in self._records.items() if record.expires_at <= now
        ]
        for capture_id in expired_records:
            record = self._records.pop(capture_id)
            if not self._persist:
                record.path.unlink(missing_ok=True)
        return len(expired_records)


def _validated_jpeg_dimensions(body: bytes) -> tuple[int, int]:
    try:
        with Image.open(BytesIO(body)) as image:
            width, height = image.size
            if (
                image.format != "JPEG"
                or width <= 0
                or height <= 0
                or width > _MAX_CAPTURE_WIDTH
                or height > _MAX_CAPTURE_HEIGHT
                or width * height > _MAX_CAPTURE_PIXELS
            ):
                raise CaptureValidationError(
                    "INVALID_JPEG",
                    "capture dimensions are outside the supported bounds",
                )
            image.verify()
        with Image.open(BytesIO(body)) as image:
            image.load()
    except CaptureValidationError:
        raise
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError, ValueError) as error:
        raise CaptureValidationError("INVALID_JPEG", "capture is not a decodable JPEG") from error
    return width, height
