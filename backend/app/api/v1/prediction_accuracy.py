from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import DbSession, get_current_user
from app.api.v1.cameras import NOT_FOUND_DOC, CameraDep, require_aware
from app.schemas.prediction_accuracy import HorizonAccuracyOut, PredictionAccuracyOut
from app.services.prediction_accuracy import prediction_accuracy

router = APIRouter(
    prefix="/cameras",
    tags=["monitoring"],
    dependencies=[Depends(get_current_user)],
)


@router.get(
    "/{camera_id}/predictions/accuracy",
    response_model=PredictionAccuracyOut,
    responses=NOT_FOUND_DOC,
)
async def get_prediction_accuracy(
    db: DbSession,
    camera: CameraDep,
    hours: Annotated[int, Query(ge=1, le=168, description="Window length")] = 24,
    end: Annotated[
        datetime | None, Query(description="ISO 8601 with offset, default now")
    ] = None,
) -> PredictionAccuracyOut:
    """Forecast errors per horizon for predictions whose target time is in the window.

    Each prediction is compared with the record at its target time; predictions
    whose target time has no record yet are not counted.
    """
    require_aware(end, "end")
    end = end or datetime.now(timezone.utc)
    start = end - timedelta(hours=hours)
    results = await prediction_accuracy(db, camera, start, end)
    return PredictionAccuracyOut(
        camera_id=camera.code,
        start=start,
        end=end,
        horizons=[HorizonAccuracyOut.from_result(r) for r in results],
    )
