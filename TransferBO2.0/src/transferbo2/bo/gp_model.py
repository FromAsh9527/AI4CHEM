"""Gaussian process surrogate and acquisition helpers (sklearn)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
from scipy.stats import norm
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel, Matern, WhiteKernel


@dataclass
class GPSurrogate:
    normalize_y: bool = True
    seed: int = 0
    model: Optional[GaussianProcessRegressor] = None

    def fit(self, X: np.ndarray, y: np.ndarray, sample_weight: Optional[np.ndarray] = None) -> "GPSurrogate":
        X = np.asarray(X, dtype=float)
        y = np.asarray(y, dtype=float).reshape(-1)
        if sample_weight is not None:
            # sklearn GP has no sample_weight; approximate by repeating high-weight points
            w = np.asarray(sample_weight, dtype=float)
            w = np.clip(w, 1e-3, None)
            w = w / w.mean()
            reps = np.maximum(1, np.round(w).astype(int))
            # cap expansion
            if reps.sum() > 400:
                reps = np.maximum(1, np.round(reps * 400 / reps.sum()).astype(int))
            X = np.repeat(X, reps, axis=0)
            y = np.repeat(y, reps, axis=0)
        kernel = ConstantKernel(1.0, (1e-3, 1e3)) * Matern(
            length_scale=np.ones(X.shape[1]), length_scale_bounds=(1e-2, 1e2), nu=2.5
        ) + WhiteKernel(noise_level=1e-3, noise_level_bounds=(1e-8, 1e1))
        self.model = GaussianProcessRegressor(
            kernel=kernel,
            normalize_y=self.normalize_y,
            n_restarts_optimizer=1,
            random_state=self.seed,
            alpha=1e-6,
        )
        self.model.fit(X, y)
        return self

    def predict(self, X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        assert self.model is not None
        mu, std = self.model.predict(np.asarray(X, dtype=float), return_std=True)
        return mu.astype(float), np.maximum(std.astype(float), 1e-9)


def expected_improvement(mu: np.ndarray, std: np.ndarray, best: float, xi: float = 0.01) -> np.ndarray:
    z = (mu - best - xi) / std
    return (mu - best - xi) * norm.cdf(z) + std * norm.pdf(z)


def ucb(mu: np.ndarray, std: np.ndarray, beta: float = 2.0) -> np.ndarray:
    return mu + beta * std


def select_next(
    mu: np.ndarray,
    std: np.ndarray,
    observed_mask: np.ndarray,
    *,
    acquisition: str = "ei",
    best: float = 0.0,
    beta: float = 2.0,
) -> int:
    acq = expected_improvement(mu, std, best) if acquisition == "ei" else ucb(mu, std, beta=beta)
    acq = acq.copy()
    acq[np.asarray(observed_mask, dtype=bool)] = -np.inf
    return int(np.argmax(acq))
