# -*- coding: utf-8 -*-
"""读写约定：输入分子表 / 输出描述符 CSV。"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

ID_COL = "molecule_id"
SMILES_CANDIDATES = ("smiles", "SMILES", "Smiles", "canonical_smiles")


def resolve_smiles_column(df: pd.DataFrame, smiles_col: str | None = None) -> str:
    if smiles_col:
        if smiles_col not in df.columns:
            raise ValueError(f"找不到 SMILES 列: {smiles_col}")
        return smiles_col
    for c in SMILES_CANDIDATES:
        if c in df.columns:
            return c
    raise ValueError(f"表中无 SMILES 列，尝试过: {SMILES_CANDIDATES}")


def read_table(path: Path) -> pd.DataFrame:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.suffix.lower() in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    return pd.read_csv(path)


def molecules_from_dataframe(
    df: pd.DataFrame,
    *,
    id_col: str | None = None,
    smiles_col: str | None = None,
) -> pd.DataFrame:
    smi = resolve_smiles_column(df, smiles_col)
    if id_col and id_col in df.columns:
        mid = id_col
    elif ID_COL in df.columns:
        mid = ID_COL
    else:
        mid = None

    out = pd.DataFrame()
    if mid is None:
        out[ID_COL] = df[smi].astype(str).str.strip()
    else:
        out[ID_COL] = df[mid].astype(str).str.strip()
    out["smiles"] = df[smi].astype(str).str.strip()
    out = out.dropna(subset=["smiles"])
    out = out[out["smiles"].str.len() > 0]
    out = out.drop_duplicates(subset=[ID_COL], keep="first")
    return out.reset_index(drop=True)


def load_molecule_table(
    path: Path,
    *,
    id_col: str | None = None,
    smiles_col: str | None = None,
) -> pd.DataFrame:
    return molecules_from_dataframe(read_table(path), id_col=id_col, smiles_col=smiles_col)


def write_descriptor_csv(df: pd.DataFrame, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if ID_COL not in df.columns:
        raise ValueError(f"输出缺少 {ID_COL}")
    cols = [ID_COL] + [c for c in df.columns if c != ID_COL]
    df[cols].to_csv(path, index=False)
    return path


def validate_descriptor_frame(df: pd.DataFrame) -> None:
    """校验是否符合 BOUSE 交接契约（见 ../CONTRACT.md）。"""
    if ID_COL not in df.columns:
        raise ValueError(f"缺少 {ID_COL}")
    if df[ID_COL].isna().any() or df[ID_COL].astype(str).str.strip().eq("").any():
        raise ValueError(f"{ID_COL} 存在空值")
    if df[ID_COL].astype(str).str.strip().duplicated().any():
        raise ValueError(f"{ID_COL} 存在重复")
    feat = [c for c in df.columns if c != ID_COL]
    if not feat:
        raise ValueError("没有特征列")
    for c in feat:
        if not pd.api.types.is_numeric_dtype(df[c]):
            raise ValueError(f"特征列非数值: {c}")


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")
