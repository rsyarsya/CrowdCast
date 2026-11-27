import pytest

from app.services.vision.roi import Roi, anchor_point, count_in_roi, point_in_polygon
from app.services.vision.types import Box

SQUARE = [(0, 0), (10, 0), (10, 10), (0, 10)]
# L-shape (concave): the top-right quarter is missing.
L_SHAPE = [(0, 0), (5, 0), (5, 5), (10, 5), (10, 10), (0, 10)]


@pytest.mark.parametrize(
    ("point", "inside"),
    [((5, 5), True), ((-1, 5), False), ((11, 5), False), ((5, 11), False)],
)
def test_point_in_square(point, inside):
    assert point_in_polygon(point, SQUARE) is inside


def test_point_in_concave_polygon():
    assert point_in_polygon((2, 2), L_SHAPE)
    assert not point_in_polygon((8, 2), L_SHAPE)  # in the missing corner
    assert point_in_polygon((8, 8), L_SHAPE)


def test_anchor_point_foot_and_head():
    box = Box(10, 20, 30, 80)
    assert anchor_point(box, "foot") == (20, 80)
    assert anchor_point(box, "head") == (20, 20)


def test_roi_scales_with_resolution():
    roi = Roi.from_points([(0, 0.5), (1, 0.5), (1, 1), (0, 1)])  # bottom half
    box = Box(100, 300, 140, 400)  # feet at y=400
    assert count_in_roi([box], roi, 640, 480) == 1  # 400 > 240
    assert count_in_roi([box], roi, 1280, 960) == 0  # 400 < 480


def test_count_uses_anchor_mode():
    roi = Roi.from_points([(0, 0), (1, 0), (1, 0.5), (0, 0.5)])  # top half of 100x100
    box = Box(40, 30, 60, 70)  # head inside, feet outside
    assert count_in_roi([box], roi, 100, 100, "head") == 1
    assert count_in_roi([box], roi, 100, 100, "foot") == 0


def test_no_roi_counts_everything():
    boxes = [Box(0, 0, 1, 1), Box(5, 5, 6, 6)]
    assert count_in_roi(boxes, None, 10, 10) == 2


def test_roi_json_roundtrip():
    roi = Roi.from_points([(0.1, 0.2), (0.9, 0.2), (0.5, 0.8)])
    assert Roi.from_json(roi.to_json()) == roi


@pytest.mark.parametrize("points", [[(0, 0), (1, 1)], [(0, 0), (1.5, 0), (1, 1)]])
def test_invalid_roi_rejected(points):
    with pytest.raises(ValueError):
        Roi.from_points(points)


def test_person_cut_by_frame_edge_counts_in_roi_drawn_to_the_edge():
    roi = Roi.from_points([(0, 0.5), (1, 0.5), (1, 1), (0, 1)])  # bottom half, down to the edge
    box = Box(10, 60, 20, 100)  # feet exactly on the bottom border of a 100x100 frame
    assert count_in_roi([box], roi, 100, 100) == 1
