from __future__ import annotations

from collections.abc import Callable, Iterator

import pytest
from stackchan_bridge.observability.reconnect import ReconnectObservationError, observe_reconnect


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.value += seconds


def sequence_probe(values: list[bool]) -> tuple[Callable[[], bool], Iterator[bool]]:
    samples = iter(values)
    return lambda: next(samples), samples


def test_reconnect_observer_ignores_one_transient_loss_and_measures_confirmed_outage() -> None:
    clock = FakeClock()
    probe, _ = sequence_probe(
        [
            True,
            False,
            True,
            False,
            False,
            False,
            True,
        ]
    )

    observation = observe_reconnect(
        probe,
        timeout_seconds=5,
        poll_interval_seconds=0.1,
        loss_confirmations=2,
        clock=clock,
        sleep=clock.sleep,
    )

    assert observation.loss_confirmations == 2
    assert observation.reconnect_seconds == 0.2


def test_reconnect_observer_times_out_when_no_confirmed_loss_occurs() -> None:
    clock = FakeClock()

    with pytest.raises(
        ReconnectObservationError,
        match="confirmed disconnect was not observed before timeout",
    ):
        observe_reconnect(
            lambda: True,
            timeout_seconds=1,
            poll_interval_seconds=0.25,
            clock=clock,
            sleep=clock.sleep,
        )

    assert clock.value == 1
