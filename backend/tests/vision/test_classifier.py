import pytest

from app.services.vision.classifier import HysteresisClassifier, StatusThresholds, classify

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
