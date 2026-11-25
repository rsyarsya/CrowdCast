"""Draw a region of interest (ROI) polygon on one video frame.

Run from the backend folder:
    .\\.venv\\Scripts\\python.exe experiments\\roi_tool.py --camera kabukicho --minute 390

Controls:
    left click   add a point
    right click  remove the last point
    Enter        save (needs at least 3 points)
    Esc          quit without saving

Click the corners of the floor area where people should be counted. A person
counts when the FEET (bottom-center of the box) are inside the polygon.
The polygon is saved with normalized 0-1 coordinates to
experiments/configs/roi/<camera>.json, so it works at any resolution.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.services.vision.roi import Roi  # noqa: E402

ROI_DIR = BACKEND_DIR / "experiments" / "configs" / "roi"
WINDOW = "CrowdCast ROI - left: add, right: undo, Enter: save, Esc: quit"


def read_frame(path: Path, minute: float):
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise SystemExit(f"Cannot open {path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(minute * 60 * fps))
    ok, frame = cap.read()
    cap.release()
    if not ok:
        raise SystemExit(f"Cannot read a frame at minute {minute}")
    return frame


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--camera", required=True, help="Camera name, used as the file name")
    parser.add_argument("--video", type=Path, default=next((BACKEND_DIR / "data" / "videos").glob("*.mp4"), None))
    parser.add_argument("--minute", type=float, default=0, help="Video position of the frame to draw on")
    args = parser.parse_args()

    frame = read_frame(args.video, args.minute)
    h, w = frame.shape[:2]
    out_path = ROI_DIR / f"{args.camera}.json"
    points: list[tuple[int, int]] = []
    if out_path.exists():
        points = [(int(x * w), int(y * h)) for x, y in Roi.from_json(out_path.read_text()).points]
        print(f"Loaded existing ROI from {out_path}")

    def on_mouse(event, x, y, _flags, _param):
        if event == cv2.EVENT_LBUTTONDOWN:
            points.append((x, y))
        elif event == cv2.EVENT_RBUTTONDOWN and points:
            points.pop()

    cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WINDOW, w, h)
    cv2.setMouseCallback(WINDOW, on_mouse)
    while True:
        view = frame.copy()
        if len(points) >= 3:
            overlay = view.copy()
            cv2.fillPoly(overlay, [np.array(points, dtype=np.int32)], (0, 200, 255))
            view = cv2.addWeighted(overlay, 0.3, view, 0.7, 0)
        for i, p in enumerate(points):
            cv2.circle(view, p, 5, (0, 0, 255), -1)
            if i:
                cv2.line(view, points[i - 1], p, (0, 255, 255), 2)
        if len(points) >= 3:
            cv2.line(view, points[-1], points[0], (0, 255, 255), 1)
        cv2.putText(view, f"{len(points)} points", (10, h - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.imshow(WINDOW, view)

        key = cv2.waitKey(30) & 0xFF
        if key == 27 or cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
            print("Quit without saving.")
            break
        if key in (13, 10):
            if len(points) < 3:
                print("Need at least 3 points.")
                continue
            roi = Roi.from_points([(min(max(x / w, 0), 1), min(max(y / h, 0), 1)) for x, y in points])
            ROI_DIR.mkdir(parents=True, exist_ok=True)
            out_path.write_text(roi.to_json() + "\n", encoding="utf-8")
            cv2.imwrite(str(BACKEND_DIR / "experiments" / "outputs" / f"roi_{args.camera}.jpg"), view)
            print(f"Saved {len(points)} points to {out_path}")
            break
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
