# -*- coding: utf-8 -*-
"""实验结果回填合并。"""
from __future__ import annotations

import pandas as pd

from factors import FactorSpec, factor_keys


def measurement_template(recommendations: pd.DataFrame, target_col: str) -> pd.DataFrame:
    cols = [c for c in recommendations.columns if c != "rank"]
    out = recommendations[cols].copy()
    out[target_col] = pd.NA
    return out


def merge_results(
    history: pd.DataFrame,
    new_df: pd.DataFrame,
    factors: list[FactorSpec],
    target_col: str,
    replace: bool = False,
) -> pd.DataFrame:
    keys = factor_keys(factors)
    required = keys + [target_col]
    for c in required:
        if c not in new_df.columns:
            raise ValueError(f"回填表缺少列: {c}")

    incoming = new_df[required].copy()
    for k in keys:
        incoming[k] = incoming[k].astype(str)
    incoming[target_col] = pd.to_numeric(incoming[target_col], errors="coerce")
    if incoming[target_col].isna().any():
        raise ValueError(f"目标列 {target_col} 存在无法解析的数值")

    if history is None or history.empty:
        return incoming.reset_index(drop=True)

    hist = history.copy()
    for k in keys:
        if k not in hist.columns:
            raise ValueError(f"历史表缺少因子列: {k}")
        hist[k] = hist[k].astype(str)

    if not replace:
        return pd.concat([hist, incoming], ignore_index=True)

    hist["_key"] = list(zip(*[hist[k] for k in keys]))
    incoming["_key"] = list(zip(*[incoming[k] for k in keys]))
    overwrite = set(incoming["_key"])
    kept = hist[~hist["_key"].isin(overwrite)].drop(columns=["_key"])
    incoming = incoming.drop(columns=["_key"])
    return pd.concat([kept, incoming], ignore_index=True)
