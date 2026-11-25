"""Build the full-recording dataset and derive crowd status thresholds.

Run from the backend folder:
    .\\.venv\\Scripts\\python.exe experiments\\phase3_dataset.py extract --chunk 0
    .\\.venv\\Scripts\\python.exe experiments\\phase3_dataset.py build

`extract --chunk K` : detects people in one 30-minute chunk of the video and saves
                      the boxes to outputs/phase3/detections/chunk_KK.csv.gz.
                      Finished chunks are skipped, so a crash only loses one chunk.
                      Run every chunk (see `extract --list`) before `build`.
`build`             : runs CountingPipeline over all saved detections (no GPU),
                      writes the per-minute dataset for forecasting, derives
                      thresholds from percentiles, and compares status flicker
                      with and without margin and dwell time.
"""

from __future__ import annotations

import argparse
import gzip
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BACKEND_DIR / "experiments"))

from app.services.vision.classifier import (  # noqa: E402
    HysteresisClassifier,
    StatusThresholds,
    thresholds_from_percentiles,
)
from app.services.vision.clock import frame_timestamp  # noqa: E402
from app.services.vision.pipeline import CountingPipeline  # noqa: E402
from app.services.vision.roi import Roi  # noqa: E402
from app.services.vision.types import Box  # noqa: E402

OUT_DIR = BACKEND_DIR / "experiments" / "outputs" / "phase3"
DET_DIR = OUT_DIR / "detections"
ROI_DIR = BACKEND_DIR / "experiments" / "configs" / "roi"
VIDEO = next((BACKEND_DIR / "data" / "videos").glob("*.mp4"), None)
VIDEO_START = "2026-08-25T18:00:00+09:00"
CHUNK_MINUTES = 30


def video_info(path: Path) -> tuple[float, int, int, int]:
    import cv2

    cap = cv2.VideoCapture(str(path))
    info = (
        cap.get(cv2.CAP_PROP_FPS) or 30,
        int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
        int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
    )
    cap.release()
    return info


