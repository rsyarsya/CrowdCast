"""Load the forecaster chosen by the forecasting experiment."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from app.services.forecast.base import Forecaster
from app.services.forecast.baselines import MovingAverageForecaster, NaiveForecaster
from app.services.forecast.linear import LinearLagForecaster

logger = logging.getLogger(__name__)

FALLBACK_WINDOW = 10


def load_forecaster(path: Path | None) -> Forecaster:
    """`.json`: linear or baseline model; `.pt`: GRU. Missing file: moving average."""
    if path is None or not path.exists():
        logger.warning(
            "No forecast model at %s; using a %d-minute moving average", path, FALLBACK_WINDOW
        )
        return MovingAverageForecaster(FALLBACK_WINDOW)
    if path.suffix == ".pt":
        from app.services.forecast.gru import GruForecaster

        return GruForecaster.load(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    kind = data.get("type")
    if kind == "linear":
        return LinearLagForecaster.from_dict(data)
    if kind == "moving_average":
        return MovingAverageForecaster(int(data["window"]))
    if kind == "naive":
        return NaiveForecaster()
    raise ValueError(f"Unknown forecaster type {kind!r} in {path}")


def find_model_file(models_dir: Path, camera_code: str) -> Path | None:
    for suffix in (".pt", ".json"):
        path = models_dir / f"{camera_code}{suffix}"
        if path.exists():
            return path
    return None
