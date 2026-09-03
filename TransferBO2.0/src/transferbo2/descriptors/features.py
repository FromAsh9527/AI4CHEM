"""Condition and substrate feature builders."""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Sequence

import numpy as np
import pandas as pd
from sklearn.preprocessing import OneHotEncoder, StandardScaler


def _one_hot_encoder() -> OneHotEncoder:
    try:
        return OneHotEncoder(sparse_output=False, handle_unknown="ignore")
    except TypeError:  # sklearn < 1.2
        return OneHotEncoder(sparse=False, handle_unknown="ignore")


def one_hot_conditions(df: pd.DataFrame, cols: Optional[Sequence[str]] = None) -> np.ndarray:
    cols = list(cols or ["catalyst", "ligand", "base", "solvent"])
    enc = _one_hot_encoder()
    cat = enc.fit_transform(df[cols].astype(str))
    num_cols = [c for c in ["temperature_c", "time_h", "equiv"] if c in df.columns]
    if num_cols:
        num = StandardScaler().fit_transform(df[num_cols].astype(float).to_numpy())
        return np.hstack([cat, num])
    return cat


def align_condition_features(
    reference: pd.DataFrame,
    target: pd.DataFrame,
    cols: Optional[Sequence[str]] = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Fit OHE on reference∪target categories so feature dims match."""
    cols = list(cols or ["catalyst", "ligand", "base", "solvent"])
    enc = _one_hot_encoder()
    enc.fit(pd.concat([reference[cols], target[cols]], axis=0).astype(str))
    cat_ref = enc.transform(reference[cols].astype(str))
    cat_tgt = enc.transform(target[cols].astype(str))
    num_cols = [
        c
        for c in ["temperature_c", "time_h", "equiv"]
        if c in reference.columns and c in target.columns
    ]
    if num_cols:
        scaler = StandardScaler()
        num_ref = scaler.fit_transform(reference[num_cols].astype(float).to_numpy())
        num_tgt = scaler.transform(target[num_cols].astype(float).to_numpy())
        return np.hstack([cat_ref, num_ref]), np.hstack([cat_tgt, num_tgt])
    return cat_ref, cat_tgt


def descriptor_lookup(
    desc_df: pd.DataFrame,
    entity_ids: Sequence[str],
) -> np.ndarray:
    """Map entity_id -> descriptor rows; missing -> zeros."""
    if desc_df.empty:
        return np.zeros((len(entity_ids), 1), dtype=float)
    feat_cols = [c for c in desc_df.columns if c != "entity_id"]
    index = desc_df.set_index("entity_id")
    dim = len(feat_cols)
    out = np.zeros((len(entity_ids), dim), dtype=float)
    for i, eid in enumerate(entity_ids):
        if eid in index.index:
            out[i] = index.loc[eid, feat_cols].to_numpy(dtype=float)
    return out


def pairwise_rbf_similarity(A: np.ndarray, B: np.ndarray, lengthscale: float = 1.0) -> np.ndarray:
    """Return (nA, nB) RBF similarities."""
    A = np.asarray(A, dtype=float)
    B = np.asarray(B, dtype=float)
    a2 = np.sum(A**2, axis=1, keepdims=True)
    b2 = np.sum(B**2, axis=1, keepdims=True).T
    d2 = np.maximum(a2 + b2 - 2 * A @ B.T, 0.0)
    return np.exp(-0.5 * d2 / (lengthscale**2 + 1e-12))


def substrate_similarity_map(
    desc_by_id: Dict[str, np.ndarray],
    target_id: str,
    source_ids: Iterable[str],
    lengthscale: float = 1.0,
) -> Dict[str, float]:
    if target_id not in desc_by_id:
        return {s: 1.0 for s in source_ids}
    t = desc_by_id[target_id].reshape(1, -1)
    out = {}
    for s in source_ids:
        if s not in desc_by_id:
            out[s] = 0.0
            continue
        sim = pairwise_rbf_similarity(t, desc_by_id[s].reshape(1, -1), lengthscale=lengthscale)[0, 0]
        out[s] = float(sim)
    return out
