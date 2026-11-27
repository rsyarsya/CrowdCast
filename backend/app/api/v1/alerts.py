from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.api.deps import CurrentUser, DbSession, get_current_user
from app.api.v1.cameras import CAMERA_NOT_FOUND, require_aware
from app.schemas.alerts import AlertOut
from app.services import alerts, monitoring

router = APIRouter(prefix="/alerts", tags=["alerts"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[AlertOut])
async def list_alerts(
    db: DbSession,
    camera_id: Annotated[str | None, Query(description="Public camera code")] = None,
    active: Annotated[bool | None, Query(description="true: open only, false: ended only")] = None,
    start: Annotated[datetime | None, Query(description="started_at lower bound, with offset")] = None,
    end: Annotated[datetime | None, Query(description="started_at upper bound, with offset")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[AlertOut]:
    """Newest alerts first."""
    require_aware(start, "start")
    require_aware(end, "end")
    camera = None
    if camera_id is not None:
        camera = await monitoring.get_camera_by_code(db, camera_id)
        if camera is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=CAMERA_NOT_FOUND)
    rows = await alerts.list_alerts(db, camera, active, start, end, limit)
    return [AlertOut.from_model(alert) for alert in rows]


@router.post(
    "/{alert_id}/ack",
    response_model=AlertOut,
    responses={404: {"description": "alert_not_found"}},
)
async def acknowledge_alert(
    db: DbSession, user: CurrentUser, alert_id: Annotated[int, Path()]
) -> AlertOut:
    alert = await alerts.get_alert(db, alert_id)
    if alert is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="alert_not_found")
    return AlertOut.from_model(await alerts.acknowledge(db, alert, user))
