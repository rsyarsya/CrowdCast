import pytest

# numpy is an optional AI dependency; CI only installs requirements.txt.
np = pytest.importorskip("numpy")

from app.services.vision.detector import merge_sources, parse_tiles, tile_windows  # noqa: E402


def test_tile_windows_cover_image_with_overlap():
    windows = tile_windows(480, 640, 2, 2, 0.2)
    assert len(windows) == 4
    assert windows[0][:2] == (0, 0)
    assert max(w[2] for w in windows) == 640
    assert max(w[3] for w in windows) == 480
    left, right = windows[0], windows[1]
    assert right[0] < left[2]  # neighbouring tiles overlap


def test_merge_joins_partial_box_from_other_tile():
    boxes = np.array([[0, 0, 10, 20, 0.9], [0, 10, 10, 20, 0.5]], dtype=np.float32)
    merged = merge_sources(boxes, np.array([0, 1]))
    assert merged.tolist() == [[0, 0, 10, 20, pytest.approx(0.9)]]


def test_merge_keeps_close_people_from_same_tile():
    boxes = np.array([[50, 0, 60, 20, 0.8], [51, 1, 59, 19, 0.7]], dtype=np.float32)
    assert len(merge_sources(boxes, np.array([0, 0]))) == 2


def test_parse_tiles():
    assert parse_tiles("none") is None
    assert parse_tiles("2x3") == (2, 3)
