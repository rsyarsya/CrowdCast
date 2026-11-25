"""Write API for the vision worker. Every route requires the X-Worker-Key header."""

import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.dialects.postgresql import insert

from app.api.deps import DbSession, LiveHubDep
from app.api.v1.cameras import CameraDep
from app.core.config import get_settings
from app.models import CrowdRecord
from app.schemas.ingest import (
    LiveAccepted,
    LiveIn,
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
    await db.commit()
    return RecordsAccepted(received=len(rows))


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
