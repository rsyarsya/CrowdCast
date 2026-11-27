"""Short-term crowd forecasting (5, 15, 30 minutes ahead) from per-minute counts.

`base`, `baselines`, `linear` (predict) and `loader` are plain Python; fitting
the linear model needs numpy and the GRU needs torch.
"""