def extract(args: argparse.Namespace) -> None:
    import cv2
    from phase1_detect import load_model, run_detector

    fps, total, _, _ = video_info(args.video)
    chunk_frames = int(CHUNK_MINUTES * 60 * fps)
    n_chunks = -(-total // chunk_frames)
    if args.list:
        print(n_chunks)
        return
    out = DET_DIR / f"chunk_{args.chunk:02d}.csv.gz"
    if out.exists():
        print(f"chunk {args.chunk}: already done")
        return

    first, last = args.chunk * chunk_frames, min(total, (args.chunk + 1) * chunk_frames)
    step = max(1, round(fps / args.rate))
    cap = cv2.VideoCapture(str(args.video))
    cap.set(cv2.CAP_PROP_POS_FRAMES, first)
    model = load_model(args.model)
    rows, index, n, start = [], first, 0, time.perf_counter()
    while index < last:
        ok, frame = cap.read()
        if not ok:
            break
        dets = run_detector(model, frame, args.imgsz, args.conf, args.tiles, args)
        rows.append(f"{index},-1,-1,-1,-1,-1")  # marks a processed frame, also when empty
        rows.extend(f"{index},{d[0]:.1f},{d[1]:.1f},{d[2]:.1f},{d[3]:.1f},{d[4]:.3f}" for d in dets)
        n += 1
        for _ in range(step - 1):
            if not cap.grab():
                break
        index += step
    cap.release()

    DET_DIR.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8") as f:
        f.write("frame,x1,y1,x2,y2,score\n" + "\n".join(rows) + "\n")
    tmp.replace(out)  # only complete files get the final name
    print(f"chunk {args.chunk}: {n} samples in {time.perf_counter() - start:.0f}s")


def load_samples() -> list[tuple[int, list[Box]]]:
    files = sorted(DET_DIR.glob("chunk_*.csv.gz"))
    if not files:
        raise SystemExit("No detections yet. Run extract first.")
    df = pd.concat(pd.read_csv(f) for f in files).sort_values("frame", kind="stable")
    samples = []
    for frame, group in df.groupby("frame", sort=True):
        boxes = [Box(r.x1, r.y1, r.x2, r.y2, r.score) for r in group.itertuples() if r.score >= 0]
        samples.append((int(frame), boxes))
    return samples


def run(samples, fps, w, h, roi, th, dwell_s, window_s):
    start = datetime.fromisoformat(VIDEO_START)
    pipe = CountingPipeline(th, roi=roi, smoothing_window_s=window_s, interval_s=60, status_dwell_s=dwell_s)
    live, records = [], []
    for index, boxes in samples:
        ts = frame_timestamp(index, fps, "dataset", video_start=start)
        state, record = pipe.process(ts, boxes, w, h)
        live.append((ts, state.raw_count, state.smoothed_count, state.crowd_status))
        if record:
            records.append(record)
    if (record := pipe.flush()) is not None:
        records.append(record)
    live_df = pd.DataFrame(live, columns=["timestamp", "raw", "smoothed", "status"])
    minutes = pd.DataFrame([(r.start, r.people_count, r.n_samples) for r in records],
                           columns=["timestamp", "people_count", "n_samples"])
    return live_df, minutes


def changes(series: pd.Series) -> int:
    return int((series != series.shift()).sum() - 1)


def build(args: argparse.Namespace) -> None:
    fps, _, w, h = video_info(args.video)
    roi = Roi.from_json((ROI_DIR / f"{args.camera}.json").read_text())
    samples = load_samples()
    print(f"{len(samples)} samples, {len(samples) / args.rate / 3600:.1f} h of video")

    # Thresholds only depend on the per-minute counts, not on the classifier settings.
    _, minutes = run(samples, fps, w, h, roi, StatusThresholds(1, 2), 0, args.window)
    th = thresholds_from_percentiles(minutes.people_count.tolist(), args.low_pct, args.high_pct, args.margin)
    print(f"Per-minute counts: min={minutes.people_count.min()} median={minutes.people_count.median():g} "
          f"max={minutes.people_count.max()}")
    print(f"Thresholds from p{args.low_pct:g}/p{args.high_pct:g}: Normal from {th.normal_from:g}, "
          f"Ramai from {th.ramai_from:g}, margin {th.margin:g}")

    variants = {
        "no margin, no dwell": (StatusThresholds(th.normal_from, th.ramai_from, 0), 0),
        f"margin {th.margin:g}": (th, 0),
        f"margin {th.margin:g} + dwell {args.dwell:g}s": (th, args.dwell),
    }
    rows = []
    for name, (variant, dwell) in variants.items():
        live, _ = run(samples, fps, w, h, roi, variant, dwell, args.window)
        clf = HysteresisClassifier(variant)
        minute_status = pd.Series([clf.update(c) for c in minutes.people_count])
        rows.append({
            "variant": name,
            "live_changes": changes(live.status),
            "live_changes_per_hour": changes(live.status) / (len(live) / args.rate / 3600),
            "minute_changes": changes(minute_status),
            **{f"share_{s}": (live.status == s).mean() for s in ("Sepi", "Normal", "Ramai")},
        })
        if dwell:
            final_live = live
    report = pd.DataFrame(rows)

    clf = HysteresisClassifier(th)
    minutes["crowd_status"] = [clf.update(c) for c in minutes.people_count]
    minutes.insert(0, "camera_id", args.camera)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    minutes.to_csv(OUT_DIR / f"{args.camera}_minutes.csv", index=False)
    report.to_csv(OUT_DIR / f"{args.camera}_flicker.csv", index=False, float_format="%.3f")
    plot(final_live, minutes, th, OUT_DIR / f"{args.camera}_full.png", args)
    print(report.to_string(index=False, float_format=lambda v: f"{v:.2f}"))
    print(f"Saved per-minute dataset ({len(minutes)} rows), report, and plot to {OUT_DIR}")


def plot(live, minutes, th, path, args) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, (ax, ax2) = plt.subplots(2, 1, figsize=(14, 7), sharex=True, height_ratios=[3, 1])
    top = max(minutes.people_count.max(), th.ramai_from) * 1.2
    ax.axhspan(0, th.normal_from, color="#9ad1d4", alpha=0.25, label="Sepi")
    ax.axhspan(th.normal_from, th.ramai_from, color="#b39ddb", alpha=0.25, label="Normal")
    ax.axhspan(th.ramai_from, top, color="#f48fb1", alpha=0.25, label="Ramai")
    ax.plot(minutes.timestamp, minutes.people_count, color="#c62828", lw=1, label="record / menit")
    ax.set_ylim(0, top)
    ax.set_ylabel("jumlah orang")
    ax.legend(loc="upper right", ncol=4, fontsize=8)
    ax.set_title(f"{args.camera}: seluruh rekaman, threshold p{args.low_pct:g}/p{args.high_pct:g} = "
                 f"{th.normal_from:g}/{th.ramai_from:g}, margin {th.margin:g}, dwell {args.dwell:g}s")
    level = live.status.map({"Sepi": 0, "Normal": 1, "Ramai": 2})
    ax2.step(live.timestamp, level, where="post", color="#1f4e79", lw=0.8)
    ax2.set_yticks([0, 1, 2], ["Sepi", "Normal", "Ramai"])
    ax2.set_ylabel("status live")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    ext = sub.add_parser("extract")
    ext.add_argument("--chunk", type=int, default=0)
    ext.add_argument("--list", action="store_true", help="Print the number of chunks and exit")
    ext.add_argument("--rate", type=float, default=1, help="Detection samples per second")
    ext.add_argument("--model", default="yolo11n.pt")
    ext.add_argument("--imgsz", type=int, default=960)
    ext.add_argument("--tiles", default="2x2")
    ext.add_argument("--conf", type=float, default=0.15)
    ext.add_argument("--overlap", type=float, default=0.2)
    ext.add_argument("--full-imgsz", type=int, default=960)

    bld = sub.add_parser("build")
    bld.add_argument("--camera", default="kabukicho")
    bld.add_argument("--rate", type=float, default=1, help="Must match extract --rate")
    bld.add_argument("--window", type=float, default=5, help="Rolling median window in seconds")
    bld.add_argument("--low-pct", type=float, default=25)
    bld.add_argument("--high-pct", type=float, default=75)
    bld.add_argument("--margin", type=float, default=2)
    bld.add_argument("--dwell", type=float, default=30)

    for p in (ext, bld):
        p.add_argument("--video", type=Path, default=VIDEO)
    args = parser.parse_args()
    extract(args) if args.cmd == "extract" else build(args)


if __name__ == "__main__":
    main()
