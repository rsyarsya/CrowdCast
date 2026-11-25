"""Region of interest (ROI): the floor area where people are counted.

The polygon is stored in normalized coordinates (0-1 of frame width/height) so
the same ROI works for any video resolution of that camera.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from app.services.vision.types import AnchorMode, Box

Point = tuple[float, float]


@dataclass(frozen=True, slots=True)
class Roi:
    """Polygon with normalized (x, y) points in the range 0-1."""

    points: tuple[Point, ...]

    def __post_init__(self) -> None:
        if len(self.points) < 3:
            raise ValueError("An ROI polygon needs at least 3 points")
        for x, y in self.points:
            if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
                raise ValueError(f"ROI point ({x}, {y}) is outside the 0-1 range")

    @classmethod
    def from_points(cls, points: Iterable[Sequence[float]]) -> Roi:
        return cls(tuple((float(x), float(y)) for x, y in points))

    @classmethod
    def from_json(cls, text: str) -> Roi:
        """Parse `{"points": [[x, y], ...]}`."""
        return cls.from_points(json.loads(text)["points"])

    def to_json(self) -> str:
        return json.dumps({"points": [list(p) for p in self.points]})

    def to_pixels(self, frame_w: int, frame_h: int) -> list[Point]:
        return [(x * frame_w, y * frame_h) for x, y in self.points]


def anchor_point(box: Box, mode: AnchorMode = "foot") -> Point:
    """Point that represents a person's position: bottom-center (foot) or top-center (head)."""
    x = (box.x1 + box.x2) / 2
    return (x, box.y2) if mode == "foot" else (x, box.y1)


def point_in_polygon(point: Point, polygon: Sequence[Point]) -> bool:
    """Ray casting: count how often a horizontal ray from the point crosses the polygon edges.

    An odd number of crossings means the point is inside. Works for concave polygons.
    """
    x, y = point
    inside = False
    n = len(polygon)
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            x_cross = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < x_cross:
                inside = not inside
    return inside


def count_in_roi(
    boxes: Iterable[Box],
    roi: Roi | None,
    frame_w: int,
    frame_h: int,
    anchor: AnchorMode = "foot",
) -> int:
    """Number of boxes whose anchor point lies inside the ROI. No ROI means the whole frame."""
    boxes = list(boxes)
    if roi is None:
        return len(boxes)
    polygon = roi.to_pixels(frame_w, frame_h)
    return sum(point_in_polygon(anchor_point(b, anchor), polygon) for b in boxes)
