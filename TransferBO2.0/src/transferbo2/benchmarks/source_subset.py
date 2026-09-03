"""P1+P2: pooled top-k list helpers over source subsets (offline)."""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Sequence

import numpy as np
import pandas as pd

from transferbo2.descriptors.features import substrate_similarity_map

K_DEFAULT = 5


def load_yield_matrix(csv_path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    return df.pivot_table(
        index="condition_id", columns="substrate_id", values="yield", aggfunc="mean"
    )


def jaccard(a: Sequence, b: Sequence) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def sample_source_subset(
    sources: Sequence[str],
    n_s: int | str,
    *,
    subset_seed: int,
    target: str,
) -> list[str]:
    src = list(sources)
    if not src:
        return []
    if n_s == "all" or (isinstance(n_s, str) and str(n_s).lower() == "all"):
        return src
    n = min(int(n_s), len(src))
    rng = np.random.default_rng(subset_seed + hash(target) % 10_007)
    pick = rng.choice(src, size=n, replace=False)
    return [str(s) for s in pick]


def pooled_topk_ids(
    long_df: pd.DataFrame,
    target: str,
    sources: Sequence[str],
    *,
    k: int = K_DEFAULT,
    mat: Optional[pd.DataFrame] = None,
) -> list[str]:
    """Pool mean yield over sources; return top-k condition IDs present on target."""
    if mat is None:
        sub = long_df[long_df["substrate_id"].isin(sources)]
        rank = sub.groupby("condition_id")["yield"].mean().sort_values(ascending=False)
    else:
        cols = [c for c in sources if c in mat.columns]
        if not cols:
            return []
        rank = mat[cols].mean(axis=1).sort_values(ascending=False)
    if target not in (mat.columns if mat is not None else long_df["substrate_id"].unique()):
        tgt_col = target
    else:
        tgt_col = target
    if mat is not None:
        valid = mat[tgt_col].dropna().index
    else:
        valid = set(long_df.loc[long_df["substrate_id"] == target, "condition_id"])
    out = []
    for cid in rank.index:
        if cid in valid:
            out.append(str(cid))
        if len(out) >= k:
            break
    return out


def single_source_topk_ids(
    long_df: pd.DataFrame,
    source: str,
    target: str,
    *,
    k: int = K_DEFAULT,
    mat: Optional[pd.DataFrame] = None,
) -> list[str]:
    if mat is not None and source in mat.columns:
        rank = mat[source].sort_values(ascending=False)
        valid = mat[target].dropna().index if target in mat.columns else []
    else:
        sub = long_df[long_df["substrate_id"] == source]
        rank = sub.groupby("condition_id")["yield"].mean().sort_values(ascending=False)
        valid = set(long_df.loc[long_df["substrate_id"] == target, "condition_id"])
    out = []
    for cid in rank.index:
        if cid in valid:
            out.append(str(cid))
        if len(out) >= k:
            break
    return out


def random_source_topk_ids(
    long_df: pd.DataFrame,
    target: str,
    sources: Sequence[str],
    *,
    k: int = K_DEFAULT,
    subset_seed: int,
    mat: Optional[pd.DataFrame] = None,
) -> tuple[list[str], str]:
    if not sources:
        return [], ""
    rng = np.random.default_rng(subset_seed + 90_001 + hash(target) % 10_007)
    src = str(rng.choice(list(sources)))
    return single_source_topk_ids(long_df, src, target, k=k, mat=mat), src


def nearest_source_topk_ids(
    long_df: pd.DataFrame,
    target: str,
    sources: Sequence[str],
    desc_by_id: Dict[str, np.ndarray],
    *,
    k: int = K_DEFAULT,
    mat: Optional[pd.DataFrame] = None,
    metric: str = "tanimoto",
) -> tuple[list[str], str, float]:
    if not sources:
        return [], "", float("nan")
    sims = substrate_similarity_map(desc_by_id, target, list(sources), metric=metric)
    if not sims:
        return [], "", float("nan")
    src = max(sims, key=sims.get)
    ids = single_source_topk_ids(long_df, src, target, k=k, mat=mat)
    return ids, src, float(sims[src])


def source_support(long_df: pd.DataFrame, sources: Sequence[str], cids: Sequence[str]) -> dict[str, int]:
    sub = long_df[long_df["substrate_id"].isin(sources)]
    counts = sub.groupby("condition_id")["substrate_id"].nunique()
    return {str(c): int(counts.get(c, 0)) for c in cids}


def init_metrics(mat: pd.DataFrame, target: str, cids: Sequence[str]) -> dict[str, float]:
    if target not in mat.columns or not cids:
        return {"init_best": float("nan"), "init_mean": float("nan"), "init_max": float("nan")}
    y = mat[target].reindex(list(cids)).dropna()
    if y.empty:
        return {"init_best": float("nan"), "init_mean": float("nan"), "init_max": float("nan")}
    vals = y.to_numpy(dtype=float)
    return {
        "init_best": float(np.max(vals)),
        "init_mean": float(np.mean(vals)),
        "init_max": float(np.max(vals)),
    }
