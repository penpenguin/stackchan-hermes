"""Bridge-owned camera capture coordination."""

from __future__ import annotations

import builtins
from uuid import UUID

from stackchan_bridge.captures.store import (
    CaptureRecord,
    CaptureStore,
    CaptureValidationError,
)
from stackchan_bridge.device_gateway.application import DeviceRegistry


class CaptureCommandFailedError(RuntimeError):
    """The device rejected a camera capture command."""


class CaptureTimedOutError(RuntimeError):
    """The device did not upload a capture within the configured deadline."""


class CaptureCoordinator:
    """Reserve an ID, command one device, and await its authenticated upload."""

    def __init__(
        self,
        registry: DeviceRegistry,
        store: CaptureStore,
        *,
        timeout_seconds: float,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("capture timeout must be positive")
        self._registry = registry
        self._store = store
        self._timeout_seconds = timeout_seconds

    async def take_photo(self, device_id: str, *, quality: int = 80) -> CaptureRecord:
        reservation = self._store.reserve(device_id)
        try:
            result = await self._registry.send_command(
                device_id,
                "camera.capture",
                {"capture_id": str(reservation.capture_id), "quality": quality},
            )
            if not result.payload.ok:
                raise CaptureCommandFailedError("device rejected capture")
            return await self._store.wait_for(
                reservation.capture_id,
                timeout_seconds=self._timeout_seconds,
            )
        except builtins.TimeoutError as error:
            raise CaptureTimedOutError("capture upload timed out") from error
        except CaptureValidationError as error:
            if error.code == "CAPTURE_FAILED":
                raise CaptureCommandFailedError("device capture failed") from error
            raise
        finally:
            self._store.cancel(reservation.capture_id)

    def report_failure(self, device_id: str, capture_id: UUID) -> bool:
        return self._store.fail(capture_id, device_id=device_id)

    def delete_capture(self, capture_id: UUID) -> bool:
        return self._store.delete(capture_id)
