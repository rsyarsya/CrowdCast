import math

import pytest

from app.services.forecast.metrics import score


def test_score_matches_hand_computed_values() -> None:
    s = score([5, 8, 2], [4, 10, 2], ["Normal", "Normal", "Sepi"], ["Normal", "Ramai", "Sepi"])
    assert s.samples == 3
    assert s.mae == pytest.approx(1.0)
    assert s.rmse == pytest.approx(math.sqrt(5 / 3))
    assert s.bias == pytest.approx(-1 / 3)
    assert s.status_accuracy == pytest.approx(2 / 3)


def test_empty_score_has_no_metrics() -> None:
    s = score([], [], [], [])
    assert (s.samples, s.mae, s.rmse, s.bias, s.status_accuracy) == (0, None, None, None, None)


def test_length_mismatch_is_rejected() -> None:
    with pytest.raises(ValueError):
        score([1, 2], [1], ["Sepi", "Sepi"], ["Sepi", "Sepi"])
