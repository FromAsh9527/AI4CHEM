# -*- coding: utf-8 -*-
"""各生成器共用：路径、分子解析。"""
from __future__ import annotations

import sys
from pathlib import Path

from rdkit import Chem

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from io_utils import ID_COL  # noqa: E402


def mol_from_smiles(smi: str):
    mol = Chem.MolFromSmiles(str(smi))
    if mol is None:
        return None
    try:
        Chem.SanitizeMol(mol)
    except Exception:
        return None
    return mol


def drop_all_nan_features(df, id_col: str = ID_COL):
    import pandas as pd

    if df is None or df.empty:
        return df
    feat = [c for c in df.columns if c != id_col]
    keep = [c for c in feat if df[c].notna().any()]
    return df[[id_col] + keep]
