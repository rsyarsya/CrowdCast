"""Write API for the vision worker. Every route requires the X-Worker-Key header."""

import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy import and_, delete, or_, select
from sqlalchemy.dialects.postgresql import insert

from app.api.deps import DbSession, LiveHubDep
from app.api.v1.cameras import CameraDep
from app.core.config import get_settings
from app.models import CrowdRecord, Prediction
from app.services.alerts import Observation, track_forecasts, track_records
from app.schemas.ingest import (
    LiveAccepted,
    LiveIn,
    PredictionsIn,
    RecordIn,
    RecordsAccepted,
    RecordsIn,
    WorkerCameraConfig,
)

MAX_FRAME_BYTES = 2 * 1024 * 1024


def require_worker_key(
    x_worker_key: Annotated[str | None, Header()] = None,
) -> None:
    configured = get_settings().WORKER_API_KEY
    if configured is None or not configured.get_secret_value():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="ingest_disabled")
    if x_worker_key is None or not secrets.compare_digest(
        x_worker_key.encode(), configured.get_secret_value().encode()
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="invalid_worker_key")


router = APIRouter(
    prefix="/ingest/cameras/{camera_id}",
    tags=["ingest"],
    dependencies=[Depends(require_worker_key)],
)


@router.get("/config", response_model=WorkerCameraConfig)
async def get_worker_config(camera: CameraDep) -> WorkerCameraConfig:
    return WorkerCameraConfig.from_model(camera)


@router.post("/records", response_model=RecordsAccepted)
async def post_records(db: DbSession, camera: CameraDep, body: RecordsIn) -> RecordsAccepted:
    """Store per-interval records. Re-sending the same timestamp overwrites it,
    so the worker can safely retry after a network error."""
    rows = [
        {
            "camera_id": camera.id,
            "timestamp": r.timestamp,
            "people_count": r.people_count,
            "crowd_status": r.crowd_status,
        }
        for r in body.records
    ]
    statement = insert(CrowdRecord).values(rows)
    statement = statement.on_conflict_do_update(
        index_elements=["camera_id", "timestamp"],
        set_={
            "people_count": statement.excluded.people_count,
            "crowd_status": statement.excluded.crowd_status,
        },
    )
    await db.execute(statement)
    await track_records(
        db,
        camera,
        (Observation(r.timestamp, r.people_count, r.crowd_status) for r in body.records),
    )
    await db.commit()
    return RecordsAccepted(received=len(rows))


@router.get("/records/recent", response_model=list[RecordIn])
async def get_recent_records(
    db: DbSession, camera: CameraDep, limit: Annotated[int, Query(ge=1, le=1440)] = 180
) -> list[RecordIn]:
    """Latest records in ascending time order, so a restarted worker can resume
    forecasting without waiting for a fresh history."""
    rows = (
        await db.scalars(
            select(CrowdRecord)
            .where(CrowdRecord.camera_id == camera.id)
            .order_by(CrowdRecord.timestamp.desc())
            .limit(limit)
        )
    ).all()
    return [
        RecordIn(timestamp=r.timestamp, people_count=r.people_count, crowd_status=r.crowd_status)
        for r in reversed(rows)
    ]


@router.post("/predictions", response_model=RecordsAccepted)
async def post_predictions(db: DbSession, camera: CameraDep, body: PredictionsIn) -> RecordsAccepted:
    """Store forecasts. A forecast with the same (timestamp, horizon) replaces the
    earlier one, so retries do not create duplicates."""
    keys = [and_(Prediction.timestamp == p.timestamp, Prediction.horizon_minutes == p.horizon_minutes)
            for p in body.predictions]
    await db.execute(delete(Prediction).where(Prediction.camera_id == camera.id, or_(*keys)))
    db.add_all(
        Prediction(
            camera_id=camera.id,
            timestamp=p.timestamp,
            horizon_minutes=p.horizon_minutes,
            predicted_count=p.predicted_count,
            predicted_status=p.predicted_status,
            model_name=p.model_name,
            is_simulation=False,
        )
        for p in body.predictions
    )
    await track_forecasts(
        db,
        camera,
        (
            (p.horizon_minutes, Observation(p.timestamp, p.predicted_count, p.predicted_status))
            for p in body.predictions
        ),
    )
    await db.commit()
    return RecordsAccepted(received=len(body.predictions))


@router.put("/live", response_model=LiveAccepted)
async def put_live(camera: CameraDep, hub: LiveHubDep, body: LiveIn) -> LiveAccepted:
    state = hub.set_live(
        camera.code, body.timestamp, body.raw_count, body.smoothed_count, body.crowd_status
    )
    return LiveAccepted(received_at=state.received_at)


@router.put("/frame", status_code=status.HTTP_204_NO_CONTENT)
async def put_frame(request: Request, camera: CameraDep, hub: LiveHubDep) -> None:
    if request.headers.get("content-type") != "image/jpeg":
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="expected_image_jpeg")
    jpeg = await request.body()
    if not jpeg or len(jpeg) > MAX_FRAME_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, detail="invalid_frame_size")
    await hub.publish_frame(camera.code, jpeg)
