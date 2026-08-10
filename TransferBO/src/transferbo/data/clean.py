"""SMILES cleaning and plate-level deduplication."""

from __future__ import annotations

import pandas as pd


def clean_smiles(smiles: str) -> str | None:
    """Canonicalise SMILES with RDKit; return None if invalid."""
    try:
        from rdkit import Chem
    except ImportError as e:
        raise ImportError("rdkit is required for SMILES cleaning") from e

    if smiles is None or (isinstance(smiles, float) and pd.isna(smiles)):
        return None
    mol = Chem.MolFromSmiles(str(smiles))
    if mol is None:
        return None
    return Chem.MolToSmiles(mol)


def deduplicate_plate(
    df: pd.DataFrame,
    *,
    smiles_col: str = "smiles",
    response_col: str = "response",
    agg: str = "mean",
) -> pd.DataFrame:
    """Canonicalise SMILES, drop invalids, aggregate duplicate responses."""
    out = df.copy()
    out[smiles_col] = out[smiles_col].map(clean_smiles)
    out = out.dropna(subset=[smiles_col]).reset_index(drop=True)

    group_cols = [c for c in out.columns if c not in (response_col,)]
    # Prefer grouping by plate + smiles when present
    keys = [c for c in ("plate_id", smiles_col) if c in out.columns]
    if not keys:
        keys = [smiles_col]

    if agg == "mean":
        agg_map = {response_col: "mean"}
        keep = [c for c in out.columns if c not in keys and c != response_col]
        for c in keep:
            agg_map[c] = "first"
        out = out.groupby(keys, as_index=False).agg(agg_map)
    else:
        out = out.drop_duplicates(subset=keys, keep="first")

    return out.reset_index(drop=True)
