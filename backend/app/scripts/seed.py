"""Seed the demo camera, simulated history and predictions, and an admin.

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
from app.models import Camera, CrowdRecord, CrowdStatus, Prediction, User, UserRole

logger = logging.getLogger(__name__)

SIMULATION_FILE = BACKEND_DIR.parent / "docs" / "data" / "monitoring-simulation.json"

# Placeholder thresholds consistent with the simulation data (0 Sepi, 18 Normal,
# 37 Ramai). Final values come from the per-camera threshold decision.
DEMO_CAMERA = {
    "code": "CAM-01",
    "name": "Kamera Lobi",
    "location": "Lobi Gedung A",
    "threshold_normal": 10,
    "threshold_ramai": 30,
}

# Simulated predictions (horizon minutes -> count, status) made at the time of
# the last simulated observation. The 15-minute value matches the frontend mock.
# Replaced once real forecasts are available.
SIMULATED_PREDICTIONS = {
    5: (40, CrowdStatus.RAMAI),
    15: (45, CrowdStatus.RAMAI),
    30: (28, CrowdStatus.NORMAL),
}
SIMULATION_MODEL_NAME = "simulation"


@dataclass
class SeedResult:
    cameras: int
    crowd_records: int
    predictions: int
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


async def seed_simulated_predictions(session: AsyncSession, camera: Camera) -> int:
    already_seeded = await session.scalar(
        select(Prediction.id).where(
            Prediction.camera_id == camera.id,
            Prediction.model_name == SIMULATION_MODEL_NAME,
        )
    )
    if already_seeded:
        return 0
    made_at = await session.scalar(
        select(func.max(CrowdRecord.timestamp)).where(
            CrowdRecord.camera_id == camera.id
        )
    )
    if made_at is None:
        return 0
    session.add_all(
        Prediction(
            camera_id=camera.id,
            timestamp=made_at,
            horizon_minutes=horizon,
            predicted_count=count,
            predicted_status=status,
            model_name=SIMULATION_MODEL_NAME,
            is_simulation=True,
        )
        for horizon, (count, status) in SIMULATED_PREDICTIONS.items()
    )
    return len(SIMULATED_PREDICTIONS)


async def seed_admin(session: AsyncSession, settings: Settings) -> bool:
    email = settings.FIRST_SUPERUSER_EMAIL
    password = settings.FIRST_SUPERUSER_PASSWORD
    if not email or not password:
        logger.warning("FIRST_SUPERUSER_EMAIL/PASSWORD not set; skipping admin.")
        return False
    email = email.lower()
    if await session.scalar(select(User.id).where(func.lower(User.email) == email)):
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
    predictions = await seed_simulated_predictions(session, camera)
    admin_created = await seed_admin(session, settings)
    await session.commit()
    logger.info(
        "Inserted %d crowd records and %d predictions; admin created: %s",
        inserted,
        predictions,
        admin_created,
    )

    async def count(model: type) -> int:
        return await session.scalar(select(func.count()).select_from(model)) or 0

    return SeedResult(
        cameras=await count(Camera),
        crowd_records=await count(CrowdRecord),
        predictions=await count(Prediction),
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
        f"record(s), {result.predictions} prediction(s), "
        f"admin created: {result.admin_created}"
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
