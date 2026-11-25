"""Stable counting with ROI, rolling median smoothing, and 1-minute records.

Run from the backend folder:
    .\\.venv\\Scripts\\python.exe experiments\\phase2_counting.py mall
    .\\.venv\\Scripts\\python.exe experiments\\phase2_counting.py video --camera kabukicho --start-minute 360 --minutes 30

`mall`  : uses the per-frame counts from phase1_detect.py and measures whether rolling
          median smoothing changes the error against the ground truth.
`video` : detects people at a fixed rate (default 2 fps) on a segment of the
          long video, runs app.services.vision.CountingPipeline, and writes
          per-sample and per-minute CSVs plus a plot.
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BACKEND_DIR / "experiments"))

from app.services.vision.classifier import HysteresisClassifier, StatusThresholds  # noqa: E402
from app.services.vision.clock import frame_timestamp  # noqa: E402
from app.services.vision.pipeline import CountingPipeline  # noqa: E402
from app.services.vision.roi import Roi  # noqa: E402
from app.services.vision.smoothing import RollingMedian  # noqa: E402
from app.services.vision.types import Box  # noqa: E402

PHASE1_DIR = BACKEND_DIR / "experiments" / "outputs" / "phase1"
OUT_DIR = BACKEND_DIR / "experiments" / "outputs" / "phase2"
ROI_DIR = BACKEND_DIR / "experiments" / "configs" / "roi"
# Start of the Kabukicho recording, read from the clock burned into the video.
KABUKICHO_START = "2026-08-25T18:00:00+09:00"


def run_mall(args: argparse.Namespace) -> None:
    csv = PHASE1_DIR / f"mall_{args.config}.csv"
    if not csv.exists():
        raise SystemExit(f"{csv} not found. Run phase1_detect.py mall for that config first.")
    df = pd.read_csv(csv)
    rows = [{"window_s": 0, "mae": (df["pred"] - df["gt"]).abs().mean(), "bias": (df["pred"] - df["gt"]).mean()}]
    for window in args.windows:
        smoother = RollingMedian(window)
        smoothed = np.array([smoother.update(i * args.frame_interval, c) for i, c in enumerate(df["pred"])])
        err = smoothed - df["gt"].to_numpy()
        rows.append({"window_s": window, "mae": np.abs(err).mean(), "bias": err.mean()})
    result = pd.DataFrame(rows)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUT_DIR / f"mall_smoothing_{args.config}.csv", index=False, float_format="%.3f")
    print(f"Config: {args.config} (frame interval assumed {args.frame_interval}s; window 0 = no smoothing)")
    print(result.to_string(index=False, float_format=lambda v: f"{v:.2f}"))


def detect_samples(args: argparse.Namespace) -> tuple[list[tuple[int, list[Box]]], float, int, int]:
    """Run the detector at `args.rate` samples per second. Returns (frame_index, boxes) pairs."""
    import cv2
    from phase1_detect import load_model, run_detector

    cap = cv2.VideoCapture(str(args.video))
    if not cap.isOpened():
        raise SystemExit(f"Cannot open {args.video}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    step = max(1, round(fps / args.rate))
    first = int(args.start_minute * 60 * fps)
    last = first + int(args.minutes * 60 * fps)
    cap.set(cv2.CAP_PROP_POS_FRAMES, first)
    model = load_model(args.model)

    samples, index, start = [], first, time.perf_counter()
    while index < last:
        ok, frame = cap.read()
        if not ok:
            break
        dets = run_detector(model, frame, args.imgsz, args.conf, args.tiles, args)
        samples.append((index, [Box(*map(float, d)) for d in dets]))
        if len(samples) % 600 == 0:
            done = (index - first) / (last - first)
            print(f"   {len(samples)} samples ({done:.0%}), {len(samples) / (time.perf_counter() - start):.1f} samples/s")
        for _ in range(step - 1):  # skip frames without decoding them fully
            if not cap.grab():
                break
        index += step
    cap.release()
    return samples, fps, w, h


def tertile_thresholds(values: pd.Series) -> StatusThresholds:
    """Provisional thresholds: lower/upper third of the per-minute counts (PROPOSED, final values are decided separately)."""
    low, high = np.percentile(values, [33.3, 66.7])
    normal_from = max(1.0, round(low))
    ramai_from = max(normal_from + 2, round(high))
    margin = max(0.0, min(round(0.1 * ramai_from), normal_from - 1, ramai_from - normal_from - 1))
    return StatusThresholds(normal_from, ramai_from, margin)


def run_pipeline(samples, fps, w, h, roi, thresholds, args):
    video_start = datetime.fromisoformat(args.video_start)
    pipeline = CountingPipeline(thresholds, roi=roi, smoothing_window_s=args.window, interval_s=args.interval)
    live_rows, records = [], []
    for index, boxes in samples:
        ts = frame_timestamp(index, fps, "dataset", video_start=video_start)
        live, record = pipeline.process(ts, boxes, w, h)
        live_rows.append(
            {"timestamp": ts, "raw": live.raw_count, "smoothed": live.smoothed_count, "status": live.crowd_status}
        )
        if record:
            records.append(record)
    if (record := pipeline.flush()) is not None:
        records.append(record)
    minutes = pd.DataFrame(
        [{"timestamp": r.start, "people_count": r.people_count, "n_samples": r.n_samples} for r in records]
    )
    return pd.DataFrame(live_rows), minutes


def plot(live: pd.DataFrame, minutes: pd.DataFrame, th: StatusThresholds, path: Path, title: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(12, 5))
    top = max(live.raw.max(), th.ramai_from) * 1.15
    ax.axhspan(0, th.normal_from, color="#9ad1d4", alpha=0.25, label="Sepi")
    ax.axhspan(th.normal_from, th.ramai_from, color="#b39ddb", alpha=0.25, label="Normal")
    ax.axhspan(th.ramai_from, top, color="#f48fb1", alpha=0.25, label="Ramai")
    ax.plot(live.timestamp, live.raw, color="0.6", lw=0.6, label="raw (2 fps)")
    ax.plot(live.timestamp, live.smoothed, color="#1f4e79", lw=1.2, label="rolling median")
    ax.step(minutes.timestamp, minutes.people_count, where="post", color="#c62828", lw=2, label="record / menit")
    ax.set_ylim(0, top)
    ax.set_ylabel("jumlah orang")
    ax.set_title(title)
    ax.legend(loc="upper left", ncol=3, fontsize=8)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def run_video(args: argparse.Namespace) -> None:
    roi_path = ROI_DIR / f"{args.camera}.json"
    roi = Roi.from_json(roi_path.read_text()) if roi_path.exists() else None
    print(f"ROI: {roi_path if roi else 'none (whole frame)'}")
    samples, fps, w, h = detect_samples(args)
    print(f"{len(samples)} samples from {args.minutes} min of video")

    # Pass 1 only to find provisional thresholds; the pipeline is cheap, detection is not.
    th = StatusThresholds(*args.thresholds) if args.thresholds else None
    if th is None:
        _, minutes = run_pipeline(samples, fps, w, h, roi, StatusThresholds(1, 2), args)
        th = tertile_thresholds(minutes.people_count)
    live, minutes = run_pipeline(samples, fps, w, h, roi, th, args)
    clf = HysteresisClassifier(th)
    minutes["crowd_status"] = [clf.update(c) for c in minutes.people_count]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tag = f"{args.camera}_m{args.start_minute:g}-{args.start_minute + args.minutes:g}"
    live.to_csv(OUT_DIR / f"{tag}_samples.csv", index=False)
    minutes.to_csv(OUT_DIR / f"{tag}_minutes.csv", index=False)
    title = (
        f"{args.camera}: {args.model} imgsz={args.imgsz} tiles={args.tiles} conf={args.conf}, "
        f"median {args.window}s, threshold PROPOSED {th.normal_from:g}/{th.ramai_from:g} margin {th.margin:g}"
    )
    plot(live, minutes, th, OUT_DIR / f"{tag}.png", title)

    changes = int((live.status != live.status.shift()).sum() - 1)
    raw_changes = int((live.raw.diff() != 0).sum())
    print(f"Thresholds (PROPOSED): normal_from={th.normal_from:g} ramai_from={th.ramai_from:g} margin={th.margin:g}")
    print(f"Raw count changed {raw_changes} times; live status changed {changes} times")
    print(minutes.to_string(index=False))
    print(f"Saved CSVs and plot to {OUT_DIR}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    mall = sub.add_parser("mall")
    mall.add_argument("--config", default="yolo11n_960_tiles2x2_conf0.15", help="Config tag from phase1_detect.py")
    mall.add_argument("--windows", nargs="+", type=float, default=[1, 2, 3, 5])
    mall.add_argument("--frame-interval", type=float, default=0.5, help="Seconds between Mall frames (assumed)")

    video = sub.add_parser("video")
    video.add_argument("--camera", default="kabukicho")
    video.add_argument("--video", type=Path, default=next((BACKEND_DIR / "data" / "videos").glob("*.mp4"), None))
    video.add_argument("--video-start", default=KABUKICHO_START, help="ISO time of the first frame, with timezone")
    video.add_argument("--start-minute", type=float, default=360)
    video.add_argument("--minutes", type=float, default=30)
    video.add_argument("--rate", type=float, default=2, help="Detection samples per second")
    video.add_argument("--model", default="yolo11n.pt")
    video.add_argument("--imgsz", type=int, default=960)
    video.add_argument("--tiles", default="2x2")
    video.add_argument("--conf", type=float, default=0.15)
    video.add_argument("--overlap", type=float, default=0.2)
    video.add_argument("--full-imgsz", type=int, default=960)
    video.add_argument("--window", type=float, default=5, help="Rolling median window in seconds")
    video.add_argument("--interval", type=int, default=60, help="Record interval in seconds")
    video.add_argument("--thresholds", nargs=3, type=float, metavar=("NORMAL_FROM", "RAMAI_FROM", "MARGIN"))

    args = parser.parse_args()
    run_mall(args) if args.cmd == "mall" else run_video(args)


if __name__ == "__main__":
    main()
