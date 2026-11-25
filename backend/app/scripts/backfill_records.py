"""Fill a camera's history with per-minute records from a processed recording.

The CSV comes from `experiments/phase3_dataset.py build` (columns timestamp and
people_count, one row per minute). Timestamps are shifted so the last row lands
on the minute before `--end` (default: now). The counts are real detections on
the recording; only the time axis is moved, so the history and forecasting
features have data right away while the live worker starts from "now".

Run from the backend folder:
    .\\.venv\\Scripts\\python.exe -m app.scripts.backfill_records --camera CAM-02 \\
        --csv experiments/outputs/phase3/kabukicho_minutes.csv

Existing rows at the same (camera, timestamp) are kept, so running it twice does
not create duplicates.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import BACKEND_DIR, get_settings
from app.db.session import create_engine, create_sessionmaker
from app.models import Camera, CrowdRecord, CrowdStatus
from app.services.vision.classifier import StatusThresholds, classify

BATCH_SIZE = 1000


@dataclass(frozen=True)
class MinuteRow:
    timestamp: datetime
    people_count: int


def read_minutes(path: Path) -> list[MinuteRow]:
    with path.open(encoding="utf-8", newline="") as f:
        rows = [
            MinuteRow(datetime.fromisoformat(row["timestamp"]), int(row["people_count"]))
            for row in csv.DictReader(f)
        ]
    if not rows:
        raise ValueError(f"{path} has no rows")
    if any(row.timestamp.tzinfo is None for row in rows):
        raise ValueError("CSV timestamps must include a timezone offset")
    return sorted(rows, key=lambda row: row.timestamp)


def shift_to_end(rows: list[MinuteRow], end: datetime) -> list[MinuteRow]:
    """Move all rows by the same offset so the last one is the minute before `end`."""
    last_slot = end.astimezone(timezone.utc).replace(second=0, microsecond=0) - timedelta(minutes=1)
    offset = last_slot - rows[-1].timestamp
    return [MinuteRow(row.timestamp + offset, row.people_count) for row in rows]


async def backfill(
    session: AsyncSession, camera_code: str, rows: list[MinuteRow], replace: bool = False
) -> int:
    """Insert the rows. With `replace`, all existing records of the camera are
    deleted first, in the same transaction (used after changing the ROI)."""
    camera = await session.scalar(select(Camera).where(Camera.code == camera_code))
    if camera is None:
        raise LookupError(f"Camera {camera_code} does not exist. Register it first.")
    thresholds = StatusThresholds(camera.threshold_normal, camera.threshold_ramai)
    if replace:
        await session.execute(delete(CrowdRecord).where(CrowdRecord.camera_id == camera.id))
    inserted = 0
    for start in range(0, len(rows), BATCH_SIZE):
        values = [
            {
                "camera_id": camera.id,
                "timestamp": row.timestamp,
                "people_count": row.people_count,
                "crowd_status": CrowdStatus(classify(row.people_count, thresholds)),
            }
            for row in rows[start : start + BATCH_SIZE]
        ]
        stmt = insert(CrowdRecord).values(values).on_conflict_do_nothing(
            index_elements=["camera_id", "timestamp"]
        )
        inserted += (await session.execute(stmt)).rowcount or 0
    await session.commit()
    return inserted


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--camera", required=True, help="Public camera id, e.g. CAM-02")
    parser.add_argument("--csv", type=Path, required=True, help="Per-minute CSV (relative to backend/)")
    parser.add_argument("--end", type=datetime.fromisoformat, help="ISO time the history should end at")
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Delete ALL existing records of the camera first (e.g. after changing its ROI)",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    path = args.csv if args.csv.is_absolute() else BACKEND_DIR / args.csv
    end = args.end or datetime.now(timezone.utc)
    if end.tzinfo is None:
        raise SystemExit("--end must include a timezone offset")
    rows = shift_to_end(read_minutes(path), end)
    engine = create_engine(get_settings())
    try:
        async with create_sessionmaker(engine)() as session:
            inserted = await backfill(session, args.camera, rows, replace=args.replace)
    finally:
        await engine.dispose()
    print(
        f"Inserted {inserted} of {len(rows)} records for {args.camera} "
        f"({rows[0].timestamp.isoformat()} to {rows[-1].timestamp.isoformat()})"
    )


if __name__ == "__main__":
    asyncio.run(main())
