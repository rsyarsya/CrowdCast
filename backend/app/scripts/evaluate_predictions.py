"""Report how accurate a camera's stored forecasts were against the observed counts.

Run from the backend folder:
    .\\.venv\\Scripts\\python.exe -m app.scripts.evaluate_predictions --camera CAM-02 --hours 24

Each prediction is compared with the record at its target time (made time plus
horizon). Predictions whose target time has not been recorded yet are skipped.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import create_engine, create_sessionmaker
from app.models import Camera
from app.services.prediction_accuracy import HorizonAccuracy, prediction_accuracy


def format_report(results: list[HorizonAccuracy]) -> str:
    if not results:
        return "No predictions with an observed target time in this window."
    lines = [f"{'horizon':>8} {'samples':>8} {'MAE':>7} {'RMSE':>7} {'bias':>7} {'status':>7}  models"]
    for r in results:
        s = r.score
        lines.append(
            f"{r.horizon_minutes:>6} m {s.samples:>8} {s.mae:>7.2f} {s.rmse:>7.2f} "
            f"{s.bias:>+7.2f} {s.status_accuracy:>7.1%}  {', '.join(r.model_names)}"
        )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--camera", required=True, help="Public camera id, e.g. CAM-02")
    parser.add_argument("--hours", type=float, default=24, help="Window length ending at --end")
    parser.add_argument("--end", type=datetime.fromisoformat, help="ISO time with offset (default: now)")
    parser.add_argument("--include-simulation", action="store_true", help="Also score simulated predictions")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    end = args.end or datetime.now(timezone.utc)
    if end.tzinfo is None:
        raise SystemExit("--end must include a timezone offset")
    start = end - timedelta(hours=args.hours)
    engine = create_engine(get_settings())
    try:
        async with create_sessionmaker(engine)() as session:
            camera = await session.scalar(select(Camera).where(Camera.code == args.camera))
            if camera is None:
                raise SystemExit(f"Camera {args.camera} does not exist")
            results = await prediction_accuracy(session, camera, start, end, args.include_simulation)
    finally:
        await engine.dispose()
    print(f"{args.camera}, target times {start.isoformat()} to {end.isoformat()}")
    print(format_report(results))


if __name__ == "__main__":
    asyncio.run(main())
