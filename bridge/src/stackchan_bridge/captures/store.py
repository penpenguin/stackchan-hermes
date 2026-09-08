"""Device-owned, TTL-bounded JPEG reservation and storage."""

from __future__ import annotations

import os
import re
import stat
from asyncio import Event, wait_for
from collections.abc import Callable
from dataclasses import dataclass, field
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from time import monotonic, time
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


@dataclass(slots=True)
class _Transaction:
    reservation: CaptureReservation
    deadline: float
    state: str = "reserved"
    proof: tuple[str, int] | None = None
    reason: str = ""
    image_deleted: bool = False
    device_contact: bool = False
    changed: Event = field(default_factory=Event)

    @property
    def terminal(self) -> bool:
        return self.state in {"succeeded", "failed", "cancelled", "expired"}


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
        monotonic_clock: Callable[[], float] = monotonic,
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
        self._monotonic = monotonic_clock
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not self._persist:
            self._purge_expired_generated_files()
        self._reservations: dict[UUID, CaptureReservation] = {}
        self._records: dict[UUID, CaptureRecord] = {}
        self._failures: set[UUID] = set()
        self._completion_events: dict[UUID, Event] = {}
        self._transactions: dict[UUID, _Transaction] = {}

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

    def reserve(self, device_id: str, *, timeout_seconds: float = 10) -> CaptureReservation:
        if not 0 < timeout_seconds <= 120:
            raise ValueError("capture timeout must be in (0, 120]")
        self.purge_expired()
        if len(self._transactions) >= 1024:
            raise CaptureValidationError("CAPTURE_CAPACITY", "capture transaction capacity reached")
        now = self._clock()
        reservation = CaptureReservation(
            capture_id=uuid4(),
            device_id=device_id,
            expires_at=now + self._ttl_seconds,
        )
        self._reservations[reservation.capture_id] = reservation
        self._transactions[reservation.capture_id] = _Transaction(
            reservation, self._monotonic() + timeout_seconds
        )
        return reservation

    def _transaction(self, capture_id: UUID, device_id: str | None = None) -> _Transaction:
        transaction = self._transactions.get(capture_id)
        if transaction is None:
            raise CaptureValidationError("CAPTURE_NOT_FOUND", "capture was not found")
        if device_id is not None and transaction.reservation.device_id != device_id:
            raise CaptureValidationError("CAPTURE_OWNERSHIP", "capture belongs to another device")
        record = self._records.get(capture_id)
        expires_at = record.expires_at if record else transaction.reservation.expires_at
        if expires_at <= self._clock():
            raise CaptureValidationError("CAPTURE_EXPIRED", "capture expired")
        if not transaction.terminal and transaction.deadline <= self._monotonic():
            transaction.state = "expired"
            transaction.reason = "CAPTURE_COMPLETION_TIMEOUT" if record else "CAPTURE_TIMEOUT"
            transaction.changed.set()
        return transaction

    def remaining_seconds(self, capture_id: UUID) -> float:
        transaction = self._transaction(capture_id)
        return max(0.0, transaction.deadline - self._monotonic())

    def observe_device(self, capture_id: UUID, *, device_id: str) -> None:
        self._transaction(capture_id, device_id).device_contact = True

    def has_device_contact(self, capture_id: UUID) -> bool:
        transaction = self._transactions.get(capture_id)
        return transaction is not None and transaction.device_contact

    def check_upload(self, capture_id: UUID, *, device_id: str) -> float:
        transaction = self._transaction(capture_id, device_id)
        remaining = self.remaining_seconds(capture_id)
        if remaining <= 0 or transaction.state == "expired":
            raise CaptureValidationError("CAPTURE_EXPIRED", "capture upload deadline expired")
        if transaction.image_deleted or transaction.state in {"failed", "cancelled"}:
            raise CaptureValidationError(
                "CAPTURE_NOT_FOUND", "capture is no longer accepting uploads"
            )
        return remaining

    async def wait_upload_closed(self, capture_id: UUID, *, device_id: str) -> None:
        """Wake a streaming upload as soon as its transaction closes."""
        while True:
            remaining = self.check_upload(capture_id, device_id=device_id)
            transaction = self._transaction(capture_id, device_id)
            transaction.changed.clear()
            try:
                await wait_for(transaction.changed.wait(), timeout=remaining)
            except TimeoutError:
                raise TimeoutError("capture upload deadline expired") from None

    def status(self, capture_id: UUID, *, device_id: str) -> dict[str, object]:
        transaction = self._transaction(capture_id, device_id)
        record = self.get(capture_id)
        result: dict[str, object] = {
            "capture_id": str(capture_id),
            "state": transaction.state,
            "remaining_ms": int(self.remaining_seconds(capture_id) * 1000),
            "image_saved": record is not None,
            "expires_at": record.expires_at if record else transaction.reservation.expires_at,
            "reason": transaction.reason,
        }
        if record is not None:
            result.update(sha256=record.sha256, size_bytes=record.size_bytes)
        return result

    def complete(
        self,
        capture_id: UUID,
        *,
        device_id: str,
        ok: bool,
        digest: str = "",
        size_bytes: int = 0,
        reason: str = "CAPTURE_FAILED",
    ) -> bool:
        try:
            transaction = self._transaction(capture_id, device_id)
        except CaptureValidationError:
            return False
        proof = (digest, size_bytes)
        if transaction.terminal:
            return (ok and transaction.state == "succeeded" and transaction.proof == proof) or (
                not ok and transaction.state == "failed" and transaction.reason == reason
            )
        if not ok:
            return self.fail(capture_id, device_id=device_id, reason=reason)
        if re.fullmatch(r"[0-9a-f]{64}", digest) is None or not 0 < size_bytes <= self.max_bytes:
            return False
        record = self._records.get(capture_id)
        if record is not None and (record.sha256, record.size_bytes) != proof:
            return False
        if transaction.proof is not None and transaction.proof != proof:
            return False
        transaction.proof = proof
        if record is not None:
            transaction.state = "succeeded"
        transaction.changed.set()
        return True

    async def wait_for_completion(self, capture_id: UUID) -> CaptureRecord:
        while True:
            transaction = self._transaction(capture_id)
            if transaction.state == "succeeded":
                record = self.get(capture_id)
                if record is None:
                    raise CaptureValidationError("CAPTURE_EXPIRED", "capture image expired")
                return record
            if transaction.terminal:
                raise CaptureValidationError(
                    transaction.reason or "CAPTURE_FAILED", "capture did not complete"
                )
            transaction.changed.clear()
            try:
                await wait_for(
                    transaction.changed.wait(), timeout=self.remaining_seconds(capture_id)
                )
            except TimeoutError:
                if not transaction.terminal:
                    transaction.state = "expired"
                    transaction.reason = (
                        "CAPTURE_COMPLETION_TIMEOUT" if self.get(capture_id) else "CAPTURE_TIMEOUT"
                    )

    def save(
        self,
        capture_id: UUID,
        *,
        device_id: str,
        content_type: str,
        body: bytes,
    ) -> CaptureRecord:
        self.check_upload(capture_id, device_id=device_id)
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
        digest = sha256(body).hexdigest()
        previous = self.get(capture_id)
        if previous is not None:
            if (previous.sha256, previous.size_bytes) != (digest, len(body)):
                raise CaptureValidationError("CAPTURE_CONTENT_MISMATCH", "capture content differs")
            return previous
        if len(body) < 5 or not body.startswith(b"\xff\xd8\xff") or not body.endswith(b"\xff\xd9"):
            raise CaptureValidationError("INVALID_JPEG", "capture does not have JPEG markers")
        width, height = _validated_jpeg_dimensions(body)
        self.check_upload(capture_id, device_id=device_id)

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
            self.check_upload(capture_id, device_id=device_id)
        except Exception:
            if created:
                destination.unlink(missing_ok=True)
            raise
        record = CaptureRecord(
            capture_id=capture_id,
            device_id=device_id,
            content_type="image/jpeg",
            size_bytes=len(body),
            sha256=digest,
            width=width,
            height=height,
            path=destination,
            created_at=now,
            expires_at=now + self._ttl_seconds,
        )
        self._records[capture_id] = record
        transaction = self._transactions[capture_id]
        transaction.state = "image_saved"
        if transaction.proof == (record.sha256, record.size_bytes):
            transaction.state = "succeeded"
        transaction.changed.set()
        completion = self._completion_events.get(capture_id)
        if completion is not None:
            completion.set()
        return record

    def fail(self, capture_id: UUID, *, device_id: str, reason: str = "CAPTURE_FAILED") -> bool:
        try:
            transaction = self._transaction(capture_id, device_id)
        except CaptureValidationError:
            return False
        if transaction.terminal:
            return False
        transaction.state = "failed"
        transaction.reason = reason
        transaction.changed.set()
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
        transaction = self._transactions.get(capture_id)
        if transaction is not None:
            transaction.image_deleted = True
            transaction.changed.set()
        record.path.unlink(missing_ok=True)
        return True

    def cancel(self, capture_id: UUID) -> bool:
        try:
            transaction = self._transaction(capture_id)
        except CaptureValidationError:
            return False
        if transaction.terminal:
            return False
        transaction.state = "cancelled"
        transaction.reason = "CAPTURE_CANCELLED"
        transaction.changed.set()
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
        for capture_id, transaction in list(self._transactions.items()):
            record = self._records.get(capture_id)
            expires_at = record.expires_at if record else transaction.reservation.expires_at
            if expires_at <= now:
                transaction.state = "expired"
                transaction.reason = "CAPTURE_EXPIRED"
                transaction.changed.set()
                del self._transactions[capture_id]
                event = self._completion_events.pop(capture_id, None)
                if event is not None:
                    event.set()
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
