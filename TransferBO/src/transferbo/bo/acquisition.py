"""Acquisition functions for discrete candidate pools."""

from __future__ import annotations

import numpy as np
from scipy.stats import norm


def expected_improvement(
    mean: np.ndarray,
    std: np.ndarray,
    best_f: float,
    *,
    maximize: bool = True,
    xi: float = 0.01,
) -> np.ndarray:
    mean = np.asarray(mean, dtype=np.float64)
    std = np.asarray(std, dtype=np.float64)
    std = np.maximum(std, 1e-9)
    if maximize:
        z = (mean - best_f - xi) / std
        return (mean - best_f - xi) * norm.cdf(z) + std * norm.pdf(z)
    z = (best_f - mean - xi) / std
    return (best_f - mean - xi) * norm.cdf(z) + std * norm.pdf(z)


def upper_confidence_bound(
    mean: np.ndarray,
    std: np.ndarray,
    *,
    beta: float = 2.0,
    maximize: bool = True,
) -> np.ndarray:
    mean = np.asarray(mean, dtype=np.float64)
    std = np.asarray(std, dtype=np.float64)
    if maximize:
        return mean + np.sqrt(beta) * std
    return -(mean - np.sqrt(beta) * std)


def select_next(
    mean: np.ndarray,
    std: np.ndarray,
    candidate_indices: np.ndarray,
    *,
    best_f: float,
    acquisition: str = "ei",
    batch_size: int = 1,
    ucb_beta: float = 2.0,
) -> np.ndarray:
    """Pick top-`batch_size` candidates by acquisition score (greedy batch)."""
    acq = acquisition.lower()
    if acq == "ei":
        scores = expected_improvement(mean, std, best_f, maximize=True)
    elif acq == "ucb":
        scores = upper_confidence_bound(mean, std, beta=ucb_beta, maximize=True)
    else:
        raise ValueError(f"Unknown acquisition: {acquisition}")

    order = np.argsort(-scores)
    chosen = candidate_indices[order[:batch_size]]
    return np.asarray(chosen, dtype=int)
