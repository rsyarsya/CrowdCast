"""Small GRU network that reads the last `lags` minutes and predicts all horizons at once.

Needs torch (requirements-ai.txt). Counts are normalized with the mean and
standard deviation of the TRAINING data only, so no information from the
validation or test period leaks into the model.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import numpy as np
import torch
from torch import nn

from app.services.forecast.base import HORIZONS, check_history


class _GruNet(nn.Module):
    def __init__(self, hidden: int) -> None:
        super().__init__()
        self.gru = nn.GRU(input_size=1, hidden_size=hidden, batch_first=True)
        self.head = nn.Linear(hidden, len(HORIZONS))

    def forward(self, x: torch.Tensor) -> torch.Tensor:  # x: (batch, lags, 1)
        _, last_hidden = self.gru(x)
        return self.head(last_hidden[-1])


class GruForecaster:
    def __init__(self, net: _GruNet, lags: int, mean: float, std: float, hidden: int) -> None:
        self.net = net.eval()
        self.lags = lags
        self.min_history = lags
        self.mean = mean
        self.std = std
        self.hidden = hidden
        self.name = f"gru_h{hidden}_lag{lags}"

    def predict(self, history: Sequence[float]) -> dict[int, float]:
        check_history(history, self.min_history)
        x = (torch.tensor(history[-self.lags :], dtype=torch.float32) - self.mean) / self.std
        with torch.no_grad():
            out = self.net(x.view(1, -1, 1))[0] * self.std + self.mean
        return {h: float(v) for h, v in zip(HORIZONS, out)}

    def predict_many(self, windows: np.ndarray) -> np.ndarray:
        """Batch prediction for evaluation: windows (n, lags) -> (n, len(HORIZONS))."""
        x = torch.tensor((windows - self.mean) / self.std, dtype=torch.float32).unsqueeze(-1)
        with torch.no_grad():
            return (self.net(x) * self.std + self.mean).numpy()

    @classmethod
    def fit(
        cls,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray,
        y_val: np.ndarray,
        mean: float,
        std: float,
        hidden: int = 16,
        epochs: int = 300,
        lr: float = 0.01,
        patience: int = 30,
        seed: int = 0,
    ) -> GruForecaster:
        """Train with early stopping: keep the weights with the lowest validation loss."""
        torch.manual_seed(seed)
        net = _GruNet(hidden)
        opt = torch.optim.Adam(net.parameters(), lr=lr)
        loss_fn = nn.L1Loss()  # MAE, the metric we report

        def tensors(X: np.ndarray, y: np.ndarray) -> tuple[torch.Tensor, torch.Tensor]:
            return (
                torch.tensor((X - mean) / std, dtype=torch.float32).unsqueeze(-1),
                torch.tensor((y - mean) / std, dtype=torch.float32),
            )

        xt, yt = tensors(X_train, y_train)
        xv, yv = tensors(X_val, y_val)
        best, best_state, waited = float("inf"), None, 0
        for _ in range(epochs):
            net.train()
            opt.zero_grad()
            loss_fn(net(xt), yt).backward()
            opt.step()
            net.eval()
            with torch.no_grad():
                val_loss = loss_fn(net(xv), yv).item()
            if val_loss < best - 1e-5:
                best, waited = val_loss, 0
                best_state = {k: v.clone() for k, v in net.state_dict().items()}
            else:
                waited += 1
                if waited >= patience:
                    break
        net.load_state_dict(best_state)
        return cls(net, X_train.shape[1], mean, std, hidden)

    def save(self, path: Path) -> None:
        torch.save(
            {
                "type": "gru",
                "state_dict": self.net.state_dict(),
                "lags": self.lags,
                "mean": self.mean,
                "std": self.std,
                "hidden": self.hidden,
            },
            path,
        )

    @classmethod
    def load(cls, path: Path) -> GruForecaster:
        data = torch.load(path, map_location="cpu", weights_only=True)
        net = _GruNet(data["hidden"])
        net.load_state_dict(data["state_dict"])
        return cls(net, data["lags"], data["mean"], data["std"], data["hidden"])
