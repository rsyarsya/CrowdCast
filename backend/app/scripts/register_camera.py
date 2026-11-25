"""Create or update a camera and its counting configuration.

Run from the backend folder after `alembic upgrade head`, for example:
    .\\.venv\\Scripts\\python.exe -m app.scripts.register_camera --code CAM-02 \\
        --name "Kabukicho" --location "Kabukicho, Shinjuku" \\
        --source data/videos/kabukicho_night_2026-08-25_720p.mp4 \\
        --roi experiments/configs/roi/kabukicho.json --normal 4 --ramai 12

Running it again with the same code updates the existing camera.
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import BACKEND_DIR, get_settings
from app.db.session import create_engine, create_sessionmaker
from app.models import Camera
from app.services.vision.classifier import StatusThresholds
from app.services.vision.roi import Roi


@dataclass(frozen=True)
class CameraSpec:
    code: str
    name: str
    location: str
    source: str
    threshold_normal: int
    threshold_ramai: int
    roi: Roi | None = None

    def __post_init__(self) -> None:
        # Same rules the classifier enforces at runtime.
        StatusThresholds(self.threshold_normal, self.threshold_ramai)


async def register_camera(session: AsyncSession, spec: CameraSpec) -> Camera:
    values = {
        "code": spec.code,
        "name": spec.name,
        "location": spec.location,
        "source": spec.source,
        "threshold_normal": spec.threshold_normal,
        "threshold_ramai": spec.threshold_ramai,
        "roi": [list(point) for point in spec.roi.points] if spec.roi else None,
        "is_active": True,
    }
    stmt = insert(Camera).values(values)
    stmt = stmt.on_conflict_do_update(
        index_elements=[Camera.code],
        set_={key: stmt.excluded[key] for key in values if key != "code"},
    )
    await session.execute(stmt)
    await session.commit()
    camera = await session.scalar(
        select(Camera).where(Camera.code == spec.code).execution_options(populate_existing=True)
    )
    assert camera is not None
    return camera


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--code", required=True, help="Public camera id, e.g. CAM-02")
    parser.add_argument("--name", required=True)
    parser.add_argument("--location", required=True)
    parser.add_argument("--source", required=True, help="Video path relative to backend/, or an RTSP URL")
    parser.add_argument("--roi", type=Path, help="ROI JSON from experiments/roi_tool.py (default: whole frame)")
    parser.add_argument("--normal", type=int, required=True, help="Lowest count shown as Normal")
    parser.add_argument("--ramai", type=int, required=True, help="Lowest count shown as Ramai")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    roi_path = args.roi if args.roi is None or args.roi.is_absolute() else BACKEND_DIR / args.roi
    spec = CameraSpec(
        code=args.code,
        name=args.name,
        location=args.location,
        source=args.source,
        threshold_normal=args.normal,
        threshold_ramai=args.ramai,
        roi=Roi.from_json(roi_path.read_text(encoding="utf-8")) if roi_path else None,
    )
    engine = create_engine(get_settings())
    try:
        async with create_sessionmaker(engine)() as session:
            camera = await register_camera(session, spec)
    finally:
        await engine.dispose()
    roi_text = f"{len(camera.roi)}-point ROI" if camera.roi else "whole frame"
    print(
        f"Camera {camera.code} saved: {camera.location}, thresholds "
        f"{camera.threshold_normal}/{camera.threshold_ramai}, {roi_text}"
    )


if __name__ == "__main__":
    asyncio.run(main())
