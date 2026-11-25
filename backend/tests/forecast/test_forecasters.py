import json
from pathlib import Path

import pytest

from app.services.forecast.base import HORIZONS
from app.services.forecast.baselines import MovingAverageForecaster, NaiveForecaster
from app.services.forecast.linear import LinearLagForecaster
from app.services.forecast.loader import find_model_file, load_forecaster


def test_naive_repeats_last_value():
    assert NaiveForecaster().predict([1, 2, 7]) == {5: 7.0, 15: 7.0, 30: 7.0}


def test_moving_average_uses_last_window():
    assert MovingAverageForecaster(3).predict([100, 1, 2, 3]) == {h: 2.0 for h in HORIZONS}


def test_forecasters_need_enough_history():
    with pytest.raises(ValueError):
        MovingAverageForecaster(10).predict([1, 2, 3])


def test_linear_predict_is_plain_weighted_sum():
    model = LinearLagForecaster(
        2, coef={h: [0.5, 0.5] for h in HORIZONS}, intercept={5: 1.0, 15: 2.0, 30: 3.0}
    )
    assert model.predict([9, 4, 6]) == {5: 6.0, 15: 7.0, 30: 8.0}


def test_linear_fit_learns_a_trend():
    pytest.importorskip("numpy")
    series = [0.5 * t for t in range(200)]
    model = LinearLagForecaster.fit(series, lags=5, ridge=1e-6)
    pred = model.predict(series[:100])  # last value 49.5 at t=99
    for h in HORIZONS:
        assert pred[h] == pytest.approx(0.5 * (99 + h), abs=1e-3)


def test_linear_json_roundtrip(tmp_path: Path):
    model = LinearLagForecaster(2, {h: [0.1, 0.2] for h in HORIZONS}, {h: float(h) for h in HORIZONS})
    path = tmp_path / "CAM-02.json"
    model.save(path)
    loaded = load_forecaster(path)
    assert loaded.predict([3, 4]) == model.predict([3, 4])


@pytest.mark.parametrize(
    ("content", "expected"),
    [({"type": "moving_average", "window": 5}, "moving_average_5"), ({"type": "naive"}, "naive")],
)
def test_loader_reads_baseline_files(tmp_path: Path, content: dict, expected: str):
    path = tmp_path / "CAM-02.json"
    path.write_text(json.dumps(content), encoding="utf-8")
    assert load_forecaster(path).name == expected


def test_loader_falls_back_to_moving_average(tmp_path: Path):
    assert load_forecaster(None).name == "moving_average_10"
    assert load_forecaster(tmp_path / "missing.json").name == "moving_average_10"


def test_find_model_file_prefers_gru(tmp_path: Path):
    assert find_model_file(tmp_path, "CAM-02") is None
    (tmp_path / "CAM-02.json").write_text("{}")
    assert find_model_file(tmp_path, "CAM-02").suffix == ".json"
    (tmp_path / "CAM-02.pt").write_bytes(b"")
    assert find_model_file(tmp_path, "CAM-02").suffix == ".pt"


def test_gru_save_and_load(tmp_path: Path):
    np = pytest.importorskip("numpy")
    pytest.importorskip("torch")
    from app.services.forecast.gru import GruForecaster

    series = np.sin(np.arange(300) / 10) * 5 + 10
    X = np.stack([series[i - 10 : i] for i in range(10, 250)])
    y = np.stack([[series[i - 1 + h] for h in HORIZONS] for i in range(10, 250)])
    model = GruForecaster.fit(X[:200], y[:200], X[200:], y[200:], float(series.mean()), float(series.std()), epochs=5)
    model.save(tmp_path / "CAM-02.pt")
    loaded = load_forecaster(tmp_path / "CAM-02.pt")
    assert loaded.predict(list(series[:10])) == pytest.approx(model.predict(list(series[:10])))
