from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from fastapi.responses import StreamingResponse

from app.api.deps import DbSession, LiveHubDep
from app.core.config import get_settings
from app.models import Camera
from app.schemas.monitoring import (
    CameraOut,
    LiveStateOut,
    MonitoringRecordOut,
    PredictionOut,
)
from app.services import monitoring

router = APIRouter(prefix="/cameras", tags=["monitoring"])

# Stable error codes the frontend can branch on.
CAMERA_NOT_FOUND = "camera_not_found"
NO_MONITORING_DATA = "no_monitoring_data"
NO_PREDICTION = "no_prediction"
NO_LIVE_DATA = "no_live_data"
NO_STREAM = "no_stream"

STREAM_BOUNDARY = "crowdcastframe"

NOT_FOUND_DOC = {404: {"description": "camera_not_found or no data yet"}}


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


@router.get(
    "/{camera_id}/live",
    response_model=LiveStateOut,
    responses=NOT_FOUND_DOC,
)
async def get_live(camera: CameraDep, hub: LiveHubDep) -> LiveStateOut:
    state = hub.get_live(camera.code)
    if state is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=NO_LIVE_DATA)
    age = (datetime.now(timezone.utc) - state.received_at).total_seconds()
    return LiveStateOut(
        camera_id=camera.code,
        timestamp=state.timestamp,
        people_count=state.raw_count,
        smoothed_count=state.smoothed_count,
        crowd_status=state.crowd_status,
        is_stale=age > get_settings().LIVE_STALE_SECONDS,
    )


@router.get(
    "/{camera_id}/stream",
    response_class=StreamingResponse,
    responses={200: {"content": {"multipart/x-mixed-replace": {}}}, **NOT_FOUND_DOC},
)
async def get_stream(camera: CameraDep, hub: LiveHubDep) -> StreamingResponse:
    """MJPEG stream of the annotated video, usable directly as an <img> source."""
    if not hub.has_frame(camera.code):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=NO_STREAM)

    async def parts() -> AsyncIterator[bytes]:
        async for jpeg in hub.frames(camera.code):
            yield (
                b"--" + STREAM_BOUNDARY.encode() + b"\r\n"
                b"Content-Type: image/jpeg\r\n"
                b"Content-Length: " + str(len(jpeg)).encode() + b"\r\n\r\n" + jpeg + b"\r\n"
            )

    return StreamingResponse(
        parts(),
        media_type=f"multipart/x-mixed-replace; boundary={STREAM_BOUNDARY}",
        headers={"Cache-Control": "no-store"},
    )


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
