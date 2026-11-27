"""Forecast error metrics shared by the offline experiment and the live accuracy report."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class ForecastScore:
    """Errors of a set of forecasts against what was observed.

    `bias` is the mean of predicted minus actual: positive means the model
    over-predicts. All values are None when there are no samples.
    """

    samples: int
    mae: float | None
    rmse: float | None
    bias: float | None
    status_accuracy: float | None


def score(
    predicted: Sequence[float],
    actual: Sequence[float],
    predicted_status: Sequence[object],
    actual_status: Sequence[object],
) -> ForecastScore:
    n = len(predicted)
    if not (len(actual) == len(predicted_status) == len(actual_status) == n):
        raise ValueError("All sequences must have the same length")
    if n == 0:
        return ForecastScore(0, None, None, None, None)
    errors = [float(p) - float(a) for p, a in zip(predicted, actual)]
    return ForecastScore(
        samples=n,
        mae=sum(abs(e) for e in errors) / n,
        rmse=math.sqrt(sum(e * e for e in errors) / n),
        bias=sum(errors) / n,
        status_accuracy=sum(p == a for p, a in zip(predicted_status, actual_status)) / n,
    )
