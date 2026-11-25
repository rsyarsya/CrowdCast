"""Aggregation of smoothed samples into fixed intervals (one CrowdRecord each)."""

from __future__ import annotations

from datetime import datetime, timedelta

from app.services.vision.types import IntervalRecord


class IntervalAggregator:
    """Groups samples into aligned intervals (e.g. 10:00:00-10:00:59) and averages them.

    `add` returns the finished record of the previous interval when a sample from
    a new interval arrives. The stored `people_count` is the rounded mean, i.e.
    the average occupancy during that interval.
    """

    def __init__(self, interval_s: int = 60) -> None:
        if interval_s <= 0:
            raise ValueError("interval_s must be positive")
        self.interval = timedelta(seconds=interval_s)
        self._start: datetime | None = None
        self._total = 0.0
        self._n = 0

    def _bucket_start(self, timestamp: datetime) -> datetime:
        day = timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
        return day + ((timestamp - day) // self.interval) * self.interval

    def add(self, timestamp: datetime, value: float) -> IntervalRecord | None:
        start = self._bucket_start(timestamp)
        finished = None
        if self._start is not None and start != self._start:
            if start < self._start:
                raise ValueError("Samples must arrive in time order")
            finished = self.flush()
        if self._start is None:
            self._start = start
        self._total += value
        self._n += 1
        return finished

    def flush(self) -> IntervalRecord | None:
        """Close the current interval (e.g. at the end of a video) and return its record."""
        if self._start is None or self._n == 0:
            return None
        # int(x + 0.5) rounds .5 up; round() would use banker's rounding (2.5 -> 2).
        record = IntervalRecord(self._start, int(self._total / self._n + 0.5), self._n)
        self._start, self._total, self._n = None, 0.0, 0
        return record
