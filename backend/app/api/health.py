import asyncio
import logging

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text

from app.api.deps import DbSession

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])

READINESS_TIMEOUT_SECONDS = 3


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness: the process is running. Does not touch dependencies."""
    return {"status": "ok"}


@router.get(
    "/health/ready",
    responses={503: {"description": "The database is unavailable"}},
)
async def ready(db: DbSession) -> dict[str, str]:
    """Readiness: the app can serve requests because the database answers."""
    try:
        await asyncio.wait_for(
            db.execute(text("SELECT 1")), timeout=READINESS_TIMEOUT_SECONDS
        )
    except Exception as exc:  # any DB failure means "not ready", not a server bug
        logger.warning("Readiness check failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="database unavailable",
        ) from exc
    return {"status": "ready", "database": "ok"}
