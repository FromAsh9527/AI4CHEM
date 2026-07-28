# -*- coding: utf-8 -*-
"""Morgan / ECFP 指纹核心。"""
from __future__ import annotations

import numpy as np
import pandas as pd
from rdkit.Chem.rdFingerprintGenerator import GetMorganGenerator

from generators.common import drop_all_nan_features, mol_from_smiles
from io_utils import ID_COL


def compute(
    molecules: pd.DataFrame,
    *,
    radius: int = 2,
    n_bits: int = 128,
    use_counts: bool = False,
):
    if ID_COL not in molecules.columns or "smiles" not in molecules.columns:
        raise ValueError("molecules 需含 molecule_id 与 smiles")
    gen = GetMorganGenerator(radius=radius, fpSize=n_bits)
    rows, failed = [], []
    for _, r in molecules.iterrows():
        mid, smi = str(r[ID_COL]), str(r["smiles"])
        mol = mol_from_smiles(smi)
        if mol is None:
            failed.append({ID_COL: mid, "smiles": smi, "reason": "invalid_smiles"})
            continue
        if use_counts:
            fp = gen.GetCountFingerprintAsNumPy(mol)
        else:
            fp = gen.GetFingerprintAsNumPy(mol)
        feat = {ID_COL: mid}
        feat.update({f"morgan_{i}": float(fp[i]) for i in range(len(fp))})
        rows.append(feat)
    desc = drop_all_nan_features(pd.DataFrame(rows))
    return desc, pd.DataFrame(failed)
