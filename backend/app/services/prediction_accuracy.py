"""Accuracy of stored forecasts against the records observed at their target time."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import and_, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Camera, CrowdRecord, Prediction
from app.services.forecast.metrics import ForecastScore, score


@dataclass(frozen=True)
class HorizonAccuracy:
    horizon_minutes: int
    score: ForecastScore
    model_names: list[str]


async def prediction_accuracy(
    session: AsyncSession,
    camera: Camera,
    start: datetime,
    end: datetime,
    include_simulation: bool = False,
) -> list[HorizonAccuracy]:
    """Per-horizon errors of predictions whose target time lies in [start, end].

    Predictions are matched to the record at exactly timestamp + horizon, which
    holds because records and predictions both sit on interval boundaries.
    Predictions without a matching record yet are left out.
    """
    target_time = Prediction.timestamp + Prediction.horizon_minutes * literal_column(
        "interval '1 minute'"
    )
    query = (
        select(
            Prediction.horizon_minutes,
            Prediction.predicted_count,
            Prediction.predicted_status,
            Prediction.model_name,
            CrowdRecord.people_count,
            CrowdRecord.crowd_status,
        )
        .join(
            CrowdRecord,
            and_(
                CrowdRecord.camera_id == Prediction.camera_id,
                CrowdRecord.timestamp == target_time,
            ),
        )
        .where(
            Prediction.camera_id == camera.id,
            CrowdRecord.timestamp >= start,
            CrowdRecord.timestamp <= end,
        )
    )
    if not include_simulation:
        query = query.where(Prediction.is_simulation.is_(False))

    columns: dict[int, tuple[list, list, list, list]] = defaultdict(lambda: ([], [], [], []))
    models: dict[int, set[str]] = defaultdict(set)
    for horizon, predicted, predicted_status, model, actual, actual_status in await session.execute(query):
        predicted_counts, actual_counts, predicted_statuses, actual_statuses = columns[horizon]
        predicted_counts.append(predicted)
        actual_counts.append(actual)
        predicted_statuses.append(predicted_status)
        actual_statuses.append(actual_status)
        models[horizon].add(model)

    return [
        HorizonAccuracy(horizon, score(*columns[horizon]), sorted(models[horizon]))
        for horizon in sorted(columns)
    ]
