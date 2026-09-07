"""Physical event routing into owned turn cancellation."""

from __future__ import annotations

import logging
from asyncio import Task, create_task
from collections.abc import Mapping
from typing import Protocol
from uuid import UUID

from stackchan_bridge.observability.metrics import BridgeMetrics
from stackchan_bridge.protocol.models import (
    CameraCompletedEvent,
    DeviceErrorEvent,
    EventMessage,
    EventPayload,
)
from stackchan_bridge.turns.coordinator import TurnCoordinator, TurnState

_LOGGER = logging.getLogger("stackchan_bridge.turns")


class TurnCommandSender(Protocol):
    async def send_command(
        self,
        device_id: str,
        name: str,
        args: Mapping[str, object],
        *,
        turn_id: UUID | None = None,
    ) -> object: ...


class CaptureFailureReporter(Protocol):
    def report_failure(self, device_id: str, capture_id: UUID) -> bool: ...


class TurnEventHandler:
    """Remember touch state and treat a repeated press as barge-in."""

    def __init__(
        self,
        coordinator: TurnCoordinator,
        command_sender: TurnCommandSender,
        *,
        capture_failures: CaptureFailureReporter | None = None,
        metrics: BridgeMetrics | None = None,
    ) -> None:
        self._coordinator = coordinator
        self._command_sender = command_sender
        self._capture_failures = capture_failures
        self._metrics = metrics or BridgeMetrics()
        self._last_touch: dict[str, EventPayload] = {}
        self._command_tasks: set[Task[None]] = set()

    async def handle(self, device_id: str, message: EventMessage) -> None:
        if isinstance(message.payload, CameraCompletedEvent):
            if not message.payload.data.ok and self._capture_failures is not None:
                self._capture_failures.report_failure(device_id, message.payload.data.capture_id)
            return
        if isinstance(message.payload, DeviceErrorEvent):
            active = self._coordinator.current(device_id)
            if (
                message.payload.data.code == "AUDIO_DECODE_ERROR"
                and active is not None
                and active.state is TurnState.PLAYING
                and (message.turn_id is None or message.turn_id == active.turn_id)
            ):
                # Firmware already discarded playback; stop upstream work without
                # sending a speech.cancel command for its now-closed stream.
                await self._coordinator.cancel_turn(
                    device_id, active.turn_id, reason="AUDIO_DECODE_ERROR"
                )
            return
        if message.payload.name.startswith("touch."):
            self._last_touch[device_id] = message.payload
            self._metrics.touch_events_total.inc()
        if message.payload.name not in {"touch.tap", "touch.long_press"}:
            return
        active = self._coordinator.current(device_id)
        if active is None or active.state is TurnState.CAPTURING:
            return
        turn_id = active.turn_id
        if not await self._coordinator.cancel_turn(device_id, turn_id, reason="BARGE_IN"):
            return
        task = create_task(self._cancel_device_speech(device_id, turn_id))
        self._command_tasks.add(task)
        task.add_done_callback(self._command_tasks.discard)

    async def _cancel_device_speech(self, device_id: str, turn_id: UUID) -> None:
        try:
            await self._command_sender.send_command(
                device_id,
                "speech.cancel",
                {},
                turn_id=turn_id,
            )
        except RuntimeError:
            # The local turn is already safely cancelled if the device disappeared.
            return
        except Exception:
            _LOGGER.exception(
                "failed to cancel device speech after local turn cancellation",
                extra={
                    "component": "turns",
                    "event": "turn.device_cancel_failed",
                    "device_id": device_id,
                    "turn_id": str(turn_id),
                },
            )

    def last_touch(self, device_id: str) -> EventPayload | None:
        return self._last_touch.get(device_id)
