"""Slow down password guessing by limiting failed logins per client and email."""

import math
import time
from collections import deque
from collections.abc import Callable


class LoginLimiter:
    """Allows `max_failures` failed logins per key within `window_seconds`.

    State lives in memory, like the live hub, so it is per API process and
    resets on restart.
    """

    def __init__(
        self,
        max_failures: int,
        window_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self._clock = clock
        self._failures: dict[str, deque[float]] = {}

    def _recent(self, key: str) -> deque[float] | None:
        failures = self._failures.get(key)
        if failures is None:
            return None
        cutoff = self._clock() - self.window_seconds
        while failures and failures[0] <= cutoff:
            failures.popleft()
        if not failures:
            del self._failures[key]
            return None
        return failures

    def retry_after(self, key: str) -> int | None:
        """Seconds until `key` may try again, or None when it is not blocked."""
        failures = self._recent(key)
        if failures is None or len(failures) < self.max_failures:
            return None
        return max(1, math.ceil(failures[0] + self.window_seconds - self._clock()))

    def record_failure(self, key: str) -> None:
        self._recent(key)
        self._failures.setdefault(key, deque()).append(self._clock())
        if len(self._failures) > 10_000:
            for stale in list(self._failures)[:1000]:
                self._recent(stale)

    def reset(self, key: str) -> None:
        self._failures.pop(key, None)
