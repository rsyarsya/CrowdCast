"""YOLO person detector with optional tiled (SAHI-style) inference.

Needs the optional AI dependencies (`requirements-ai.txt`): numpy here, and
ultralytics/torch when a model is loaded. The API never imports this module;
only the vision worker and the experiment scripts do.

Selected configuration from the Mall Dataset benchmark: yolo11n.pt, imgsz 960,
2x2 tiles with a full-frame pass, conf 0.15 (count MAE 3.6 vs 10.4 without tiles).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from app.services.vision.types import Box

PERSON_CLASS = 0  # COCO class id for "person"
WEIGHTS_DIR = Path(__file__).resolve().parents[3] / "data" / "models"


def load_model(name: str, weights_dir: Path = WEIGHTS_DIR) -> Any:
    """Load YOLO weights from data/models/, downloading them there on first use."""
    from ultralytics import YOLO

    weights_dir.mkdir(parents=True, exist_ok=True)
    path = weights_dir / name
    model = YOLO(str(path) if path.exists() else name)
    if not path.exists() and Path(name).exists():
        Path(name).replace(path)  # ultralytics downloads into the current folder
    return model


def _precision() -> str | None:
    import torch

    return "fp16" if torch.cuda.is_available() else None


def _to_array(result: Any) -> np.ndarray:
    boxes = result.boxes
    if boxes is None or len(boxes) == 0:
        return np.zeros((0, 5), dtype=np.float32)
    return np.hstack([boxes.xyxy.cpu().numpy(), boxes.conf.cpu().numpy()[:, None]]).astype(np.float32)


def detect(model: Any, image: np.ndarray, imgsz: int, conf: float) -> np.ndarray:
    """Return person boxes as an (N, 5) array: x1, y1, x2, y2, confidence."""
    result = model.predict(
        image, imgsz=imgsz, conf=conf, classes=[PERSON_CLASS], quantize=_precision(), verbose=False
    )[0]
    return _to_array(result)


def tile_windows(h: int, w: int, rows: int, cols: int, overlap: float) -> list[tuple[int, int, int, int]]:
    """Split an image into rows x cols windows (x1, y1, x2, y2) that overlap by `overlap` of a tile."""
    tile_w = int(np.ceil(w / (cols - (cols - 1) * overlap)))
    tile_h = int(np.ceil(h / (rows - (rows - 1) * overlap)))
    xs = np.linspace(0, w - tile_w, cols).astype(int) if cols > 1 else [0]
    ys = np.linspace(0, h - tile_h, rows).astype(int) if rows > 1 else [0]
    return [(int(x), int(y), min(int(x) + tile_w, w), min(int(y) + tile_h, h)) for y in ys for x in xs]


def merge_sources(boxes: np.ndarray, sources: np.ndarray, ios_thr: float = 0.6) -> np.ndarray:
    """Merge duplicate detections that come from DIFFERENT tiles (or tile vs full frame).

    A person near a tile border is seen by two tiles, often as a cut (partial) box.
    Two boxes are duplicates when intersection / area of the smaller box (IoS) is
    above `ios_thr`; they are replaced by their union box with the highest score.
    Boxes from the same source are never merged: YOLO already applied NMS there,
    and merging them would join two real people standing close together.
    """
    if len(boxes) == 0:
        return boxes
    order = np.argsort(-boxes[:, 4])
    boxes, sources = boxes[order].copy(), sources[order]
    area = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
    used = np.zeros(len(boxes), dtype=bool)
    merged = []
    for i in range(len(boxes)):
        if used[i]:
            continue
        used[i] = True
        box = boxes[i].copy()
        for j in range(i + 1, len(boxes)):
            if used[j] or sources[j] == sources[i]:
                continue
            ix = max(0.0, min(box[2], boxes[j, 2]) - max(box[0], boxes[j, 0]))
            iy = max(0.0, min(box[3], boxes[j, 3]) - max(box[1], boxes[j, 1]))
            if ix * iy / max(min(area[i], area[j]), 1e-6) > ios_thr:
                used[j] = True
                box[:4] = [min(box[0], boxes[j, 0]), min(box[1], boxes[j, 1]),
                           max(box[2], boxes[j, 2]), max(box[3], boxes[j, 3])]
        merged.append(box)
    return np.array(merged, dtype=np.float32)


def detect_tiled(
    model: Any, image: np.ndarray, imgsz: int, conf: float, grid: tuple[int, int], overlap: float, full_imgsz: int
) -> np.ndarray:
    """Run YOLO on overlapping crops plus the full frame, then merge.

    Small people become bigger relative to the model input, so fewer are missed.
    The full-frame pass catches big people that tiles cut in half.
    """
    h, w = image.shape[:2]
    windows = tile_windows(h, w, *grid, overlap)
    crops = [image[y1:y2, x1:x2] for x1, y1, x2, y2 in windows]
    results = model.predict(
        crops, imgsz=imgsz, conf=conf, classes=[PERSON_CLASS], quantize=_precision(), verbose=False
    )
    all_boxes, all_sources = [], []
    for src, ((x1, y1, _, _), res) in enumerate(zip(windows, results)):
        b = _to_array(res)
        b[:, [0, 2]] += x1
        b[:, [1, 3]] += y1
        all_boxes.append(b)
        all_sources.append(np.full(len(b), src))
    full = detect(model, image, full_imgsz, conf)
    all_boxes.append(full)
    all_sources.append(np.full(len(full), len(windows)))
    return merge_sources(np.vstack(all_boxes).astype(np.float32), np.concatenate(all_sources))


def parse_tiles(text: str) -> tuple[int, int] | None:
    """'none' -> None, '2x2' -> (2, 2) as (rows, cols)."""
    if text == "none":
        return None
    rows, cols = text.lower().split("x")
    return int(rows), int(cols)


class YoloDetector:
    """Callable detector used by the vision worker: frame in, list of Box out."""

    def __init__(
        self,
        weights: str = "yolo11n.pt",
        imgsz: int = 960,
        conf: float = 0.15,
        tiles: str = "2x2",
        overlap: float = 0.2,
        full_imgsz: int = 960,
    ) -> None:
        self.model = load_model(weights)
        self.imgsz = imgsz
        self.conf = conf
        self.grid = parse_tiles(tiles)
        self.overlap = overlap
        self.full_imgsz = full_imgsz

    def detect_array(self, frame: np.ndarray) -> np.ndarray:
        if self.grid is None:
            return detect(self.model, frame, self.imgsz, self.conf)
        return detect_tiled(self.model, frame, self.imgsz, self.conf, self.grid, self.overlap, self.full_imgsz)

    def __call__(self, frame: np.ndarray) -> list[Box]:
        return [Box(*map(float, row)) for row in self.detect_array(frame)]
