# -*- coding: utf-8 -*-
"""把建议实验的 PENDING 目标写成实测数值。"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from workspace import (
    factor_columns,
    load_config,
    load_reaction,
    save_reaction,
    suggested_mask,
)


def pending_suggestions(ws: Path, cfg: dict | None = None) -> pd.DataFrame:
    cfg = cfg or load_config(ws)
    df = load_reaction(ws, cfg)
    if df.empty:
        return df
    objectives = list(cfg.get("objectives") or [])
    mask = suggested_mask(df)
    if not mask.any():
        # 若尚无 priority，但目标全是 PENDING，则展示全部 PENDING 行供回填
        if objectives and all(o in df.columns for o in objectives):
            pending = pd.Series([True] * len(df), index=df.index)
            for o in objectives:
                pending &= df[o].astype(str).str.contains("PENDING", case=False, na=False)
            mask = pending
    cols = factor_columns(df, objectives) + [o for o in objectives if o in df.columns]
    if "priority" in df.columns:
        cols = ["priority"] + cols
    out = df.loc[mask, cols].copy()
    out.insert(0, "_row", out.index.astype(int))
    return out.reset_index(drop=True)


def apply_backfill(ws: Path, edits: pd.DataFrame, cfg: dict | None = None) -> int:
    """edits 需含 `_row` 与各目标列；返回成功写入条数。"""
    cfg = cfg or load_config(ws)
    df = load_reaction(ws, cfg)
    if df.empty:
        raise ValueError("reaction.csv 为空")
    objectives = list(cfg.get("objectives") or [])
    if edits is None or edits.empty:
        raise ValueError("回填表为空：请填写数值或上传含 `_row` 与目标列的 CSV")
    if "_row" not in edits.columns:
        raise ValueError("回填表缺少 `_row` 列（请用「下载回填模板」或按行填写）")

    n = 0
    for _, row in edits.iterrows():
        idx = int(row["_row"])
        if idx not in df.index:
            continue
        ok = True
        values = {}
        for obj in objectives:
            if obj not in row.index:
                ok = False
                break
            raw = row[obj]
            if pd.isna(raw) or str(raw).strip().upper() == "PENDING" or str(raw).strip() == "":
                ok = False
                break
            try:
                values[obj] = float(raw)
            except (TypeError, ValueError) as e:
                raise ValueError(f"行 {idx} 目标 `{obj}` 不是数值: {raw}") from e
        if not ok:
            continue
        for obj, val in values.items():
            df.at[idx, obj] = val
        n += 1

    save_reaction(ws, df, cfg)
    return n
