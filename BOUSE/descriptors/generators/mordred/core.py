# -*- coding: utf-8 -*-
"""Mordred 2D 描述符（需 pip/conda 安装 mordred）。"""
from __future__ import annotations

import numpy as np
import pandas as pd

from generators.common import drop_all_nan_features, mol_from_smiles
from io_utils import ID_COL


def _patch_numpy_for_mordred() -> None:
    """旧版 mordred 使用已移除的 numpy.product（NumPy 2+）。"""
    if not hasattr(np, "product"):
        np.product = np.prod  # type: ignore[attr-defined]


def _require_mordred():
    _patch_numpy_for_mordred()
    try:
        from mordred import Calculator, descriptors  # type: ignore
    except ImportError as e:
        raise ImportError(
            "未安装可用的 mordred。可试: pip install mordred\n"
            "或社区维护版: pip install mordredcommunity\n"
            "若仍失败，请先用 rdkit_2d / maccs。"
        ) from e
    return Calculator, descriptors


def _to_float(v) -> float:
    try:
        x = float(v)
        if np.isfinite(x):
            return x
    except Exception:
        pass
    return float("nan")


def compute(molecules: pd.DataFrame, *, ignore_3D: bool = True):
    """
    SMILES → Mordred 描述符表。

    Parameters
    ----------
    ignore_3D :
        True 时只算 2D（推荐；无需构象）。
    """
    if ID_COL not in molecules.columns or "smiles" not in molecules.columns:
        raise ValueError("molecules 需含 molecule_id 与 smiles")

    Calculator, descriptors = _require_mordred()
    calc = Calculator(descriptors, ignore_3D=ignore_3D)
    feat_names = [str(d) for d in calc.descriptors]

    rows, failed = [], []
    # 单进程：Windows spawn 子进程不会带上 numpy.product 补丁
    for _, r in molecules.iterrows():
        mid, smi = str(r[ID_COL]), str(r["smiles"])
        mol = mol_from_smiles(smi)
        if mol is None:
            failed.append({ID_COL: mid, "smiles": smi, "reason": "invalid_smiles"})
            continue
        try:
            values = calc(mol)
            feat = {ID_COL: mid}
            feat.update({name: _to_float(v) for name, v in zip(feat_names, values)})
            rows.append(feat)
        except Exception as e:
            failed.append({ID_COL: mid, "smiles": smi, "reason": f"mordred:{e}"})

    if not rows:
        return pd.DataFrame(), pd.DataFrame(failed)

    desc = drop_all_nan_features(pd.DataFrame(rows))
    feat = [c for c in desc.columns if c != ID_COL]
    keep = [c for c in feat if desc[c].notna().any() and pd.api.types.is_numeric_dtype(desc[c])]
    desc = desc[[ID_COL] + keep]
    return desc, pd.DataFrame(failed)
