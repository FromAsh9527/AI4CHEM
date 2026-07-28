# -*- coding: utf-8 -*-
"""RDKit 2D 描述符核心。"""
from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd
from rdkit.Chem import Descriptors

from generators.common import drop_all_nan_features, mol_from_smiles
from io_utils import ID_COL

DEFAULT_RDKIT_NAMES: tuple[str, ...] = (
    "MolWt",
    "HeavyAtomMolWt",
    "ExactMolWt",
    "NumValenceElectrons",
    "NumRadicalElectrons",
    "MaxPartialCharge",
    "MinPartialCharge",
    "MaxAbsPartialCharge",
    "MinAbsPartialCharge",
    "FpDensityMorgan1",
    "FpDensityMorgan2",
    "FpDensityMorgan3",
    "BalabanJ",
    "BertzCT",
    "Chi0",
    "Chi0n",
    "Chi0v",
    "Chi1",
    "Chi1n",
    "Chi1v",
    "Chi2n",
    "Chi2v",
    "Chi3n",
    "Chi3v",
    "Chi4n",
    "Chi4v",
    "HallKierAlpha",
    "Kappa1",
    "Kappa2",
    "Kappa3",
    "LabuteASA",
    "PEOE_VSA1",
    "PEOE_VSA2",
    "PEOE_VSA3",
    "PEOE_VSA4",
    "PEOE_VSA5",
    "PEOE_VSA6",
    "SMR_VSA1",
    "SMR_VSA2",
    "SMR_VSA3",
    "SMR_VSA4",
    "SMR_VSA5",
    "SlogP_VSA1",
    "SlogP_VSA2",
    "SlogP_VSA3",
    "SlogP_VSA4",
    "SlogP_VSA5",
    "TPSA",
    "EState_VSA1",
    "EState_VSA2",
    "EState_VSA3",
    "EState_VSA4",
    "EState_VSA5",
    "VSA_EState1",
    "VSA_EState2",
    "VSA_EState3",
    "VSA_EState4",
    "VSA_EState5",
    "FractionCSP3",
    "HeavyAtomCount",
    "NHOHCount",
    "NOCount",
    "NumAliphaticCarbocycles",
    "NumAliphaticHeterocycles",
    "NumAliphaticRings",
    "NumAromaticCarbocycles",
    "NumAromaticHeterocycles",
    "NumAromaticRings",
    "NumHAcceptors",
    "NumHDonors",
    "NumHeteroatoms",
    "NumRotatableBonds",
    "NumSaturatedCarbocycles",
    "NumSaturatedHeterocycles",
    "NumSaturatedRings",
    "RingCount",
    "MolLogP",
    "MolMR",
)


def _descriptor_functions(names: Iterable[str]):
    avail = {name: fn for name, fn in Descriptors.descList}
    out = []
    missing = []
    for name in names:
        if name in avail:
            out.append((name, avail[name]))
        else:
            missing.append(name)
    if missing:
        raise ValueError(f"RDKit 不支持这些描述符: {missing}")
    return out


def compute(molecules: pd.DataFrame, *, descriptor_names: Iterable[str] | None = None):
    if ID_COL not in molecules.columns or "smiles" not in molecules.columns:
        raise ValueError("molecules 需含 molecule_id 与 smiles")
    names = tuple(descriptor_names) if descriptor_names is not None else DEFAULT_RDKIT_NAMES
    funcs = _descriptor_functions(names)
    rows, failed = [], []
    for _, r in molecules.iterrows():
        mid, smi = str(r[ID_COL]), str(r["smiles"])
        mol = mol_from_smiles(smi)
        if mol is None:
            failed.append({ID_COL: mid, "smiles": smi, "reason": "invalid_smiles"})
            continue
        feat = {ID_COL: mid}
        for name, fn in funcs:
            try:
                v = fn(mol)
                feat[f"rdkit_{name}"] = float(v) if v is not None and np.isfinite(float(v)) else np.nan
            except Exception:
                feat[f"rdkit_{name}"] = np.nan
        rows.append(feat)
    desc = drop_all_nan_features(pd.DataFrame(rows))
    return desc, pd.DataFrame(failed)
