from __future__ import annotations

from asyncio import CancelledError, Event, create_task
from uuid import UUID

import pytest
from prometheus_client import generate_latest
from stackchan_bridge.observability.metrics import BridgeMetrics
from stackchan_bridge.turns.coordinator import (
    StaleTurnError,
    TurnBusyError,
    TurnCoordinator,
    TurnState,
    TurnTrigger,
)


class RecordingCancellationHook:
    def __init__(self) -> None:
        self.calls: list[tuple[str, UUID]] = []

    async def cancel_speech(self, device_id: str, turn_id: UUID) -> None:
        self.calls.append((device_id, turn_id))


@pytest.mark.asyncio
async def test_turn_coordinator_cancels_owned_work_and_rejects_stale_results() -> None:
    metrics = BridgeMetrics()
    hook = RecordingCancellationHook()
    coordinator = TurnCoordinator(cancellation_hook=hook, metrics=metrics, clock=lambda: 10.0)
    turn = await coordinator.begin("sim-001", trigger=TurnTrigger.TOUCH)
    started = Event()
    cancelled = Event()

    async def blocking_work() -> None:
        started.set()
        try:
            await Event().wait()
        except CancelledError:
            cancelled.set()
            raise

    task = create_task(blocking_work())
    coordinator.attach_task(turn.turn_id, task)
    await coordinator.transition(turn.turn_id, TurnState.TRANSCRIBING)
    await coordinator.transition(turn.turn_id, TurnState.WAITING_HERMES)
    await started.wait()

    with pytest.raises(TurnBusyError):
        await coordinator.begin("sim-001", trigger=TurnTrigger.BUTTON)
    assert await coordinator.cancel_device("sim-001", reason="user_cancel") is True

    assert cancelled.is_set()
    assert hook.calls == [("sim-001", turn.turn_id)]
    assert coordinator.current("sim-001") is None
    assert b"active_turns 0.0" in generate_latest(metrics.registry)

    replacement = await coordinator.begin("sim-001", trigger=TurnTrigger.BUTTON)
    assert replacement.turn_id != turn.turn_id
    with pytest.raises(StaleTurnError):
        await coordinator.transition(turn.turn_id, TurnState.SYNTHESIZING)


@pytest.mark.asyncio
async def test_turn_coordinator_finalizes_completed_and_failed_turns() -> None:
    now = [10.0]
    metrics = BridgeMetrics()
    coordinator = TurnCoordinator(metrics=metrics, clock=lambda: now[0])
    completed = await coordinator.begin("sim-001", trigger=TurnTrigger.TOUCH)
    for state in (
        TurnState.TRANSCRIBING,
        TurnState.WAITING_HERMES,
        TurnState.SYNTHESIZING,
        TurnState.PLAYING,
    ):
        await coordinator.transition(completed.turn_id, state)
    now[0] = 12.5

    snapshot = await coordinator.complete(completed.turn_id)

    assert snapshot.state is TurnState.COMPLETED
    assert snapshot.timings["total"] == 2.5
    assert coordinator.current("sim-001") is None

    failed = await coordinator.begin("sim-001", trigger=TurnTrigger.BUTTON)
    now[0] = 13.0
    failure = await coordinator.fail(failed.turn_id, reason="STT_ERROR")
    assert failure.state is TurnState.FAILED
    assert failure.failure_reason == "STT_ERROR"
    assert coordinator.current("sim-001") is None


@pytest.mark.asyncio
async def test_turn_coordinator_ignores_a_stale_targeted_cancellation() -> None:
    hook = RecordingCancellationHook()
    coordinator = TurnCoordinator(cancellation_hook=hook)
    active = await coordinator.begin("sim-001", trigger=TurnTrigger.TOUCH)

    assert (
        await coordinator.cancel_turn(
            "sim-001",
            UUID("98f65be3-801e-4395-b634-28dd98f2445b"),
            reason="stale_control_request",
        )
        is False
    )
    assert coordinator.current("sim-001") is active
    assert hook.calls == []

    assert await coordinator.cancel_turn("sim-001", active.turn_id, reason="control_request")
    assert coordinator.current("sim-001") is None
    assert hook.calls == [("sim-001", active.turn_id)]
