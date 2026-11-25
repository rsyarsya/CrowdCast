"""Seed the database with the demo camera, simulated history, and an admin.

Run from the backend folder after `alembic upgrade head`:
    .\\.venv\\Scripts\\python.exe -m app.scripts.seed

Safe to run repeatedly: existing rows are left untouched.
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import BACKEND_DIR, Settings, get_settings
from app.core.security import get_password_hash
from app.db.session import create_engine, create_sessionmaker
from app.models import Camera, CrowdRecord, CrowdStatus, User, UserRole

logger = logging.getLogger(__name__)

SIMULATION_FILE = BACKEND_DIR.parent / "docs" / "data" / "monitoring-simulation.json"

# Placeholder thresholds consistent with the simulation data (0 Sepi, 18 Normal,
# 37 Ramai). Final values follow the threshold decision in the AI phase.
DEMO_CAMERA = {
    "code": "CAM-01",
    "name": "Kamera Lobi",
    "location": "Lobi Gedung A",
    "threshold_normal": 10,
    "threshold_ramai": 30,
}


@dataclass
class SeedResult:
    cameras: int
    crowd_records: int
    admin_created: bool


async def seed_demo_camera(session: AsyncSession, settings: Settings) -> Camera:
    stmt = (
        insert(Camera)
        .values(**DEMO_CAMERA, source=settings.VIDEO_SAMPLE_PATH, is_active=True)
        .on_conflict_do_nothing(index_elements=[Camera.code])
    )
    await session.execute(stmt)
    return (
        await session.execute(select(Camera).where(Camera.code == DEMO_CAMERA["code"]))
    ).scalar_one()


async def seed_simulation_records(
    session: AsyncSession, cameras_by_code: dict[str, Camera], path: Path
) -> int:
    rows = json.loads(path.read_text(encoding="utf-8"))
    values = [
        {
            "camera_id": cameras_by_code[row["camera_id"]].id,
            "timestamp": datetime.fromisoformat(row["timestamp"]),
            "people_count": row["people_count"],
            "crowd_status": CrowdStatus(row["crowd_status"]),
        }
        for row in rows
    ]
    stmt = (
        insert(CrowdRecord)
        .values(values)
        .on_conflict_do_nothing(index_elements=["camera_id", "timestamp"])
    )
    result = await session.execute(stmt)
    return result.rowcount or 0


async def seed_admin(session: AsyncSession, settings: Settings) -> bool:
    email = settings.FIRST_SUPERUSER_EMAIL
    password = settings.FIRST_SUPERUSER_PASSWORD
    if not email or not password:
        logger.warning("FIRST_SUPERUSER_EMAIL/PASSWORD not set; skipping admin.")
        return False
    if await session.scalar(select(User.id).where(User.email == email)):
        return False
    session.add(
        User(
            email=email,
            name="Administrator",
            hashed_password=get_password_hash(password.get_secret_value()),
            role=UserRole.ADMIN,
        )
    )
    return True


async def seed(
    session: AsyncSession, settings: Settings, simulation_file: Path = SIMULATION_FILE
) -> SeedResult:
    camera = await seed_demo_camera(session, settings)
    inserted = await seed_simulation_records(
        session, {camera.code: camera}, simulation_file
    )
    admin_created = await seed_admin(session, settings)
    await session.commit()
    logger.info("Inserted %d crowd records; admin created: %s", inserted, admin_created)
    return SeedResult(
        cameras=await session.scalar(select(func.count()).select_from(Camera)) or 0,
        crowd_records=await session.scalar(
            select(func.count()).select_from(CrowdRecord)
        )
        or 0,
        admin_created=admin_created,
    )


async def main() -> None:
    settings = get_settings()
    engine = create_engine(settings)
    try:
        async with create_sessionmaker(engine)() as session:
            result = await seed(session, settings)
    finally:
        await engine.dispose()
    print(
        f"Seed done: {result.cameras} camera(s), {result.crowd_records} crowd "
        f"record(s), admin created: {result.admin_created}"
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
