"""External reconnect observation without controlling either endpoint."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from time import monotonic
from time import sleep as time_sleep


class ReconnectObservationError(RuntimeError):
    """The required connected-loss-reconnected sequence was not observed."""


@dataclass(frozen=True, slots=True)
class ReconnectObservation:
    """Bounded transport observation measured from the first confirmed-loss sample."""

    reconnect_seconds: float
    loss_confirmations: int


def observe_reconnect(
    probe: Callable[[], bool],
    *,
    timeout_seconds: float,
    poll_interval_seconds: float,
    loss_confirmations: int = 2,
    clock: Callable[[], float] = monotonic,
    sleep: Callable[[float], None] = time_sleep,
) -> ReconnectObservation:
    """Observe connected → confirmed loss → connected using one total deadline."""

    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    if poll_interval_seconds <= 0:
        raise ValueError("poll_interval_seconds must be positive")
    if loss_confirmations < 1:
        raise ValueError("loss_confirmations must be positive")
    if not probe():
        raise ReconnectObservationError("device must be connected before observation")

    deadline = clock() + timeout_seconds
    consecutive_losses = 0
    first_loss_at: float | None = None
    while clock() < deadline:
        if probe():
            consecutive_losses = 0
            first_loss_at = None
        else:
            if consecutive_losses == 0:
                first_loss_at = clock()
            consecutive_losses += 1
            if consecutive_losses >= loss_confirmations:
                break
        sleep(poll_interval_seconds)
    else:
        raise ReconnectObservationError("confirmed disconnect was not observed before timeout")

    assert first_loss_at is not None
    while clock() < deadline:
        if probe():
            return ReconnectObservation(
                reconnect_seconds=max(0.0, clock() - first_loss_at),
                loss_confirmations=loss_confirmations,
            )
        sleep(poll_interval_seconds)
    raise ReconnectObservationError("device did not reconnect before timeout")
