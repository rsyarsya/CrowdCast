"""Delete predictions older than the retention period.

Crowd records and alerts are kept. Run from the backend folder, for example
daily from cron or a scheduled job:
    .\.venv\Scripts\python.exe -m app.scripts.prune --days 30
"""

import argparse
import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import create_engine, create_sessionmaker
from app.models import Prediction


async def prune_predictions(session: AsyncSession, older_than: datetime) -> int:
    result = await session.execute(delete(Prediction).where(Prediction.timestamp < older_than))
    await session.commit()
    return result.rowcount


async def main(days: int) -> None:
    engine = create_engine(get_settings())
    try:
        async with create_sessionmaker(engine)() as session:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            deleted = await prune_predictions(session, cutoff)
    finally:
        await engine.dispose()
    print(f"Deleted {deleted} prediction(s) made before {cutoff.isoformat()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=30, help="Keep predictions this many days")
    args = parser.parse_args()
    if args.days < 1:
        parser.error("--days must be at least 1")
    asyncio.run(main(args.days))
