"""Offline person detection experiments.

Subcommands (run from the backend folder):
    .\\.venv\\Scripts\\python.exe experiments\\phase1_detect.py mall
    .\\.venv\\Scripts\\python.exe experiments\\phase1_detect.py video --model yolo11s.pt --imgsz 960 --conf 0.25

`mall`  : runs a model/imgsz grid on the 2000 Mall Dataset frames and compares
          the people count with the ground truth (mall_gt.mat). Writes
          outputs/phase1/mall_summary.csv, per-frame CSVs, and annotated samples.
`video` : samples frames from a long video (no ground truth), saves annotated
          images and reports inference FPS. Used for visual checks only.

Counting rule for Mall: the ground truth marks each person's HEAD inside the
dataset ROI, so a detection is counted when the top-center of its bounding box
(roughly the head) falls inside the ROI mask.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import scipy.io as sio
import torch

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

# Detection code lives in the app so the worker and the experiments share it.
from app.services.vision.detector import (  # noqa: E402
    detect,
    detect_tiled,
    load_model,
    parse_tiles,
)
MALL_DIR = BACKEND_DIR / "data" / "mall" / "mall_dataset"
OUT_DIR = BACKEND_DIR / "experiments" / "outputs" / "phase1"
ROWS_DIR = OUT_DIR / "rows"  # one result row per finished config, so runs can resume

DEFAULT_MODELS = ["yolov8n.pt", "yolo11n.pt", "yolo11s.pt"]
DEFAULT_IMGSZ = [640, 960]
DEFAULT_CONFS = [0.25, 0.4]
WARMUP_FRAMES = 10


def run_detector(model, image: np.ndarray, imgsz: int, conf: float, tiles: str, args) -> np.ndarray:
    grid = parse_tiles(tiles)
    if grid is None:
        return detect(model, image, imgsz, conf)
    return detect_tiled(model, image, imgsz, conf, grid, args.overlap, args.full_imgsz)


def head_points(boxes: np.ndarray) -> np.ndarray:
    """Top-center of each box, used as the head position."""
    return np.stack([(boxes[:, 0] + boxes[:, 2]) / 2, boxes[:, 1]], axis=1)


def count_in_mask(boxes: np.ndarray, mask: np.ndarray) -> int:
    if len(boxes) == 0:
        return 0
    h, w = mask.shape
    pts = head_points(boxes)
    xs = np.clip(pts[:, 0].astype(int), 0, w - 1)
    ys = np.clip(pts[:, 1].astype(int), 0, h - 1)
    return int((mask[ys, xs] > 0).sum())


def draw(image: np.ndarray, boxes: np.ndarray, text: str, mask: np.ndarray | None = None) -> np.ndarray:
    out = image.copy()
    if mask is not None:
        contours, _ = cv2.findContours((mask > 0).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(out, contours, -1, (255, 200, 0), 2)
    for x1, y1, x2, y2, score in boxes:
        cv2.rectangle(out, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 1)
        cv2.putText(out, f"{score:.2f}", (int(x1), int(y1) - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 0), 1)
    cv2.rectangle(out, (0, 0), (out.shape[1], 24), (0, 0, 0), -1)
    cv2.putText(out, text, (6, 17), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    return out


class LazyImages:
    def __init__(self, paths: list[Path]) -> None:
        self.paths = paths

    def __len__(self) -> int:
        return len(self.paths)

    def __getitem__(self, index):
        if isinstance(index, slice):
            return [cv2.imread(str(p)) for p in self.paths[index]]
        return cv2.imread(str(self.paths[index]))

    def __iter__(self):
        return (cv2.imread(str(p)) for p in self.paths)


def load_mall() -> tuple[list[Path], np.ndarray, np.ndarray]:
    frames = sorted((MALL_DIR / "frames").glob("seq_*.jpg"))
    gt = sio.loadmat(MALL_DIR / "mall_gt.mat")["count"].ravel().astype(int)
    mask = sio.loadmat(MALL_DIR / "perspective_roi.mat")["roi"][0, 0]["mask"]
    if len(frames) != len(gt):
        raise SystemExit(f"Frame count {len(frames)} does not match ground truth {len(gt)}")
    return frames, gt, mask


def run_mall(args: argparse.Namespace) -> None:
    frames, gt, mask = load_mall()
    if args.limit:
        frames, gt = frames[: args.limit], gt[: args.limit]
    images = LazyImages(frames)  # read from disk on demand; all 2000 frames would use ~1.8 GB RAM
    min_conf = min(args.confs)
    sample_idx = [0, len(images) // 2, len(images) - 1]
    rows = []

    for model_name in args.models:
        model = load_model(model_name)
        for imgsz, tiles in [(i, t) for i in args.imgsz for t in args.tiles]:
            tag = f"{Path(model_name).stem}_{imgsz}" + ("" if tiles == "none" else f"_tiles{tiles}")
            row_files = [ROWS_DIR / f"{tag}_conf{c}.csv" for c in args.confs]
            if not args.limit and all(f.exists() for f in row_files):
                print(f"== {tag}: already done, skipping")
                continue
            print(f"\n== {tag}: {len(images)} frames")
            for img in images[:WARMUP_FRAMES]:
                run_detector(model, img, imgsz, min_conf, tiles, args)

            # Detect once at the lowest conf, then filter for higher thresholds.
            all_boxes, start = [], time.perf_counter()
            for i, img in enumerate(images, 1):
                all_boxes.append(run_detector(model, img, imgsz, min_conf, tiles, args))
                if i % 500 == 0:
                    print(f"   {i}/{len(images)}")
            fps = len(images) / (time.perf_counter() - start)

            for conf in args.confs:
                kept = [b[b[:, 4] >= conf] for b in all_boxes]
                pred_roi = np.array([count_in_mask(b, mask) for b in kept])
                pred_full = np.array([len(b) for b in kept])
                err = pred_roi - gt
                rows.append(
                    {
                        "model": Path(model_name).stem,
                        "imgsz": imgsz,
                        "tiles": tiles,
                        "conf": conf,
                        "mae": np.abs(err).mean(),
                        "rmse": np.sqrt((err**2).mean()),
                        "bias": err.mean(),
                        "mae_full_frame": np.abs(pred_full - gt).mean(),
                        "fps": fps,
                    }
                )
                print(f"   conf={conf}: MAE={rows[-1]['mae']:.2f} bias={rows[-1]['bias']:+.2f} fps={fps:.1f}")
                if not args.limit:
                    pd.DataFrame([rows[-1]]).to_csv(ROWS_DIR / f"{tag}_conf{conf}.csv", index=False)
                pd.DataFrame({"frame": np.arange(1, len(gt) + 1), "gt": gt, "pred": pred_roi}).to_csv(
                    OUT_DIR / f"mall_{tag}_conf{conf}.csv", index=False
                )
                for i in sample_idx:
                    text = f"{tag} conf={conf} pred={pred_roi[i]} gt={gt[i]}"
                    cv2.imwrite(str(OUT_DIR / "samples" / f"{tag}_conf{conf}_f{i + 1}.jpg"), draw(images[i], kept[i], text, mask))
        del model
        torch.cuda.empty_cache()

    if not args.limit:  # include configs finished in earlier runs
        rows = [r for f in sorted(ROWS_DIR.glob("*.csv")) for r in pd.read_csv(f).to_dict("records")]
    summary = pd.DataFrame(rows)
    summary["tiles"] = summary.get("tiles", pd.Series(dtype=str)).fillna("none")
    summary = summary.sort_values("mae")
    summary.to_csv(OUT_DIR / "mall_summary.csv", index=False, float_format="%.3f")
    print("\n" + summary.to_string(index=False, float_format=lambda v: f"{v:.2f}"))


def run_video(args: argparse.Namespace) -> None:
    cap = cv2.VideoCapture(str(args.path))
    if not cap.isOpened():
        raise SystemExit(f"Cannot open {args.path}")
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps_src = cap.get(cv2.CAP_PROP_FPS) or 30
    positions = np.linspace(0, total - 1, args.samples, dtype=int)
    model = load_model(args.model)
    out = OUT_DIR / "video"
    out.mkdir(parents=True, exist_ok=True)

    times, counts = [], []
    for n, pos in enumerate(positions):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(pos))
        ok, frame = cap.read()
        if not ok:
            continue
        start = time.perf_counter()
        boxes = run_detector(model, frame, args.imgsz, args.conf, args.tiles, args)
        if n > 0:  # first call includes warm-up
            times.append(time.perf_counter() - start)
        counts.append(len(boxes))
        minute = pos / fps_src / 60
        text = f"{Path(args.model).stem} imgsz={args.imgsz} tiles={args.tiles} conf={args.conf} t={minute:.1f}min count={len(boxes)}"
        suffix = "" if args.tiles == "none" else f"_tiles{args.tiles}"
        cv2.imwrite(str(out / f"{Path(args.path).stem}_{args.imgsz}{suffix}_{n:02d}.jpg"), draw(frame, boxes, text))
    cap.release()
    print(f"Saved {len(counts)} annotated frames to {out}")
    print(f"Counts: min={min(counts)} mean={np.mean(counts):.1f} max={max(counts)}")
    print(f"Inference FPS: {1 / np.mean(times):.1f}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    mall = sub.add_parser("mall")
    mall.add_argument("--models", nargs="+", default=DEFAULT_MODELS)
    mall.add_argument("--imgsz", nargs="+", type=int, default=DEFAULT_IMGSZ)
    mall.add_argument("--confs", nargs="+", type=float, default=DEFAULT_CONFS)
    mall.add_argument("--tiles", nargs="+", default=["none"], help="'none' or ROWSxCOLS, e.g. 2x2")
    mall.add_argument("--limit", type=int, default=0, help="Use only the first N frames (quick test)")

    video = sub.add_parser("video")
    video.add_argument("--path", type=Path, default=next((BACKEND_DIR / "data" / "videos").glob("*.mp4"), None))
    video.add_argument("--model", default="yolo11s.pt")
    video.add_argument("--imgsz", type=int, default=960)
    video.add_argument("--conf", type=float, default=0.25)
    video.add_argument("--samples", type=int, default=12)
    video.add_argument("--tiles", default="none", help="'none' or ROWSxCOLS, e.g. 2x2")

    for p in (mall, video):
        p.add_argument("--overlap", type=float, default=0.2, help="Tile overlap as a fraction of tile size")
        p.add_argument("--full-imgsz", type=int, default=960, help="imgsz of the extra full-frame pass when tiling")

    args = parser.parse_args()
    (OUT_DIR / "samples").mkdir(parents=True, exist_ok=True)
    ROWS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Device: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'}")
    run_mall(args) if args.cmd == "mall" else run_video(args)


if __name__ == "__main__":
    main()
