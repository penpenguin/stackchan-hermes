"""Cancellation-safe one-active-turn-per-device coordination."""

from __future__ import annotations

import logging
from asyncio import Event, Lock, Task, current_task, gather
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from time import monotonic
from typing import Any, Protocol
from uuid import UUID, uuid4

from stackchan_bridge.observability.metrics import BridgeMetrics

_LOGGER = logging.getLogger("stackchan_bridge.turns")


class TurnState(StrEnum):
    CAPTURING = "CAPTURING"
    TRANSCRIBING = "TRANSCRIBING"
    WAITING_HERMES = "WAITING_HERMES"
    SYNTHESIZING = "SYNTHESIZING"
    PLAYING = "PLAYING"
    CANCELLING = "CANCELLING"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"


class TurnTrigger(StrEnum):
    TOUCH = "touch"
    BUTTON = "button"
    WAKEWORD = "wakeword"
    CONTROL_API = "control_api"
    SIMULATOR = "simulator"


class TurnBusyError(RuntimeError):
    """A device already owns an active turn."""


class StaleTurnError(RuntimeError):
    """A late task attempted to mutate a turn it no longer owns."""


class InvalidTurnTransitionError(RuntimeError):
    """A current turn attempted a state transition outside the table."""


class TurnCancellationHook(Protocol):
    async def cancel_speech(self, device_id: str, turn_id: UUID) -> None: ...


class NullTurnCancellationHook:
    async def cancel_speech(self, device_id: str, turn_id: UUID) -> None:
        return None


@dataclass(slots=True)
class Turn:
    turn_id: UUID
    device_id: str
    started_at: float
    trigger: TurnTrigger
    state: TurnState = TurnState.CAPTURING
    input_stream_id: UUID | None = None
    capture_id: UUID | None = None
    transcript: str | None = None
    conversation_name: str | None = None
    hermes_response_id: str | None = None
    output_stream_ids: list[UUID] = field(default_factory=list)
    cancellation: Event = field(default_factory=Event, repr=False)
    tasks: set[Task[Any]] = field(default_factory=set, repr=False)
    timings: dict[str, float] = field(default_factory=dict)
    failure_reason: str | None = None


_ALLOWED_TRANSITIONS: dict[TurnState, frozenset[TurnState]] = {
    TurnState.CAPTURING: frozenset(
        {TurnState.TRANSCRIBING, TurnState.CANCELLING, TurnState.FAILED}
    ),
    TurnState.TRANSCRIBING: frozenset(
        {TurnState.WAITING_HERMES, TurnState.CANCELLING, TurnState.FAILED}
    ),
    TurnState.WAITING_HERMES: frozenset(
        {TurnState.SYNTHESIZING, TurnState.CANCELLING, TurnState.FAILED}
    ),
    TurnState.SYNTHESIZING: frozenset({TurnState.PLAYING, TurnState.CANCELLING, TurnState.FAILED}),
    TurnState.PLAYING: frozenset({TurnState.COMPLETED, TurnState.CANCELLING, TurnState.FAILED}),
    TurnState.CANCELLING: frozenset(),
    TurnState.FAILED: frozenset(),
    TurnState.COMPLETED: frozenset(),
}


