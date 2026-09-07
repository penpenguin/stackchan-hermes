"""Deterministic reconnect policy shared by Simulator fault tests."""

from __future__ import annotations


class ReconnectBackoff:
    """Yield the Protocol v1 reconnect delays and reset after stable uptime."""

    _DELAYS_SECONDS = (1.0, 2.0, 4.0, 8.0, 16.0, 30.0)

    def __init__(self, *, stable_connection_seconds: float = 30.0) -> None:
        if stable_connection_seconds <= 0:
            raise ValueError("stable connection duration must be positive")
        self._stable_connection_seconds = stable_connection_seconds
        self._attempt = 0

    def next_delay_seconds(self) -> float:
        delay = self._DELAYS_SECONDS[min(self._attempt, len(self._DELAYS_SECONDS) - 1)]
        self._attempt += 1
        return delay

    def record_connection(self, *, connected_seconds: float) -> None:
        if connected_seconds < 0:
            raise ValueError("connected duration cannot be negative")
        if connected_seconds >= self._stable_connection_seconds:
            self._attempt = 0
