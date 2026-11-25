import pytest

from app.services.vision.classifier import (
    HysteresisClassifier,
    StatusThresholds,
    classify,
    thresholds_from_percentiles,
)

TH = StatusThresholds(normal_from=10, ramai_from=30, margin=3)


@pytest.mark.parametrize(
    ("count", "status"),
    [(0, "Sepi"), (9.9, "Sepi"), (10, "Normal"), (29, "Normal"), (30, "Ramai"), (100, "Ramai")],
)
def test_classify_boundaries(count, status):
    assert classify(count, TH) == status


def test_hysteresis_does_not_flicker():
    clf = HysteresisClassifier(TH)
    statuses = [clf.update(c) for c in [29, 30, 29, 30, 28, 27.5]]
    assert statuses == ["Normal", "Ramai", "Ramai", "Ramai", "Ramai", "Ramai"]


def test_hysteresis_steps_down_below_margin():
    clf = HysteresisClassifier(TH)
    clf.update(35)
    assert clf.update(26.9) == "Normal"  # below 30 - 3
    assert clf.update(7.5) == "Normal"  # not below 10 - 3 yet
    assert clf.update(6) == "Sepi"


def test_hysteresis_can_drop_two_levels():
    clf = HysteresisClassifier(TH)
    clf.update(40)
    assert clf.update(0) == "Sepi"


def test_zero_margin_behaves_like_classify():
    th = StatusThresholds(10, 30)
    clf = HysteresisClassifier(th)
    for count in [5, 30, 29, 10, 9]:
        assert clf.update(count) == classify(count, th)


@pytest.mark.parametrize(
    ("normal_from", "ramai_from", "margin"),
    [(30, 10, 0), (0, 10, 0), (10, 30, -1), (10, 30, 10), (10, 12, 5)],
)
def test_invalid_thresholds_rejected(normal_from, ramai_from, margin):
    with pytest.raises(ValueError):
        StatusThresholds(normal_from, ramai_from, margin)


def test_dwell_ignores_short_peaks():
    clf = HysteresisClassifier(StatusThresholds(10, 30), dwell_s=30)
    assert clf.update(20, t=0) == "Normal"
    assert clf.update(35, t=5) == "Normal"  # Ramai proposed, not long enough
    assert clf.update(20, t=10) == "Normal"  # peak over, pending reset
    assert clf.update(35, t=20) == "Normal"
    assert clf.update(35, t=49) == "Normal"
    assert clf.update(35, t=50) == "Ramai"  # proposed for 30 s


def test_dwell_requires_timestamp():
    clf = HysteresisClassifier(StatusThresholds(10, 30), dwell_s=5)
    clf.update(20, t=0)
    with pytest.raises(ValueError):
        clf.update(35)


def test_thresholds_from_percentiles():
    counts = list(range(0, 41))  # 0..40 uniformly
    th = thresholds_from_percentiles(counts, 25, 75, margin=2)
    assert (th.normal_from, th.ramai_from, th.margin) == (10, 30, 2)


def test_thresholds_from_percentiles_shrinks_margin_for_narrow_data():
    th = thresholds_from_percentiles([5, 5, 6, 6, 7, 7, 8, 8], margin=3)
    assert th.margin < th.ramai_from - th.normal_from
