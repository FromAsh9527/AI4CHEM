# -*- coding: utf-8 -*-
"""MACCS keys 指纹（RDKit，166 bit，常用前 1–166；bit0 不用）。"""
from __future__ import annotations

import numpy as np
import pandas as pd
from rdkit.Chem import MACCSkeys

from generators.common import drop_all_nan_features, mol_from_smiles
from io_utils import ID_COL

# RDKit MACCS 长度为 167；第 0 位恒为 0，导出时用 maccs_1 … maccs_166
N_BITS = 166


def compute(molecules: pd.DataFrame):
    if ID_COL not in molecules.columns or "smiles" not in molecules.columns:
        raise ValueError("molecules 需含 molecule_id 与 smiles")
    rows, failed = [], []
    for _, r in molecules.iterrows():
        mid, smi = str(r[ID_COL]), str(r["smiles"])
        mol = mol_from_smiles(smi)
        if mol is None:
            failed.append({ID_COL: mid, "smiles": smi, "reason": "invalid_smiles"})
            continue
        fp = MACCSkeys.GenMACCSKeys(mol)
        arr = np.zeros(N_BITS, dtype=float)
        for i in range(1, N_BITS + 1):
            arr[i - 1] = float(fp.GetBit(i))
        feat = {ID_COL: mid}
        feat.update({f"maccs_{i}": arr[i - 1] for i in range(1, N_BITS + 1)})
        rows.append(feat)
    desc = drop_all_nan_features(pd.DataFrame(rows))
    return desc, pd.DataFrame(failed)
