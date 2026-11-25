"""Draw the ROI, detections, count, and status on a frame and encode it as JPEG."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from zoneinfo import ZoneInfo

import cv2
import numpy as np

from app.services.vision.roi import Roi, anchor_point, point_in_polygon
from app.services.vision.types import Box, LiveState

# BGR colors close to the dashboard status palette.
STATUS_COLORS = {"Sepi": (212, 209, 154), "Normal": (219, 157, 179), "Ramai": (177, 143, 244)}
INSIDE = (80, 220, 80)
OUTSIDE = (150, 150, 150)
ROI_COLOR = (0, 215, 255)


def make_encoder(
    roi: Roi | None, max_width: int = 960, quality: int = 70, timezone: str = "Asia/Jakarta"
) -> Callable[[np.ndarray, list[Box], LiveState | None], bytes]:
    zone = ZoneInfo(timezone)
    params = [cv2.IMWRITE_JPEG_QUALITY, quality]

    def encode(frame: np.ndarray, boxes: list[Box], live: LiveState | None) -> bytes:
        h, w = frame.shape[:2]
        scale = min(1.0, max_width / w)
        image = cv2.resize(frame, (int(w * scale), int(h * scale))) if scale < 1 else frame.copy()
        polygon = roi.to_pixels(w, h) if roi else None

        if polygon:
            pts = np.array([(x * scale, y * scale) for x, y in polygon], dtype=np.int32)
            cv2.polylines(image, [pts], isClosed=True, color=ROI_COLOR, thickness=2)
        for box in boxes:
            inside = polygon is None or point_in_polygon(anchor_point(box), polygon)
            p1 = (int(box.x1 * scale), int(box.y1 * scale))
            p2 = (int(box.x2 * scale), int(box.y2 * scale))
            cv2.rectangle(image, p1, p2, INSIDE if inside else OUTSIDE, 1)

        _draw_banner(image, live, zone)
        ok, jpeg = cv2.imencode(".jpg", image, params)
        if not ok:
            raise RuntimeError("JPEG encoding failed")
        return jpeg.tobytes()

    return encode


def _draw_banner(image: np.ndarray, live: LiveState | None, zone: ZoneInfo) -> None:
    cv2.rectangle(image, (0, 0), (image.shape[1], 30), (0, 0, 0), -1)
    if live is None:
        text, color = "Menunggu deteksi...", (255, 255, 255)
    else:
        local: datetime = live.timestamp.astimezone(zone)
        text = f"{local:%H:%M:%S}  {live.raw_count} orang  |  {live.crowd_status}"
        color = STATUS_COLORS.get(live.crowd_status, (255, 255, 255))
    cv2.putText(image, text, (10, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2, cv2.LINE_AA)
