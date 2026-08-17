"""Small in-memory sliding window rate limiter for low-volume endpoints."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from math import ceil
from threading import Lock
from time import monotonic


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    retry_after_seconds: int | None = None


class SlidingWindowRateLimiter:
    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = {}
        self._lock = Lock()

    def check(self, *, key: str, max_attempts: int, window_seconds: int) -> RateLimitDecision:
        if max_attempts <= 0 or window_seconds <= 0:
            return RateLimitDecision(allowed=True)

        now = monotonic()
        window_start = now - window_seconds
        with self._lock:
            bucket = self._events.setdefault(key, deque())
            while bucket and bucket[0] <= window_start:
                bucket.popleft()
            if len(bucket) >= max_attempts:
                retry_after = max(1, ceil((bucket[0] + window_seconds) - now))
                if not bucket:
                    self._events.pop(key, None)
                return RateLimitDecision(allowed=False, retry_after_seconds=retry_after)
            bucket.append(now)
            return RateLimitDecision(allowed=True)

    def clear(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._events.clear()
                return
            self._events.pop(key, None)
