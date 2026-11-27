"""Measure counting accuracy on the real camera against hand-labeled frames.

Run from the backend folder:
    .\\.venv\\Scripts\\python.exe experiments\\count_eval.py sample
    .\\.venv\\Scripts\\python.exe experiments\\count_eval.py label
    .\\.venv\\Scripts\\python.exe experiments\\count_eval.py evaluate

`sample`   picks frames spread over the night, the same number from Sepi, Normal,
           and Ramai minutes of the per-minute dataset, and writes them to
           experiments/labels/<camera>_counts.json.
`label`    opens each frame. Click the FEET of every person in or near the ROI.
           Only clicks inside the ROI count, the same rule the pipeline uses.
               left click   add a person
               right click  remove the last person
               Enter        save this frame and go to the next
               b            go back one frame
               Esc          save and quit (resume later where you stopped)
`evaluate` compares the labels with the YOLO detections saved by
           phase3_dataset.py extract for the same frames: count error, status
           agreement, and person-level precision and recall.
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.services.forecast.metrics import score  # noqa: E402
from app.services.vision.classifier import StatusThresholds, classify  # noqa: E402
from app.services.vision.roi import Roi, anchor_point, box_in_polygon, point_in_polygon  # noqa: E402
from app.services.vision.types import Box  # noqa: E402

EXP_DIR = BACKEND_DIR / "experiments"
DET_DIR = EXP_DIR / "outputs" / "phase3" / "detections"
OUT_DIR = EXP_DIR / "outputs" / "count_eval"
LABEL_DIR = EXP_DIR / "labels"
ROI_DIR = EXP_DIR / "configs" / "roi"
VIDEO = next((BACKEND_DIR / "data" / "videos").glob("*.mp4"), None)
VIDEO_START = datetime.fromisoformat("2026-08-25T18:00:00+09:00")
STATUSES = ("Sepi", "Normal", "Ramai")
WINDOW = "CrowdCast labels - left: add, right: undo, Enter: next, b: back, Esc: quit"


def label_path(camera: str) -> Path:
    return LABEL_DIR / f"{camera}_counts.json"


def load_labels(camera: str) -> dict:
    return json.loads(label_path(camera).read_text(encoding="utf-8"))


def save_labels(camera: str, data: dict) -> None:
    LABEL_DIR.mkdir(parents=True, exist_ok=True)
    label_path(camera).write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")


def video_info(path: Path) -> tuple[float, int, int]:
    import cv2

    cap = cv2.VideoCapture(str(path))
    info = (cap.get(cv2.CAP_PROP_FPS) or 30, int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
    cap.release()
    return info


def detected_frames() -> np.ndarray:
    frames = [pd.read_csv(f, usecols=["frame"]).frame.unique() for f in sorted(DET_DIR.glob("chunk_*.csv.gz"))]
    if not frames:
        raise SystemExit("No saved detections. Run phase3_dataset.py extract first.")
    return np.sort(np.concatenate(frames))


def sample(args: argparse.Namespace) -> None:
    path = label_path(args.camera)
    if path.exists() and not args.force:
        raise SystemExit(f"{path} exists. Use --force to replace it and lose its labels.")
    fps, _, _ = video_info(args.video)
    minutes = pd.read_csv(EXP_DIR / "outputs" / "phase3" / f"{args.camera}_minutes.csv", parse_dates=["timestamp"])
    available = detected_frames()
    per_status = -(-args.frames // len(STATUSES))
    chosen = []
    for status in STATUSES:
        group = minutes[minutes.crowd_status == status].sort_values("timestamp")
        if group.empty:
            continue
        picks = np.unique(np.linspace(0, len(group) - 1, min(per_status, len(group))).round().astype(int))
        for row in group.iloc[picks].itertuples():
            target = ((row.timestamp - VIDEO_START).total_seconds() + 30) * fps
            frame = int(available[np.abs(available - target).argmin()])
            chosen.append({"frame": frame, "minute": row.timestamp.isoformat(), "minute_status": status, "points": None})
    chosen.sort(key=lambda item: item["frame"])
    save_labels(args.camera, {"video": args.video.name, "frames": chosen})
    print(f"Saved {len(chosen)} frames to {path}")


def read_frame(cap, index: int):
    import cv2

    cap.set(cv2.CAP_PROP_POS_FRAMES, index)
    ok, frame = cap.read()
    if not ok:
        raise SystemExit(f"Cannot read frame {index}")
    return frame


def label(args: argparse.Namespace) -> None:
    import cv2

    data = load_labels(args.camera)
    items = data["frames"]
    roi = Roi.from_json((ROI_DIR / f"{args.camera}.json").read_text())
    cap = cv2.VideoCapture(str(args.video))
    position = next((i for i, item in enumerate(items) if item["points"] is None), 0)
    clicks: list[tuple[int, int]] = []

    def on_mouse(event, x, y, _flags, _param):
        if event == cv2.EVENT_LBUTTONDOWN:
            clicks.append((x, y))
        elif event == cv2.EVENT_RBUTTONDOWN and clicks:
            clicks.pop()

    cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(WINDOW, on_mouse)
    while 0 <= position < len(items):
        item = items[position]
        frame = read_frame(cap, item["frame"])
        h, w = frame.shape[:2]
        polygon = roi.to_pixels(w, h)
        cv2.resizeWindow(WINDOW, w, h)
        clicks[:] = [(round(x * w), round(y * h)) for x, y in item["points"] or []]
        loaded = list(clicks)
        action = None
        while action is None:
            view = frame.copy()
            cv2.polylines(view, [np.array(polygon, dtype=np.int32)], True, (0, 255, 255), 1)
            inside = 0
            for x, y in clicks:
                hit = point_in_polygon((x, y), polygon)
                inside += hit
                cv2.circle(view, (x, y), 5, (0, 255, 0) if hit else (150, 150, 150), -1)
                cv2.circle(view, (x, y), 6, (0, 0, 0), 1)
            text = f"frame {position + 1}/{len(items)}  people in ROI: {inside}"
            cv2.putText(view, text, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 4)
            cv2.putText(view, text, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            cv2.imshow(WINDOW, view)
            key = cv2.waitKey(30) & 0xFF
            if key in (13, 10):
                action = "next"
            elif key == ord("b"):
                action = "back"
            elif key == 27 or cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
                action = "quit"
        if action != "quit" or clicks != loaded:
            item["points"] = [[x / w, y / h] for x, y in clicks]
        save_labels(args.camera, data)
        if action == "quit":
            break
        position += 1 if action == "next" else -1
        position = max(position, 0)
    cap.release()
    cv2.destroyAllWindows()
    done = sum(item["points"] is not None for item in items)
    print(f"{done}/{len(items)} frames labeled, saved to {label_path(args.camera)}")


def load_boxes(frames: set[int]) -> dict[int, list[Box]]:
    boxes: dict[int, list[Box]] = {f: [] for f in frames}
    for path in sorted(DET_DIR.glob("chunk_*.csv.gz")):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            df = pd.read_csv(f)
        for r in df[df.frame.isin(frames) & (df.score >= 0)].itertuples():
            boxes[int(r.frame)].append(Box(r.x1, r.y1, r.x2, r.y2, r.score))
    return boxes


def match(clicks: list[tuple[float, float]], boxes: list[Box], pad: float) -> list[tuple[int, int]]:
    """Greedy one-to-one pairs (click, box): a click pairs with a box when it lies in
    the box grown by `pad` of its size, closest foot point first."""
    candidates = []
    for ci, (x, y) in enumerate(clicks):
        for bi, b in enumerate(boxes):
            dw, dh = (b.x2 - b.x1) * pad, (b.y2 - b.y1) * pad
            if b.x1 - dw <= x <= b.x2 + dw and b.y1 - dh <= y <= b.y2 + dh:
                fx, fy = anchor_point(b)
                candidates.append((np.hypot(fx - x, fy - y), ci, bi))
    pairs, used_c, used_b = [], set(), set()
    for _, ci, bi in sorted(candidates):
        if ci not in used_c and bi not in used_b:
            pairs.append((ci, bi))
            used_c.add(ci)
            used_b.add(bi)
    return pairs


def evaluate(args: argparse.Namespace) -> None:
    data = load_labels(args.camera)
    items = [item for item in data["frames"] if item["points"] is not None]
    if not items:
        raise SystemExit("No labeled frames yet. Run label first.")
    _, w, h = video_info(args.video)
    polygon = Roi.from_json((ROI_DIR / f"{args.camera}.json").read_text()).to_pixels(w, h)
    th = StatusThresholds(args.normal_from, args.ramai_from)
    boxes_by_frame = load_boxes({item["frame"] for item in items})

    rows = []
    for item in items:
        clicks = [(x * w, y * h) for x, y in item["points"]]
        boxes = boxes_by_frame[item["frame"]]
        click_in = [point_in_polygon(c, polygon) for c in clicks]
        box_in = [box_in_polygon(b, polygon, w, h) for b in boxes]
        pairs = match(clicks, boxes, args.pad)
        tp = sum(click_in[c] and box_in[b] for c, b in pairs)
        border = sum(click_in[c] != box_in[b] for c, b in pairs)
        matched_c, matched_b = {c for c, _ in pairs}, {b for _, b in pairs}
        fn = sum(click_in[c] for c in range(len(clicks)) if c not in matched_c)
        fp = sum(box_in[b] for b in range(len(boxes)) if b not in matched_b)
        rows.append({
            "frame": item["frame"],
            "minute": item["minute"],
            "minute_status": item["minute_status"],
            "label_count": sum(click_in),
            "pred_count": sum(box_in),
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "border": border,
        })
    df = pd.DataFrame(rows)
    df["error"] = df.pred_count - df.label_count
    df["label_status"] = [classify(c, th) for c in df.label_count]
    df["pred_status"] = [classify(c, th) for c in df.pred_count]

    total = score(df.pred_count.tolist(), df.label_count.tolist(), df.pred_status.tolist(), df.label_status.tolist())
    tp, fp, fn = df.tp.sum(), df.fp.sum(), df.fn.sum()
    lines = [
        f"{args.camera}: {len(df)} labeled frames, {df.label_count.sum()} people in ROI by hand, "
        f"{df.pred_count.sum()} by the pipeline",
        f"count  MAE {total.mae:.2f}  RMSE {total.rmse:.2f}  bias {total.bias:+.2f}  "
        f"status agreement {total.status_accuracy:.1%} (Normal from {args.normal_from}, Ramai from {args.ramai_from})",
        f"person precision {tp / max(tp + fp, 1):.1%}  recall {tp / max(tp + fn, 1):.1%}  "
        f"(TP {tp}, FP {fp}, FN {fn}, {df.border.sum()} matched across the ROI edge)",
        "by labeled status:",
    ]
    for status in STATUSES:
        part = df[df.label_status == status]
        if len(part):
            s = score(part.pred_count.tolist(), part.label_count.tolist(), part.pred_status.tolist(), part.label_status.tolist())
            lines.append(f"  {status:<6} n={len(part):>2}  MAE {s.mae:.2f}  bias {s.bias:+.2f}  status {s.status_accuracy:.1%}")
    report = "\n".join(lines)
    print(report)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_DIR / f"{args.camera}_frames.csv", index=False)
    (OUT_DIR / f"{args.camera}_summary.txt").write_text(report + "\n", encoding="utf-8")
    plot(df, th, OUT_DIR / f"{args.camera}_scatter.png", args.camera)
    draw_worst(df, data, boxes_by_frame, polygon, args)
    print(f"Saved per-frame CSV, summary, scatter plot, and worst frames to {OUT_DIR}")


def plot(df: pd.DataFrame, th: StatusThresholds, path: Path, camera: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    top = max(df.label_count.max(), df.pred_count.max(), th.ramai_from) + 2
    fig, ax = plt.subplots(figsize=(6, 6))
    for value in (th.normal_from, th.ramai_from):
        ax.axvline(value, color="#999", lw=0.8, ls=":")
        ax.axhline(value, color="#999", lw=0.8, ls=":")
    ax.plot([0, top], [0, top], color="#555", lw=1, label="tepat")
    jitter = np.random.default_rng(0).uniform(-0.15, 0.15, (2, len(df)))
    ax.scatter(df.label_count + jitter[0], df.pred_count + jitter[1], s=28, color="#c62828", alpha=0.8)
    ax.set_xlim(-0.5, top)
    ax.set_ylim(-0.5, top)
    ax.set_xlabel("jumlah orang (label manual)")
    ax.set_ylabel("jumlah orang (pipeline)")
    ax.set_title(f"{camera}: hitungan per frame, garis titik = threshold")
    ax.legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def draw_worst(df, data, boxes_by_frame, polygon, args) -> None:
    import cv2

    points = {item["frame"]: item["points"] for item in data["frames"]}
    cap = cv2.VideoCapture(str(args.video))
    worst = df.reindex(df.error.abs().sort_values(ascending=False).index).head(args.worst)
    for rank, row in enumerate(worst.itertuples(), 1):
        frame = read_frame(cap, row.frame)
        h, w = frame.shape[:2]
        cv2.polylines(frame, [np.array(polygon, dtype=np.int32)], True, (0, 255, 255), 1)
        for b in boxes_by_frame[row.frame]:
            color = (0, 0, 255) if box_in_polygon(b, polygon, w, h) else (120, 120, 120)
            cv2.rectangle(frame, (int(b.x1), int(b.y1)), (int(b.x2), int(b.y2)), color, 1)
        for x, y in points[row.frame]:
            cv2.circle(frame, (round(x * w), round(y * h)), 5, (0, 255, 0), -1)
        text = f"label {row.label_count}  pipeline {row.pred_count}  (green: label, red: detection)"
        cv2.putText(frame, text, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 4)
        cv2.putText(frame, text, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.imwrite(str(OUT_DIR / f"{args.camera}_worst_{rank}.jpg"), frame)
    cap.release()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    smp = sub.add_parser("sample")
    smp.add_argument("--frames", type=int, default=40)
    smp.add_argument("--force", action="store_true")
    sub.add_parser("label")
    ev = sub.add_parser("evaluate")
    ev.add_argument("--normal-from", type=int, default=4)
    ev.add_argument("--ramai-from", type=int, default=12)
    ev.add_argument("--pad", type=float, default=0.15, help="Box growth for matching clicks")
    ev.add_argument("--worst", type=int, default=3, help="Frames to draw with the largest error")
    for p in sub.choices.values():
        p.add_argument("--camera", default="kabukicho")
        p.add_argument("--video", type=Path, default=VIDEO)
    args = parser.parse_args()
    {"sample": sample, "label": label, "evaluate": evaluate}[args.cmd](args)


if __name__ == "__main__":
    main()
