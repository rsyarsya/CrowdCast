"""Common interface of the crowd forecasters.

A forecaster looks at the per-minute people counts of one camera (oldest
first, one value per minute, no gaps) and predicts the count `h` minutes after
the last observed minute, for every horizon in HORIZONS.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

HORIZONS: tuple[int, ...] = (5, 15, 30)


class Forecaster(Protocol):
    name: str
    min_history: int

    def predict(self, history: Sequence[float]) -> dict[int, float]: ...


def check_history(history: Sequence[float], min_history: int) -> None:
    if len(history) < min_history:
        raise ValueError(f"Need at least {min_history} minutes of history, got {len(history)}")
