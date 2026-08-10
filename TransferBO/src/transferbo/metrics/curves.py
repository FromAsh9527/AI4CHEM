"""Best-so-far curves and top-k hitting times."""

from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd


def align_curves(curves: Sequence[Sequence[float]], budget: int | None = None) -> np.ndarray:
    """Stack curves to shape (n_seeds, T), forward-filling shorter runs."""
    if not curves:
        return np.zeros((0, 0))
    T = budget or max(len(c) for c in curves)
    out = np.full((len(curves), T), np.nan, dtype=float)
    for i, c in enumerate(curves):
        arr = np.asarray(c, dtype=float)
        n = min(len(arr), T)
        out[i, :n] = arr[:n]
        if n < T and n > 0:
            out[i, n:] = arr[n - 1]
    return out


def best_so_far_summary(
    curves: Sequence[Sequence[float]],
    *,
    budget: int | None = None,
) -> pd.DataFrame:
    """Mean ± std of best-so-far vs query index (1-based)."""
    mat = align_curves(curves, budget=budget)
    if mat.size == 0:
        return pd.DataFrame(columns=["query", "mean", "std", "n"])
    mean = np.nanmean(mat, axis=0)
    std = np.nanstd(mat, axis=0)
    n = np.sum(~np.isnan(mat), axis=0)
    return pd.DataFrame(
        {
            "query": np.arange(1, mat.shape[1] + 1),
            "mean": mean,
            "std": std,
            "n": n.astype(int),
        }
    )


def queries_to_threshold(
    curves: Sequence[Sequence[float]],
    threshold: float,
) -> np.ndarray:
    """First query index (1-based) at which best-so-far >= threshold; NaN if never."""
    out = []
    for c in curves:
        arr = np.asarray(c, dtype=float)
        hits = np.where(arr >= threshold)[0]
        out.append(float(hits[0] + 1) if len(hits) else np.nan)
    return np.asarray(out, dtype=float)
