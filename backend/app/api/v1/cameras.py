from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.api.deps import DbSession, LiveHubDep, get_current_user
from app.core.config import get_settings
from app.models import Camera
from app.schemas.monitoring import (
    CameraOut,
    LiveStateOut,
    MonitoringRecordOut,
    MonitoringSummaryOut,
    PredictionOut,
    SummaryPointOut,
)
from app.services import monitoring

# Every monitoring route needs a logged-in user (operator or admin).
router = APIRouter(
    prefix="/cameras",
    tags=["monitoring"],
    dependencies=[Depends(get_current_user)],
)

# Stable error codes the frontend can branch on.
CAMERA_NOT_FOUND = "camera_not_found"
NO_MONITORING_DATA = "no_monitoring_data"
NO_PREDICTION = "no_prediction"
NO_LIVE_DATA = "no_live_data"
NO_STREAM = "no_stream"

NOT_FOUND_DOC = {
    401: {"description": "not_authenticated or invalid_token"},
    404: {"description": "camera_not_found or no data yet"},
}


async def get_camera_or_404(
    db: DbSession,
    camera_id: Annotated[str, Path(description="Public camera code, e.g. CAM-01")],
) -> Camera:
    camera = await monitoring.get_camera_by_code(db, camera_id)
    if camera is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=CAMERA_NOT_FOUND)
    return camera


CameraDep = Annotated[Camera, Depends(get_camera_or_404)]


def require_aware(value: datetime | None, name: str) -> None:
    if value is not None and value.tzinfo is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"{name} must include a timezone offset",
        )


@router.get("", response_model=list[CameraOut])
async def list_cameras(db: DbSession) -> list[CameraOut]:
    return [CameraOut.from_model(camera) for camera in await monitoring.list_cameras(db)]


@router.get(
    "/{camera_id}/monitoring/latest",
    response_model=MonitoringRecordOut,
    responses=NOT_FOUND_DOC,
)
async def get_latest_monitoring(db: DbSession, camera: CameraDep) -> MonitoringRecordOut:
    record = await monitoring.get_latest_record(db, camera)
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=NO_MONITORING_DATA)
    return MonitoringRecordOut.from_model(camera, record)


@router.get(
    "/{camera_id}/monitoring",
    response_model=list[MonitoringRecordOut],
    responses=NOT_FOUND_DOC,
)
async def list_monitoring(
    db: DbSession,
    camera: CameraDep,
    start: Annotated[
        datetime | None, Query(description="ISO 8601 with offset, inclusive")
    ] = None,
    end: Annotated[
        datetime | None, Query(description="ISO 8601 with offset, inclusive")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=2000)] = 500,
) -> list[MonitoringRecordOut]:
    require_aware(start, "start")
    require_aware(end, "end")
    if start is not None and end is not None and start > end:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, detail="start must not be after end"
        )
    records = await monitoring.list_records(db, camera, start, end, limit)
    return [MonitoringRecordOut.from_model(camera, record) for record in records]


BUCKETS = {
    "5m": timedelta(minutes=5),
    "15m": timedelta(minutes=15),
    "1h": timedelta(hours=1),
    "1d": timedelta(days=1),
}
MAX_BUCKETS = 2000


@router.get(
    "/{camera_id}/monitoring/summary",
    response_model=MonitoringSummaryOut,
    responses=NOT_FOUND_DOC,
)
async def summarize_monitoring(
    db: DbSession,
    camera: CameraDep,
    bucket: Annotated[Literal["5m", "15m", "1h", "1d"], Query()] = "15m",
    start: Annotated[
        datetime | None, Query(description="ISO 8601 with offset, inclusive; default end - 24 h")
    ] = None,
    end: Annotated[
        datetime | None, Query(description="ISO 8601 with offset, exclusive; default now")
    ] = None,
) -> MonitoringSummaryOut:
    """History grouped per bucket for long ranges. Buckets align to midnight in TIMEZONE."""
    require_aware(start, "start")
    require_aware(end, "end")
    end = end or datetime.now(timezone.utc)
    start = start or end - timedelta(hours=24)
    if start >= end:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, detail="start must be before end"
        )
    size = BUCKETS[bucket]
    if (end - start) / size > MAX_BUCKETS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="too_many_buckets")
    origin = datetime(2000, 1, 1, tzinfo=ZoneInfo(get_settings().TIMEZONE))
    buckets = await monitoring.summarize_records(db, camera, start, end, size, origin)
    return MonitoringSummaryOut(
        camera_id=camera.code,
        location=camera.location,
        bucket=bucket,
        start=start,
        end=end,
        points=[SummaryPointOut.from_bucket(b) for b in buckets],
    )


@router.get(
    "/{camera_id}/live",
    response_model=LiveStateOut,
    responses=NOT_FOUND_DOC,
)
async def get_live(camera: CameraDep, hub: LiveHubDep) -> LiveStateOut:
    state = hub.get_live(camera.code)
    if state is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=NO_LIVE_DATA)
    return LiveStateOut.from_state(camera.code, state)


@router.get(
    "/{camera_id}/predictions/latest",
    response_model=list[PredictionOut],
    responses=NOT_FOUND_DOC,
)
async def get_latest_predictions(db: DbSession, camera: CameraDep) -> list[PredictionOut]:
    predictions = await monitoring.get_latest_predictions(db, camera)
    if not predictions:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=NO_PREDICTION)
    return [PredictionOut.from_model(camera, p) for p in predictions]

