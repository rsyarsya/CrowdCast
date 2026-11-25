"""Forecasts made by the worker each time a per-minute record is finished."""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from app.services.forecast.base import Forecaster
from app.services.vision.classifier import StatusThresholds, classify
from app.services.vision.types import CrowdStatus

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ForecastPoint:
    timestamp: datetime  # last observed minute; target time = timestamp + horizon
    horizon_minutes: int
    predicted_count: int
    predicted_status: CrowdStatus
    model_name: str


class PredictionSender(Protocol):
    def post_predictions(self, predictions: list[ForecastPoint]) -> None: ...


class ForecastRunner:
    """Keeps the recent per-minute history and forecasts after every new minute.

    The forecasters assume one value per minute without gaps. When a gap longer
    than `max_gap` appears (worker restart, video loop, API outage), the history
    restarts and forecasting waits until enough new minutes are collected.
    """

    def __init__(
        self,
        forecaster: Forecaster,
        thresholds: StatusThresholds,
        interval: timedelta = timedelta(minutes=1),
        max_gap: timedelta = timedelta(minutes=5),
        max_history: int = 180,
    ) -> None:
        self.forecaster = forecaster
        self.thresholds = thresholds
        self.interval = interval
        self.max_gap = max_gap
        self._history: deque[tuple[datetime, int]] = deque(maxlen=max_history)

    @property
    def history_length(self) -> int:
        return len(self._history)

    def seed(self, records: list[tuple[datetime, int]]) -> None:
        """Load history from the API (oldest first) when the worker starts."""
        for timestamp, count in records:
            self._append(timestamp, count)

    def _append(self, timestamp: datetime, count: int) -> None:
        if self._history:
            last = self._history[-1][0]
            if timestamp <= last:
                return  # duplicate or out of order; keep the series strictly increasing
            if timestamp - last > self.max_gap:
                logger.info("History gap of %s; restarting forecast history", timestamp - last)
                self._history.clear()
        self._history.append((timestamp, count))

    def on_record(self, timestamp: datetime, count: int) -> list[ForecastPoint]:
        self._append(timestamp, count)
        values = self._fill_small_gaps()
        if len(values) < self.forecaster.min_history:
            return []
        predicted = self.forecaster.predict(values)
        return [
            ForecastPoint(
                timestamp=timestamp,
                horizon_minutes=h,
                predicted_count=max(0, round(value)),
                predicted_status=classify(max(0, round(value)), self.thresholds),
                model_name=self.forecaster.name,
            )
            for h, value in predicted.items()
        ]

    def _fill_small_gaps(self) -> list[float]:
        """One value per minute: missing minutes (shorter than max_gap) repeat the previous value."""
        values: list[float] = []
        previous: datetime | None = None
        for timestamp, count in self._history:
            if previous is not None:
                missing = int((timestamp - previous) / self.interval) - 1
                values.extend([values[-1]] * max(0, missing))
            values.append(float(count))
            previous = timestamp
        return values
