from datetime import datetime

from pydantic import BaseModel, field_serializer

from app.schemas.monitoring import to_local_time
from app.services.prediction_accuracy import HorizonAccuracy


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, 3)


class HorizonAccuracyOut(BaseModel):
    """Errors in people for one horizon. Metrics are null when `samples` is 0."""

    horizon_minutes: int
    samples: int
    mae: float | None
    rmse: float | None
    bias: float | None
    status_accuracy: float | None
    model_names: list[str]

    @classmethod
    def from_result(cls, result: HorizonAccuracy) -> "HorizonAccuracyOut":
        s = result.score
        return cls(
            horizon_minutes=result.horizon_minutes,
            samples=s.samples,
            mae=_round(s.mae),
            rmse=_round(s.rmse),
            bias=_round(s.bias),
            status_accuracy=_round(s.status_accuracy),
            model_names=result.model_names,
        )


class PredictionAccuracyOut(BaseModel):
    """How close stored forecasts were to the counts observed at their target time."""

    camera_id: str
    start: datetime
    end: datetime
    horizons: list[HorizonAccuracyOut]

    @field_serializer("start", "end")
    def serialize_times(self, value: datetime) -> str:
        return to_local_time(value).isoformat()
