"""Run the vision worker for one camera.

From the backend folder, with the API running and the AI dependencies installed:
    .\\.venv\\Scripts\\python.exe -m app.worker --camera CAM-02 --start-minute 300

The worker reads WORKER_API_KEY (and optionally WORKER_API_URL) from the
environment or backend/.env. It asks the API for the camera's video source,
ROI, and thresholds, so it never needs database credentials.
"""

from __future__ import annotations

import argparse
import logging
import signal
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.services.vision.classifier import StatusThresholds
from app.services.vision.pipeline import CountingPipeline
from app.services.vision.roi import Roi

BACKEND_DIR = Path(__file__).resolve().parents[2]
logger = logging.getLogger("app.worker")


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env", env_file_encoding="utf-8", case_sensitive=True, extra="ignore"
    )

    WORKER_API_KEY: SecretStr
    WORKER_API_URL: str = "http://localhost:8000"
    TIMEZONE: str = "Asia/Jakarta"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--camera", required=True, help="Public camera code, e.g. CAM-02")
    parser.add_argument("--api", help="API origin (default: WORKER_API_URL or http://localhost:8000)")
    parser.add_argument("--source", type=Path, help="Override the camera's video source")
    parser.add_argument("--start-minute", type=float, default=300, help="Video position to start from")
    parser.add_argument("--no-loop", action="store_true", help="Stop at the end of the video")
    parser.add_argument("--weights", default="yolo11n.pt")
    parser.add_argument("--imgsz", type=int, default=960)
    parser.add_argument("--conf", type=float, default=0.15)
    parser.add_argument("--tiles", default="2x2", help="'none' or ROWSxCOLS")
    parser.add_argument("--detect-fps", type=float, default=2.0)
    parser.add_argument("--stream-fps", type=float, default=10.0)
    parser.add_argument("--smoothing-window", type=float, default=5.0, help="Rolling median window (s)")
    parser.add_argument("--interval", type=int, default=60, help="Record interval (s)")
    parser.add_argument("--dwell", type=float, default=30.0, help="Live status dwell time (s)")
    parser.add_argument(
        "--forecast-model",
        type=Path,
        help="Model from experiments/phase5_forecast.py (default: data/models/forecast/<camera>.pt|.json)",
    )
    parser.add_argument("--no-forecast", action="store_true", help="Do not send predictions")
    return parser.parse_args()


def resolve_source(source: str) -> Path:
    path = Path(source)
    return path if path.is_absolute() else BACKEND_DIR / path


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    # httpx logs every request at INFO; the worker sends about 12 per second.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    args = parse_args()
    settings = WorkerSettings()

    # Heavy imports after argument parsing so --help stays fast.
    from app.services.vision.detector import YoloDetector
    from app.worker.client import IngestClient
    from app.worker.overlay import make_encoder
    from app.worker.runner import VisionWorker
    from app.worker.source import VideoReplaySource

    client = IngestClient(args.api or settings.WORKER_API_URL, args.camera, settings.WORKER_API_KEY.get_secret_value())
    config = client.get_config()
    roi = Roi.from_points(config["roi"]) if config["roi"] else None
    thresholds = StatusThresholds(config["threshold_normal"], config["threshold_ramai"])
    source_path = args.source or resolve_source(config["source"])
    logger.info(
        "Camera %s: source=%s, thresholds=%s/%s, roi=%s",
        args.camera, source_path, thresholds.normal_from, thresholds.ramai_from, "yes" if roi else "whole frame",
    )

    logger.info("Loading %s (imgsz %d, tiles %s, conf %.2f)", args.weights, args.imgsz, args.tiles, args.conf)
    detector = YoloDetector(args.weights, imgsz=args.imgsz, conf=args.conf, tiles=args.tiles)
    source = VideoReplaySource(source_path, start_minute=args.start_minute, loop=not args.no_loop)
    pipeline = CountingPipeline(
        thresholds,
        roi=roi,
        smoothing_window_s=args.smoothing_window,
        interval_s=args.interval,
        status_dwell_s=args.dwell,
    )
    forecast = None
    if not args.no_forecast:
        from datetime import timedelta

        from app.services.forecast.loader import find_model_file, load_forecaster
        from app.worker.forecasting import ForecastRunner

        model_path = args.forecast_model or find_model_file(BACKEND_DIR / "data" / "models" / "forecast", args.camera)
        forecaster = load_forecaster(model_path)
        forecast = ForecastRunner(forecaster, thresholds, interval=timedelta(seconds=args.interval))
        forecast.seed(client.get_recent_records())
        logger.info(
            "Forecasting with %s (%d minutes of history loaded, %d needed)",
            forecaster.name, forecast.history_length, forecaster.min_history,
        )

    worker = VisionWorker(
        detector=detector,
        encoder=make_encoder(roi, timezone=settings.TIMEZONE),
        sender=client,
        pipeline=pipeline,
        thresholds=thresholds,
        detect_interval_s=1 / args.detect_fps,
        stream_interval_s=1 / args.stream_fps,
        forecast=forecast,
    )
    signal.signal(signal.SIGINT, lambda *_: worker.stop())
    logger.info("Streaming at %.0f fps, detecting at %.1f fps. Press Ctrl+C to stop.", args.stream_fps, args.detect_fps)
    try:
        worker.run(iter(source))
    finally:
        source.close()
        client.close()
        logger.info("Stopped. Sent %d records.", worker.stats.records_sent)


if __name__ == "__main__":
    main()
