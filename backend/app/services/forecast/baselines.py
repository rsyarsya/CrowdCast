"""Baseline forecasters. Any learned model must beat these to be worth using."""

from __future__ import annotations

from collections.abc import Sequence

from app.services.forecast.base import HORIZONS, check_history


class NaiveForecaster:
    """The future looks like the last observed minute."""

    name = "naive"
    min_history = 1

    def predict(self, history: Sequence[float]) -> dict[int, float]:
        check_history(history, self.min_history)
        return {h: float(history[-1]) for h in HORIZONS}


class MovingAverageForecaster:
    """The future looks like the mean of the last `window` minutes."""

    def __init__(self, window: int = 10) -> None:
        if window < 1:
            raise ValueError("window must be at least 1")
        self.window = window
        self.min_history = window
        self.name = f"moving_average_{window}"

    def predict(self, history: Sequence[float]) -> dict[int, float]:
        check_history(history, self.min_history)
        recent = history[-self.window :]
        mean = sum(recent) / len(recent)
        return {h: mean for h in HORIZONS}
