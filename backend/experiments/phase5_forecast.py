"""Compare crowd forecasters (5, 15, 30 minutes ahead) on the per-minute dataset.

Run from the backend folder after `phase3_dataset.py build`:
    .\\.venv\\Scripts\\python.exe experiments\\phase5_forecast.py

The series is split by time: the first 60% of minutes for training, the next
20% for validation (model and hyperparameter choice), the last 20% for the
final test. Nothing is shuffled, so no model ever sees the future it predicts.
The model with the lowest mean validation MAE is saved to
data/models/forecast/<camera>.json or .pt for the vision worker.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.services.forecast.base import HORIZONS  # noqa: E402
from app.services.forecast.baselines import MovingAverageForecaster, NaiveForecaster  # noqa: E402
from app.services.forecast.linear import LinearLagForecaster  # noqa: E402
from app.services.forecast.metrics import score  # noqa: E402
from app.services.vision.classifier import StatusThresholds, classify  # noqa: E402

DATASET = BACKEND_DIR / "experiments" / "outputs" / "phase3" / "kabukicho_minutes.csv"
OUT_DIR = BACKEND_DIR / "experiments" / "outputs" / "phase5"
MODELS_DIR = BACKEND_DIR / "data" / "models" / "forecast"
LAGS = 30


def windows(series: np.ndarray, start: int, end: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Samples whose last observed minute i lies in [start, end) and whose targets exist.

    Inputs may reach back before `start` (the past is allowed), targets never
    reach past the end of the series.
    """
    idx = [i for i in range(max(start, LAGS - 1), end) if i + max(HORIZONS) < len(series)]
    X = np.stack([series[i - LAGS + 1 : i + 1] for i in idx])
    y = np.stack([[series[i + h] for h in HORIZONS] for i in idx])
    return X, y, np.array(idx)


def predict_all(model, X: np.ndarray) -> np.ndarray:
    if hasattr(model, "predict_many"):
        return model.predict_many(X)
    return np.array([[model.predict(list(row))[h] for h in HORIZONS] for row in X])


