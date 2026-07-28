# -*- coding: utf-8 -*-
"""L2：已有描述符表清洗。"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from io_utils import ID_COL, read_table

DEFAULT_DROP_KEYWORDS = (
    "file_name",
    "entry",
    "vibration",
    "correlation",
    "Rydberg",
    "correction",
    "atom_number",
    "E-M_angle",
    "MEAN",
    "MAXG",
    "STDEV",
    "log_file",
    "log_name",
    "stoichiometry",
    "convergence",
)


def _guess_id_column(df: pd.DataFrame, id_col: str | None) -> str:
    if id_col:
        if id_col not in df.columns:
            raise ValueError(f"找不到 id 列: {id_col}")
        return id_col
    if ID_COL in df.columns:
        return ID_COL
    smiles_like = [c for c in df.columns if "SMILES" in str(c) or str(c).lower() == "smiles"]
    if smiles_like:
        return smiles_like[0]
    raise ValueError("无法推断 id 列，请指定 id_col")


def clean_dataframe(
    raw: pd.DataFrame,
    *,
    id_col: str | None = None,
    drop_keywords: tuple[str, ...] = DEFAULT_DROP_KEYWORDS,
    max_features: int | None = None,
    drop_na_rows: bool = False,
) -> tuple[pd.DataFrame, dict]:
    src_id = _guess_id_column(raw, id_col)
    drop_kw = tuple(k.lower() for k in drop_keywords)
    feat_cols: list[str] = []
    for c in raw.columns:
        if c == src_id:
            continue
        cl = str(c).lower()
        if any(k in cl for k in drop_kw):
            continue
        if not pd.api.types.is_numeric_dtype(raw[c]):
            continue
        if raw[c].nunique(dropna=False) <= 1:
            continue
        feat_cols.append(c)

    info = {
        "n_rows_raw": int(len(raw)),
        "n_cols_raw": int(raw.shape[1]),
        "id_source": src_id,
        "n_features_before_cap": len(feat_cols),
    }
    if max_features is not None and len(feat_cols) > max_features:
        var = raw[feat_cols].var(numeric_only=True).sort_values(ascending=False)
        feat_cols = list(var.head(int(max_features)).index)
        info["max_features"] = int(max_features)

    out = pd.DataFrame()
    out[ID_COL] = raw[src_id].astype(str).str.strip()
    for c in feat_cols:
        out[c] = pd.to_numeric(raw[c], errors="coerce")
    out = out.replace([np.inf, -np.inf], np.nan)
    if drop_na_rows:
        out = out.dropna()
    else:
        out = out[out[ID_COL].str.len() > 0]
        feat = [c for c in out.columns if c != ID_COL]
        if feat:
            out = out.dropna(how="all", subset=feat)
    out = out.drop_duplicates(subset=[ID_COL], keep="first").reset_index(drop=True)
    info["n_rows_out"] = int(len(out))
    info["n_features_out"] = int(out.shape[1] - 1)
    return out, info


def clean_descriptor_table(path: Path, **kwargs) -> tuple[pd.DataFrame, dict]:
    return clean_dataframe(read_table(path), **kwargs)
