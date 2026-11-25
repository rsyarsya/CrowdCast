"""Linear regression on the last `lags` minutes, one model per horizon.

Fitting needs numpy (experiments); predicting is plain Python, so a fitted
model saved as JSON runs anywhere.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from app.services.forecast.base import HORIZONS, check_history


class LinearLagForecaster:
    def __init__(self, lags: int, coef: dict[int, list[float]], intercept: dict[int, float]) -> None:
        if any(len(coef[h]) != lags for h in HORIZONS):
            raise ValueError("Each horizon needs one coefficient per lag")
        self.lags = lags
        self.min_history = lags
        self.coef = coef
        self.intercept = intercept
        self.name = f"linear_lag{lags}"

    def predict(self, history: Sequence[float]) -> dict[int, float]:
        check_history(history, self.min_history)
        x = history[-self.lags :]
        return {h: self.intercept[h] + sum(w * v for w, v in zip(self.coef[h], x)) for h in HORIZONS}

    @classmethod
    def fit(cls, series: Sequence[float], lags: int = 30, ridge: float = 1.0) -> LinearLagForecaster:
        """Ridge regression: predict series[i + h] from series[i - lags + 1 : i + 1].

        Ridge adds `ridge * ||w||^2` to the squared error, which keeps the 30
        weights small and stable when neighbouring minutes are strongly correlated.
        """
        import numpy as np

        values = np.asarray(series, dtype=float)
        last = len(values) - max(HORIZONS)
        if last <= lags:
            raise ValueError("Series is too short for these lags and horizons")
        X = np.stack([values[i - lags + 1 : i + 1] for i in range(lags - 1, last)])
        mean_x = X.mean(axis=0)
        Xc = X - mean_x
        coef, intercept = {}, {}
        for h in HORIZONS:
            y = values[lags - 1 + h : last + h]
            mean_y = y.mean()
            # Solve (Xc^T Xc + ridge I) w = Xc^T (y - mean_y); the intercept is not penalized.
            w = np.linalg.solve(Xc.T @ Xc + ridge * np.eye(lags), Xc.T @ (y - mean_y))
            coef[h] = w.tolist()
            intercept[h] = float(mean_y - mean_x @ w)
        return cls(lags, coef, intercept)

    def to_dict(self) -> dict:
        return {
            "type": "linear",
            "lags": self.lags,
            "coef": {str(h): self.coef[h] for h in HORIZONS},
            "intercept": {str(h): self.intercept[h] for h in HORIZONS},
        }

    @classmethod
    def from_dict(cls, data: dict) -> LinearLagForecaster:
        return cls(
            data["lags"],
            {int(h): [float(v) for v in w] for h, w in data["coef"].items()},
            {int(h): float(b) for h, b in data["intercept"].items()},
        )

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(self.to_dict()), encoding="utf-8")
