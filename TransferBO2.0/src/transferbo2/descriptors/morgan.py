"""Morgan fingerprints and chemical similarity helpers (RDKit)."""

from __future__ import annotations

from typing import Optional

import numpy as np

try:
    from rdkit import Chem
    from rdkit.Chem import AllChem
    from rdkit.DataStructs import ConvertToNumpyArray
except ImportError:  # pragma: no cover
    Chem = None  # type: ignore
    AllChem = None  # type: ignore
    ConvertToNumpyArray = None  # type: ignore


def require_rdkit() -> None:
    if Chem is None or AllChem is None or ConvertToNumpyArray is None:
        raise ImportError("RDKit is required for Morgan descriptors. pip install rdkit")


def morgan_bit_vector(smiles: str, *, n_bits: int = 2048, radius: int = 2) -> np.ndarray:
    """Return dense 0/1 Morgan fingerprint; zeros if SMILES invalid/empty."""
    require_rdkit()
    s = (smiles or "").strip()
    out = np.zeros(n_bits, dtype=float)
    if not s:
        return out
    mol = Chem.MolFromSmiles(s)
    if mol is None:
        return out
    # Prefer MorganGenerator (RDKit ≥2022); fall back to deprecated helper.
    try:
        from rdkit.Chem import rdFingerprintGenerator

        gen = rdFingerprintGenerator.GetMorganGenerator(radius=radius, fpSize=n_bits)
        fp = gen.GetFingerprint(mol)
    except Exception:
        fp = AllChem.GetMorganFingerprintAsBitVect(mol, radius, nBits=n_bits)
    arr = np.zeros((n_bits,), dtype=float)
    ConvertToNumpyArray(fp, arr)
    return arr


def morgan_pair_vector(
    smiles_a: str,
    smiles_b: str,
    *,
    n_bits: int = 2048,
    radius: int = 2,
    combine: str = "or",
) -> np.ndarray:
    """Fingerprint a substrate pair (e.g. electrophile + nucleophile)."""
    fa = morgan_bit_vector(smiles_a, n_bits=n_bits, radius=radius)
    fb = morgan_bit_vector(smiles_b, n_bits=n_bits, radius=radius)
    if combine == "concat":
        return np.concatenate([fa, fb])
    if combine == "sum":
        return fa + fb
    return np.clip(fa + fb, 0.0, 1.0)


def tanimoto(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, dtype=float).ravel()
    b = np.asarray(b, dtype=float).ravel()
    inter = float(np.minimum(a, b).sum())
    union = float(np.maximum(a, b).sum())
    if union <= 0:
        return 0.0
    return inter / union


def component_morgan_or(
    *smiles_parts: Optional[str],
    n_bits: int = 2048,
    radius: int = 2,
) -> np.ndarray:
    acc = np.zeros(n_bits, dtype=float)
    for s in smiles_parts:
        if s is None or (isinstance(s, float) and np.isnan(s)):
            continue
        text = str(s).strip()
        if not text or text.lower() == "nan" or text.upper() == "NA":
            continue
        acc = np.clip(acc + morgan_bit_vector(text, n_bits=n_bits, radius=radius), 0.0, 1.0)
    return acc
