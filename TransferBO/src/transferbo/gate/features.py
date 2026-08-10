"""Cheap, interpretable TransferGate features.

Hard rule: features may use source (X_s, y_s) and target X_t only.
Target responses y_t must never enter this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence

import numpy as np

FEATURE_NAMES: list[str] = [
    "fp_jaccard_mean",
    "fp_jaccard_p90",
    "mmd_rbf",
    "mean_min_l2",
    "rank_corr_proxy",
    "source_top_entropy",
    "source_y_skew",
    "source_y_std",
    "source_top_frac_spread",
    "src_frac",
    "rep_morgan",
    "rep_drfp",
    "rep_fragprint",
    "rep_ohe",
    "rep_other",
]


@dataclass
class GateFeatureInputs:
    X_source: np.ndarray
    y_source: np.ndarray
    X_target: np.ndarray
    representation: str
    source_fraction: float = 1.0
    seed: int = 0


def _as_float2d(X: np.ndarray) -> np.ndarray:
    X = np.asarray(X, dtype=np.float64)
    if X.ndim == 1:
        X = X.reshape(-1, 1)
    return X


def _jaccard_row_vs_matrix(a: np.ndarray, B: np.ndarray) -> np.ndarray:
    """Jaccard of binary row a against each row of B."""
    a_bin = a > 0.5
    B_bin = B > 0.5
    inter = B_bin & a_bin
    union = B_bin | a_bin
    inter_n = inter.sum(axis=1).astype(np.float64)
    union_n = union.sum(axis=1).astype(np.float64)
    return inter_n / np.maximum(union_n, 1.0)


def fp_jaccard_stats(
    X_s: np.ndarray,
    X_t: np.ndarray,
    *,
    top_k: int = 5,
    max_target: int = 200,
    rng: np.random.Generator,
) -> tuple[float, float]:
    """Mean / p90 of top-k source Jaccard for subsampled target rows."""
    n_t = X_t.shape[0]
    idx = np.arange(n_t)
    if n_t > max_target:
        idx = rng.choice(n_t, size=max_target, replace=False)
    scores = []
    for i in idx:
        jac = _jaccard_row_vs_matrix(X_t[i], X_s)
        k = min(top_k, len(jac))
        scores.append(float(np.mean(np.partition(jac, -k)[-k:])))
    arr = np.asarray(scores, dtype=np.float64)
    return float(np.mean(arr)), float(np.percentile(arr, 90))


def mmd_rbf(
    X: np.ndarray,
    Y: np.ndarray,
    *,
    gamma: Optional[float] = None,
    max_n: int = 120,
    rng: np.random.Generator,
) -> float:
    """Biased MMD^2 with RBF kernel (subsampled)."""
    if len(X) > max_n:
        X = X[rng.choice(len(X), size=max_n, replace=False)]
    if len(Y) > max_n:
        Y = Y[rng.choice(len(Y), size=max_n, replace=False)]
    XY = np.vstack([X, Y])
    # median heuristic on pairwise L2 of a subsample
    if gamma is None:
        m = min(80, len(XY))
        sub = XY[rng.choice(len(XY), size=m, replace=False)]
        d = np.linalg.norm(sub[:, None, :] - sub[None, :, :], axis=-1)
        med = float(np.median(d[d > 0])) if np.any(d > 0) else 1.0
        gamma = 1.0 / (2.0 * (med**2 + 1e-8))

    def kmat(A: np.ndarray, B: np.ndarray) -> np.ndarray:
        d2 = ((A[:, None, :] - B[None, :, :]) ** 2).sum(axis=-1)
        return np.exp(-gamma * d2)

    Kxx = kmat(X, X)
    Kyy = kmat(Y, Y)
    Kxy = kmat(X, Y)
    n, m = len(X), len(Y)
    return float(Kxx.mean() + Kyy.mean() - 2.0 * Kxy.mean())


def mean_min_l2(
    X_s: np.ndarray,
    X_t: np.ndarray,
    *,
    max_target: int = 200,
    rng: np.random.Generator,
) -> float:
    n_t = X_t.shape[0]
    idx = np.arange(n_t)
    if n_t > max_target:
        idx = rng.choice(n_t, size=max_target, replace=False)
    mins = []
    for i in idx:
        d = np.linalg.norm(X_s - X_t[i], axis=1)
        mins.append(float(np.min(d)))
    return float(np.mean(mins))


def rank_corr_proxy(
    X_s: np.ndarray,
    y_s: np.ndarray,
    *,
    seed: int,
    n_rep: int = 3,
    knn: int = 5,
) -> float:
    """Source-only self-check: kNN transfer across random halves (Spearman)."""
    from scipy.stats import spearmanr

    rng = np.random.default_rng(seed)
    n = len(y_s)
    if n < 20:
        return 0.0
    cors = []
    for _ in range(n_rep):
        perm = rng.permutation(n)
        half = n // 2
        a, b = perm[:half], perm[half:]
        Xa, ya = X_s[a], y_s[a]
        Xb, yb = X_s[b], y_s[b]
        pred = np.empty(len(b), dtype=np.float64)
        for j, x in enumerate(Xb):
            d = np.linalg.norm(Xa - x, axis=1)
            nn = np.argpartition(d, min(knn, len(d) - 1))[:knn]
            pred[j] = float(np.mean(ya[nn]))
        r, _ = spearmanr(pred, yb)
        if np.isfinite(r):
            cors.append(float(r))
    return float(np.mean(cors)) if cors else 0.0


def source_top_entropy(X_s: np.ndarray, y_s: np.ndarray, *, top_frac: float = 0.1, k: int = 5) -> float:
    """Entropy of k-means clusters among source top responses (normalized)."""
    n = len(y_s)
    n_top = max(k, int(np.ceil(n * top_frac)))
    top_idx = np.argpartition(y_s, -n_top)[-n_top:]
    Xt = X_s[top_idx]
    # cheap 1-shot kmeans via random centers + nearest assignment
    rng = np.random.default_rng(0)
    k_eff = min(k, len(Xt))
    centers = Xt[rng.choice(len(Xt), size=k_eff, replace=False)]
    for _ in range(8):
        d = ((Xt[:, None, :] - centers[None, :, :]) ** 2).sum(axis=-1)
        lab = np.argmin(d, axis=1)
        for j in range(k_eff):
            mask = lab == j
            if np.any(mask):
                centers[j] = Xt[mask].mean(axis=0)
    counts = np.bincount(lab, minlength=k_eff).astype(np.float64)
    p = counts / counts.sum()
    p = p[p > 0]
    ent = float(-(p * np.log(p + 1e-12)).sum())
    return ent / np.log(k_eff)  # in [0, 1]


def source_top_frac_spread(X_s: np.ndarray, y_s: np.ndarray, *, top_frac: float = 0.1) -> float:
    """Mean pairwise L2 among top responders / global mean pairwise (proxy sharpness)."""
    n = len(y_s)
    n_top = max(2, int(np.ceil(n * top_frac)))
    top_idx = np.argpartition(y_s, -n_top)[-n_top:]
    Xt = X_s[top_idx]
    # subsample for cost
    rng = np.random.default_rng(1)
    n_ref = min(40, n)
    ref = X_s[rng.choice(n, size=n_ref, replace=False)]

    def mean_pair(A: np.ndarray) -> float:
        m = min(30, len(A))
        S = A[rng.choice(len(A), size=m, replace=False)]
        d = np.linalg.norm(S[:, None, :] - S[None, :, :], axis=-1)
        return float(d[np.triu_indices(m, 1)].mean()) if m > 1 else 0.0

    top_d = mean_pair(Xt)
    ref_d = mean_pair(ref)
    return float(top_d / (ref_d + 1e-8))


def _rep_one_hot(name: str) -> dict[str, float]:
    key = name.lower().strip()
    out = {
        "rep_morgan": 0.0,
        "rep_drfp": 0.0,
        "rep_fragprint": 0.0,
        "rep_ohe": 0.0,
        "rep_other": 0.0,
    }
    mapped = {
        "morgan": "rep_morgan",
        "drfp": "rep_drfp",
        "fragprint": "rep_fragprint",
        "ohe": "rep_ohe",
    }.get(key)
    if mapped:
        out[mapped] = 1.0
    else:
        out["rep_other"] = 1.0
    return out


def compute_gate_features(
    inputs: GateFeatureInputs,
    *,
    y_target: Any = None,
) -> dict[str, float]:
    """Compute φ for one (source, target, representation) pair.

    ``y_target`` is accepted only so callers cannot accidentally pass it via
    kwargs into silent use — if provided, we refuse.
    """
    if y_target is not None:
        raise ValueError("Gate features must not receive target labels (y_target).")

    X_s = _as_float2d(inputs.X_source)
    X_t = _as_float2d(inputs.X_target)
    y_s = np.asarray(inputs.y_source, dtype=np.float64).ravel()
    if len(X_s) != len(y_s):
        raise ValueError("X_source and y_source length mismatch")
    rng = np.random.default_rng(inputs.seed)

    jac_mean, jac_p90 = fp_jaccard_stats(X_s, X_t, rng=rng)
    feat: dict[str, float] = {
        "fp_jaccard_mean": jac_mean,
        "fp_jaccard_p90": jac_p90,
        "mmd_rbf": mmd_rbf(X_s, X_t, rng=rng),
        "mean_min_l2": mean_min_l2(X_s, X_t, rng=rng),
        "rank_corr_proxy": rank_corr_proxy(X_s, y_s, seed=inputs.seed),
        "source_top_entropy": source_top_entropy(X_s, y_s),
        "source_y_skew": float(_skew(y_s)),
        "source_y_std": float(np.std(y_s) / (np.abs(np.mean(y_s)) + 1e-8)),
        "source_top_frac_spread": source_top_frac_spread(X_s, y_s),
        "src_frac": float(inputs.source_fraction),
    }
    feat.update(_rep_one_hot(inputs.representation))
    # ensure stable key order / completeness
    return {k: float(feat[k]) for k in FEATURE_NAMES}


def features_to_vector(
    feat: Mapping[str, float],
    names: Optional[Sequence[str]] = None,
) -> np.ndarray:
    names = list(names) if names is not None else FEATURE_NAMES
    return np.asarray([float(feat[n]) for n in names], dtype=np.float64)


def _skew(y: np.ndarray) -> float:
    y = np.asarray(y, dtype=np.float64)
    m = y.mean()
    s = y.std()
    if s < 1e-12:
        return 0.0
    return float(np.mean(((y - m) / s) ** 3))
