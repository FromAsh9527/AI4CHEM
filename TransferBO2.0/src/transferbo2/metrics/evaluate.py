"""Evaluation metrics for transfer BO."""

from __future__ import annotations

from typing import Dict, List, Sequence

import numpy as np


def best_so_far(values: Sequence[float]) -> np.ndarray:
    out = []
    cur = -np.inf
    for v in values:
        cur = max(cur, float(v))
        out.append(cur)
    return np.asarray(out, dtype=float)


def optimisation_auc(bsf: Sequence[float]) -> float:
    return float(np.sum(np.asarray(bsf, dtype=float)))


def simple_regret(bsf: Sequence[float], y_star: float) -> np.ndarray:
    return np.asarray(y_star, dtype=float) - np.asarray(bsf, dtype=float)


def topk_hit_rate(indices: Sequence[int], top_mask: np.ndarray, t: int) -> float:
    chosen = np.asarray(indices[:t], dtype=int)
    if len(chosen) == 0:
        return 0.0
    return float(np.any(top_mask[chosen]))


def threshold_attainment(bsf: Sequence[float], tau: float) -> int | None:
    arr = np.asarray(bsf, dtype=float)
    hits = np.where(arr >= tau)[0]
    return int(hits[0] + 1) if len(hits) else None


def summarize_run(
    values: Sequence[float],
    *,
    y_star: float,
    top_mask: np.ndarray,
    indices: Sequence[int],
    thresholds: Sequence[float] = (70.0, 0.95),
) -> Dict:
    bsf = best_so_far(values)
    # thresholds: absolute or fraction of y_star if <= 1
    t_stats = {}
    for tau in thresholds:
        thr = float(tau * y_star) if 0 < tau <= 1 else float(tau)
        t_stats[f"T_{tau}"] = threshold_attainment(bsf, thr)
    return {
        "auc": optimisation_auc(bsf),
        "final_best": float(bsf[-1]) if len(bsf) else float("nan"),
        "final_regret": float(y_star - bsf[-1]) if len(bsf) else float("nan"),
        "hit10_top5pct": topk_hit_rate(indices, top_mask, min(10, len(indices))),
        "y_star": float(y_star),
        "best_so_far": bsf.tolist(),
        **t_stats,
    }


def negative_transfer_rate(auc_transfer: Sequence[float], auc_cold: Sequence[float]) -> float:
    a = np.asarray(auc_transfer, dtype=float)
    b = np.asarray(auc_cold, dtype=float)
    n = min(len(a), len(b))
    if n == 0:
        return float("nan")
    return float(np.mean(a[:n] < b[:n]))
