"""Precomputed xTB descriptors loaded from a SMILES-keyed table (BOUSE pipeline)."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd

from .base import Representation

_FEAT_PREFIX = "xtb_"


class XTBTableEncoder(Representation):
    """Lookup continuous xTB features from a CSV produced by BOUSE descriptors."""

    name = "xtb"

    def __init__(
        self,
        table_path: str | Path,
        *,
        smiles_col: str = "smiles",
        standardize: bool = True,
        fill_value: float = 0.0,
    ) -> None:
        self.table_path = Path(table_path)
        self.smiles_col = smiles_col
        self.standardize = bool(standardize)
        self.fill_value = float(fill_value)
        self._feat_cols: list[str] = []
        self._lookup: dict[str, np.ndarray] = {}
        self._mean: np.ndarray | None = None
        self._std: np.ndarray | None = None
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        if not self.table_path.is_file():
            raise FileNotFoundError(
                f"xTB table not found: {self.table_path}. "
                "Run: python scripts/prepare_chaos_xtb.py"
            )
        df = pd.read_csv(self.table_path)
        if self.smiles_col not in df.columns:
            raise ValueError(f"xTB table missing {self.smiles_col!r}")
        feat_cols = [c for c in df.columns if c.startswith(_FEAT_PREFIX)]
        if not feat_cols:
            feat_cols = [
                c
                for c in df.columns
                if c not in {self.smiles_col, "molecule_id", "additive_id"}
                and pd.api.types.is_numeric_dtype(df[c])
            ]
        if not feat_cols:
            # last resort: all non-key columns coerced later
            feat_cols = [
                c
                for c in df.columns
                if c not in {self.smiles_col, "molecule_id", "additive_id"}
            ]
        if not feat_cols:
            raise ValueError("No feature columns in descriptor table")
        self._feat_cols = feat_cols
        for _, row in df.iterrows():
            smi = str(row[self.smiles_col])
            vec = pd.to_numeric(row[feat_cols], errors="coerce").to_numpy(dtype=np.float64)
            vec = np.nan_to_num(vec, nan=self.fill_value, posinf=self.fill_value, neginf=self.fill_value)
            self._lookup[smi] = vec
        self._loaded = True

    def fit(self, smiles: Sequence[str]) -> "XTBTableEncoder":
        self._ensure_loaded()
        if not self.standardize:
            self._mean = None
            self._std = None
            return self
        mats = []
        for s in smiles:
            v = self._lookup.get(str(s))
            if v is not None:
                mats.append(v)
        if not mats:
            raise ValueError("No xTB rows found for fit smiles")
        X = np.vstack(mats)
        self._mean = X.mean(axis=0)
        self._std = X.std(axis=0)
        self._std = np.where(self._std < 1e-12, 1.0, self._std)
        return self

    def transform(self, smiles: Sequence[str]) -> np.ndarray:
        self._ensure_loaded()
        n = len(smiles)
        d = len(self._feat_cols)
        X = np.full((n, d), self.fill_value, dtype=np.float64)
        missing = 0
        for i, s in enumerate(smiles):
            v = self._lookup.get(str(s))
            if v is None:
                missing += 1
                continue
            X[i] = v
        if missing:
            # keep going but make failures visible in logs via stderr once
            import sys

            print(
                f"[xtb] warning: {missing}/{n} SMILES missing from table {self.table_path.name}",
                file=sys.stderr,
            )
        if self.standardize and self._mean is not None and self._std is not None:
            X = (X - self._mean) / self._std
        return X