class TurnCoordinator:
    """Own mutable turn state and make late asynchronous results harmless."""

    def __init__(
        self,
        *,
        cancellation_hook: TurnCancellationHook | None = None,
        metrics: BridgeMetrics | None = None,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self._active: dict[str, Turn] = {}
        self._lock = Lock()
        self._cancellation_hook = cancellation_hook or NullTurnCancellationHook()
        self._metrics = metrics or BridgeMetrics()
        self._clock = clock

    async def begin(
        self,
        device_id: str,
        *,
        trigger: TurnTrigger,
        turn_id: UUID | None = None,
        initial_state: TurnState = TurnState.CAPTURING,
    ) -> Turn:
        if initial_state not in {TurnState.CAPTURING, TurnState.SYNTHESIZING}:
            raise ValueError("initial state must be CAPTURING or SYNTHESIZING")
        async with self._lock:
            if device_id in self._active:
                raise TurnBusyError(f"device already has an active turn: {device_id}")
            selected_turn_id = turn_id or uuid4()
            if any(turn.turn_id == selected_turn_id for turn in self._active.values()):
                raise TurnBusyError(f"turn id is already active: {selected_turn_id}")
            turn = Turn(
                turn_id=selected_turn_id,
                device_id=device_id,
                started_at=self._clock(),
                trigger=trigger,
                state=initial_state,
                conversation_name=f"stackchan:{device_id}",
            )
            self._active[device_id] = turn
            self._metrics.active_turns.inc()
            _LOGGER.info(
                "turn started",
                extra={
                    "component": "turns",
                    "event": "turn.started",
                    "device_id": device_id,
                    "turn_id": str(turn.turn_id),
                },
            )
            return turn

    def current(self, device_id: str) -> Turn | None:
        return self._active.get(device_id)

    def attach_task(self, turn_id: UUID, task: Task[Any]) -> None:
        turn = self._find_owned_turn(turn_id)
        turn.tasks.add(task)
        task.add_done_callback(turn.tasks.discard)

    async def transition(self, turn_id: UUID, state: TurnState) -> Turn:
        async with self._lock:
            turn = self._find_owned_turn(turn_id)
            if state not in _ALLOWED_TRANSITIONS[turn.state]:
                raise InvalidTurnTransitionError(f"cannot transition {turn.state} to {state}")
            turn.state = state
            turn.timings[state.value] = self._clock() - turn.started_at
            return turn

    async def cancel_device(self, device_id: str, *, reason: str) -> bool:
        return await self._cancel_owned(device_id, expected_turn_id=None, reason=reason)

    async def cancel_turn(self, device_id: str, turn_id: UUID, *, reason: str) -> bool:
        """Cancel only when the caller still targets the active turn."""

        return await self._cancel_owned(device_id, expected_turn_id=turn_id, reason=reason)

    async def _cancel_owned(
        self,
        device_id: str,
        *,
        expected_turn_id: UUID | None,
        reason: str,
    ) -> bool:
        async with self._lock:
            turn = self._active.get(device_id)
            if turn is None or (expected_turn_id is not None and turn.turn_id != expected_turn_id):
                return False
            turn.state = TurnState.CANCELLING
            turn.failure_reason = reason
            turn.cancellation.set()
            caller = current_task()
            tasks = [task for task in turn.tasks if task is not caller and not task.done()]
        for task in tasks:
            task.cancel()
        try:
            if tasks:
                await gather(*tasks, return_exceptions=True)
            await self._cancellation_hook.cancel_speech(turn.device_id, turn.turn_id)
        finally:
            async with self._lock:
                if self._active.get(device_id) is turn:
                    del self._active[device_id]
                    self._metrics.active_turns.dec()
                    elapsed = self._clock() - turn.started_at
                    turn.timings["total"] = elapsed
                    self._metrics.turn_total_duration_seconds.observe(elapsed)
                    _LOGGER.info(
                        "turn cancelled",
                        extra={
                            "component": "turns",
                            "event": "turn.cancelled",
                            "device_id": turn.device_id,
                            "turn_id": str(turn.turn_id),
                            "duration_ms": elapsed * 1_000,
                            "error_code": reason,
                        },
                    )
        return True

    async def complete(self, turn_id: UUID) -> Turn:
        async with self._lock:
            turn = self._find_owned_turn(turn_id)
            if TurnState.COMPLETED not in _ALLOWED_TRANSITIONS[turn.state]:
                raise InvalidTurnTransitionError(f"cannot complete turn from {turn.state}")
            turn.state = TurnState.COMPLETED
            elapsed = self._finalize_owned_turn(turn)
            _LOGGER.info(
                "turn completed",
                extra={
                    "component": "turns",
                    "event": "turn.completed",
                    "device_id": turn.device_id,
                    "turn_id": str(turn.turn_id),
                    "duration_ms": elapsed * 1_000,
                },
            )
            return turn

    async def fail(self, turn_id: UUID, *, reason: str) -> Turn:
        async with self._lock:
            turn = self._find_owned_turn(turn_id)
            if TurnState.FAILED not in _ALLOWED_TRANSITIONS[turn.state]:
                raise InvalidTurnTransitionError(f"cannot fail turn from {turn.state}")
            turn.state = TurnState.FAILED
            turn.failure_reason = reason
            elapsed = self._finalize_owned_turn(turn)
            _LOGGER.warning(
                "turn failed",
                extra={
                    "component": "turns",
                    "event": "turn.failed",
                    "device_id": turn.device_id,
                    "turn_id": str(turn.turn_id),
                    "duration_ms": elapsed * 1_000,
                    "error_code": reason,
                },
            )
            return turn

    def _find_owned_turn(self, turn_id: UUID) -> Turn:
        turn = next(
            (candidate for candidate in self._active.values() if candidate.turn_id == turn_id),
            None,
        )
        if turn is None:
            raise StaleTurnError(f"turn is no longer active: {turn_id}")
        return turn

    def _finalize_owned_turn(self, turn: Turn) -> float:
        elapsed = self._clock() - turn.started_at
        turn.timings["total"] = elapsed
        del self._active[turn.device_id]
        self._metrics.active_turns.dec()
        self._metrics.turn_total_duration_seconds.observe(elapsed)
        return elapsed
