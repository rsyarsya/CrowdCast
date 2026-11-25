"""Smoothing of per-sample people counts."""

from __future__ import annotations

from collections import deque
from statistics import median


class RollingMedian:
    """Median of the counts seen in the last `window_s` seconds.

    The median ignores short spikes (a person hidden for one sample, a flickering
    false detection) better than a mean. The window is in seconds, not samples,
    so the behavior does not change when the detection rate (fps) changes.
    A longer window is more stable but reacts more slowly to real changes.
    """

    def __init__(self, window_s: float = 5.0) -> None:
        if window_s <= 0:
            raise ValueError("window_s must be positive")
        self.window_s = window_s
        self._samples: deque[tuple[float, int]] = deque()

    def update(self, t: float, count: int) -> float:
        """Add a sample at time `t` (seconds) and return the current median."""
        if self._samples and t < self._samples[-1][0]:
            raise ValueError("Samples must arrive in time order")
        self._samples.append((t, count))
        while self._samples[0][0] <= t - self.window_s:
            self._samples.popleft()
        return float(median(c for _, c in self._samples))

    def reset(self) -> None:
        self._samples.clear()
