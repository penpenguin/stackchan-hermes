"""One owned deadline for image storage and released-firmware confirmation."""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from time import monotonic
from uuid import UUID

from stackchan_bridge.captures.store import CaptureRecord, CaptureStore, CaptureValidationError
from stackchan_bridge.device_gateway.application import (
    CommandTimedOutError,
    DeviceDisconnectedError,
    DeviceRegistry,
)

_LOGGER = logging.getLogger("stackchan_bridge.captures")


class CaptureCommandFailedError(RuntimeError):
    """A capture failed, with bounded non-secret diagnostic context."""

    code = "CAPTURE_FAILED"

    def __init__(self, message: str, *, details: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.details = details or {}


class CaptureTimedOutError(CaptureCommandFailedError):
    """The common capture deadline expired."""

    code = "CAPTURE_TIMEOUT"


class CaptureCoordinator:
    def __init__(
        self, registry: DeviceRegistry, store: CaptureStore, *, timeout_seconds: float
    ) -> None:
        if not 0 < timeout_seconds <= 120:
            raise ValueError("capture timeout must be in (0, 120]")
        self._registry = registry
        self._store = store
        self._timeout_seconds = timeout_seconds
        self._active: dict[str, UUID] = {}
        self._cancellations: set[asyncio.Task[None]] = set()

    async def take_photo(self, device_id: str, *, quality: int = 80) -> CaptureRecord:
        if device_id in self._active:
            raise CaptureCommandFailedError(
                "camera transaction is busy", details={"reason": "DEVICE_BUSY"}
            )
        started = monotonic()
        try:
            reservation = self._store.reserve(device_id, timeout_seconds=self._timeout_seconds)
        except CaptureValidationError as error:
            raise CaptureCommandFailedError(
                "capture capacity unavailable", details={"reason": error.code}
            ) from error
        capture_id = reservation.capture_id
        self._active[device_id] = capture_id
        command = asyncio.create_task(
            self._registry.send_command(
                device_id,
                "camera.capture",
                {
                    "capture_id": str(capture_id),
                    "quality": quality,
                    "timeout_ms": max(1, int(self._store.remaining_seconds(capture_id) * 1000)),
                },
            )
        )
        finished = asyncio.create_task(self._store.wait_for_completion(capture_id))
        acknowledged = False
        succeeded = False
        waiting = {command, finished}
        try:
            while True:
                done, _ = await asyncio.wait(waiting, return_when=asyncio.FIRST_COMPLETED)
                if finished in done:
                    record = finished.result()
                    succeeded = True
                    return record
                waiting.discard(command)
                try:
                    result = command.result()
                except (CommandTimedOutError, DeviceDisconnectedError):
                    continue
                acknowledged = True
                if not result.payload.ok:
                    reason = (
                        result.payload.error.code.value
                        if result.payload.error
                        else "CAPTURE_FAILED"
                    )
                    self._store.fail(capture_id, device_id=device_id, reason=reason)
        except CaptureValidationError as error:
            # Retention cleanup can remove the transaction before diagnostics run.
            # Keep the original failure and do not claim whether a removed image was saved.
            state: dict[str, object] = {"state": "unavailable", "image_saved": None}
            with suppress(CaptureValidationError):
                state = self._store.status(capture_id, device_id=device_id)
            details = {
                "capture_id": str(capture_id),
                "stage": state["state"],
                "reason": error.code,
                "image_saved": state["image_saved"],
            }
            _LOGGER.warning(
                "capture did not complete",
                extra={
                    "component": "captures",
                    "event": "capture.failed",
                    "device_id": device_id,
                    "duration_ms": round((monotonic() - started) * 1000),
                    **details,
                },
            )
            if error.code in {"CAPTURE_TIMEOUT", "CAPTURE_COMPLETION_TIMEOUT", "CAPTURE_EXPIRED"}:
                failure = CaptureTimedOutError("capture deadline expired", details=details)
                failure.code = error.code
                if (
                    error.code == "CAPTURE_TIMEOUT"
                    and not acknowledged
                    and not self._store.has_device_contact(capture_id)
                ):
                    failure.code = "COMMAND_TIMEOUT"
                raise failure from error
            raise CaptureCommandFailedError("device capture failed", details=details) from error
        finally:
            for task in (command, finished):
                task.cancel()
                with suppress(asyncio.CancelledError, Exception):
                    await task
            if not succeeded:
                self._store.cancel(capture_id)
                cancellation = asyncio.create_task(self._cancel_device(device_id, capture_id))
                self._cancellations.add(cancellation)
                cancellation.add_done_callback(self._cancellations.discard)
            self._active.pop(device_id, None)

    async def _cancel_device(self, device_id: str, capture_id: UUID) -> None:
        with suppress(Exception):
            async with asyncio.timeout(0.1):
                await self._registry.send_command(
                    device_id, "camera.cancel", {"capture_id": str(capture_id)}
                )

    def report_failure(self, device_id: str, capture_id: UUID) -> bool:
        return self._store.fail(capture_id, device_id=device_id)

    def delete_capture(self, capture_id: UUID) -> bool:
        return self._store.delete(capture_id)
