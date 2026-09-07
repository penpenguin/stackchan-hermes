"""Small in-memory token buckets for authenticated local/LAN boundaries."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from math import ceil
from time import monotonic


@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    allowed: bool
    retry_after_seconds: int = 0


@dataclass(slots=True)
class _Bucket:
    tokens: float
    updated_at: float


class TokenBucketRateLimiter:
    """Bounded token buckets keyed by an already authenticated identity."""

    def __init__(
        self,
        *,
        rate_per_second: float,
        capacity: int,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        if rate_per_second <= 0:
            raise ValueError("rate must be positive")
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self._rate_per_second = rate_per_second
        self._capacity = capacity
        self._clock = clock
        self._buckets: dict[str, _Bucket] = {}

    def acquire(self, key: str) -> RateLimitDecision:
        now = self._clock()
        bucket = self._buckets.get(key)
        if bucket is None:
            bucket = _Bucket(tokens=float(self._capacity), updated_at=now)
            self._buckets[key] = bucket
        else:
            elapsed = max(0.0, now - bucket.updated_at)
            bucket.tokens = min(
                float(self._capacity),
                bucket.tokens + elapsed * self._rate_per_second,
            )
            bucket.updated_at = now
        if bucket.tokens >= 1:
            bucket.tokens -= 1
            return RateLimitDecision(allowed=True)
        wait_seconds = ceil((1 - bucket.tokens) / self._rate_per_second)
        return RateLimitDecision(allowed=False, retry_after_seconds=max(1, wait_seconds))