def evaluate(pred: np.ndarray, y: np.ndarray, th: StatusThresholds) -> dict[str, float]:
    pred = np.clip(np.rint(pred), 0, None)
    row = {}
    for k, h in enumerate(HORIZONS):
        p, a = pred[:, k].tolist(), y[:, k].tolist()
        s = score(p, a, [classify(v, th) for v in p], [classify(v, th) for v in a])
        row[f"mae_{h}"] = s.mae
        row[f"rmse_{h}"] = s.rmse
        row[f"status_acc_{h}"] = s.status_accuracy
    row["mae_mean"] = np.mean([row[f"mae_{h}"] for h in HORIZONS])
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", type=Path, default=DATASET)
    parser.add_argument("--camera-code", default="CAM-02", help="Name of the saved model file")
    parser.add_argument("--normal", type=float, default=4, help="Camera threshold_normal")
    parser.add_argument("--ramai", type=float, default=12, help="Camera threshold_ramai")
    parser.add_argument("--seeds", type=int, default=5, help="GRU training runs averaged in the report")
    parser.add_argument("--no-gru", action="store_true")
    args = parser.parse_args()

    df = pd.read_csv(args.dataset, parse_dates=["timestamp"]).sort_values("timestamp")
    series = df["people_count"].to_numpy(dtype=float)
    n = len(series)
    n_train, n_val = int(n * 0.6), int(n * 0.8)
    th = StatusThresholds(args.normal, args.ramai)
    splits = {
        "train": windows(series, 0, n_train - max(HORIZONS)),  # train targets stay inside train
        "val": windows(series, n_train, n_val - max(HORIZONS)),
        "test": windows(series, n_val, n),
    }
    print(f"{n} minutes: train {n_train}, val {n_val - n_train}, test {n - n_val}; "
          f"samples train/val/test = {', '.join(str(len(s[1])) for s in splits.values())}")
    train_series = series[:n_train]

    candidates: dict[str, object] = {"naive": NaiveForecaster()}
    for window in (5, 10, 15, 30):
        candidates[f"moving_average_{window}"] = MovingAverageForecaster(window)
    for ridge in (1.0, 10.0, 100.0, 1000.0):
        candidates[f"linear_ridge{ridge:g}"] = LinearLagForecaster.fit(train_series, LAGS, ridge)

    gru_runs = []
    if not args.no_gru:
        from app.services.forecast.gru import GruForecaster

        (Xtr, ytr, _), (Xva, yva, _) = splits["train"], splits["val"]
        mean, std = float(train_series.mean()), float(train_series.std() or 1.0)
        gru_runs = [GruForecaster.fit(Xtr, ytr, Xva, yva, mean, std, seed=s) for s in range(args.seeds)]

    rows = []
    for name, model in list(candidates.items()) + [(f"gru_seed{i}", m) for i, m in enumerate(gru_runs)]:
        for split in ("val", "test"):
            X, y, _ = splits[split]
            rows.append({"model": name, "split": split, **evaluate(predict_all(model, X), y, th)})
    report = pd.DataFrame(rows)

    # One row per model family for choosing: GRU is averaged over seeds.
    report["family"] = report["model"].where(~report["model"].str.startswith("gru"), "gru (mean of seeds)")
    summary = report.groupby(["family", "split"], as_index=False).mean(numeric_only=True)
    val = summary[summary.split == "val"].sort_values("mae_mean")
    best_family = val.iloc[0]["family"]
    if best_family == "gru (mean of seeds)":
        gru_val = report[(report.split == "val") & report.model.str.startswith("gru")]
        best_name = gru_val.sort_values("mae_mean").iloc[0]["model"]
        best_model = gru_runs[int(best_name.removeprefix("gru_seed"))]
    else:
        best_name, best_model = best_family, candidates[best_family]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report.to_csv(OUT_DIR / "forecast_report.csv", index=False, float_format="%.3f")
    cols = ["family", "split", "mae_mean"] + [f"mae_{h}" for h in HORIZONS] + [f"status_acc_{h}" for h in HORIZONS]
    print("\nValidation (choose):")
    print(val[cols].to_string(index=False, float_format=lambda v: f"{v:.2f}"))
    test = summary[summary.split == "test"].set_index("family").loc[val.family].reset_index()
    print("\nTest (report):")
    print(test[cols].to_string(index=False, float_format=lambda v: f"{v:.2f}"))

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    for old in MODELS_DIR.glob(f"{args.camera_code}.*"):
        old.unlink()
    if best_name.startswith("gru"):
        path = MODELS_DIR / f"{args.camera_code}.pt"
        best_model.save(path)
    else:
        path = MODELS_DIR / f"{args.camera_code}.json"
        if isinstance(best_model, LinearLagForecaster):
            best_model.save(path)
        elif isinstance(best_model, MovingAverageForecaster):
            path.write_text(f'{{"type": "moving_average", "window": {best_model.window}}}', encoding="utf-8")
        else:
            path.write_text('{"type": "naive"}', encoding="utf-8")
    print(f"\nChosen on validation: {best_name} -> {path}")
    plot(series, splits["test"], best_model, best_name, n_val, df["timestamp"], OUT_DIR / "forecast_test.png")


def plot(series, test_split, model, name, n_val, timestamps, path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    X, _, idx = test_split
    pred = np.clip(np.rint(predict_all(model, X)), 0, None)
    fig, axes = plt.subplots(len(HORIZONS), 1, figsize=(12, 8), sharex=True)
    for k, (ax, h) in enumerate(zip(axes, HORIZONS)):
        ax.plot(timestamps.iloc[n_val:], series[n_val:], color="0.4", lw=1, label="aktual")
        ax.plot(timestamps.iloc[idx + h], pred[:, k], color="#c62828", lw=1.2, label=f"prediksi {h} menit")
        ax.set_ylabel("orang")
        ax.legend(loc="upper right", fontsize=8)
    axes[0].set_title(f"Data test: {name}")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


if __name__ == "__main__":
    main()
