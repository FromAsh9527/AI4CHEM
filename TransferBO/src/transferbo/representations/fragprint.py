"""Fragprints: Morgan + RDKit path fingerprints (concatenated bit vectors)."""

from __future__ import annotations

from typing import Sequence

import numpy as np

from .base import Representation
from .morgan import MorganFingerprint


class FragprintEncoder(Representation):
    """Simple fragprint stand-in: Morgan || RDKit fingerprint."""

    name = "fragprint"

    def __init__(self, radius: int = 2, n_bits: int = 2048) -> None:
        self.radius = radius
        self.n_bits = n_bits
        self._morgan = MorganFingerprint(radius=radius, n_bits=n_bits)

    def fit(self, smiles: Sequence[str]) -> "FragprintEncoder":
        self._morgan.fit(smiles)
        return self

    def transform(self, smiles: Sequence[str]) -> np.ndarray:
        from rdkit import Chem
        from rdkit.Chem import RDKFingerprint

        morgan = self._morgan.transform(smiles)
        rdkit_fp = np.zeros((len(smiles), self.n_bits), dtype=np.float64)
        for i, s in enumerate(smiles):
            mol = Chem.MolFromSmiles(str(s))
            if mol is None:
                continue
            bv = RDKFingerprint(mol, fpSize=self.n_bits)
            rdkit_fp[i] = np.array(bv, dtype=np.float64)
        return np.hstack([morgan, rdkit_fp])
