"""Morgan / ECFP fingerprints via RDKit."""

from __future__ import annotations

from typing import Sequence

import numpy as np

from .base import Representation


class MorganFingerprint(Representation):
    """ECFP for single-molecule SMILES, or '||'-joined multi-component conditions.

    EDBO condition keys are ligand||base||solvent (or ||additive). Each component
    is fingerprinted and concatenated so substrates never enter X when absent
    from the key. Single-molecule CHAOS additives are unchanged (no '||').
    """

    name = "morgan"

    def __init__(self, radius: int = 2, n_bits: int = 2048) -> None:
        self.radius = radius
        self.n_bits = n_bits
        self._n_parts: int | None = None

    def fit(self, smiles: Sequence[str]) -> "MorganFingerprint":
        parts = [max(1, str(s).count("||") + 1) for s in smiles]
        self._n_parts = max(parts) if parts else 1
        return self

    def _fp_one(self, smi: str) -> np.ndarray:
        from rdkit import Chem
        from rdkit.Chem import AllChem
        from rdkit.DataStructs import ConvertToNumpyArray

        out = np.zeros((self.n_bits,), dtype=np.float64)
        mol = Chem.MolFromSmiles(str(smi))
        if mol is None:
            return out
        try:
            from rdkit.Chem import rdFingerprintGenerator

            gen = rdFingerprintGenerator.GetMorganGenerator(
                radius=self.radius, fpSize=self.n_bits
            )
            return gen.GetFingerprintAsNumPy(mol).astype(np.float64)
        except Exception:
            bv = AllChem.GetMorganFingerprintAsBitVect(mol, self.radius, nBits=self.n_bits)
            ConvertToNumpyArray(bv, out)
            return out

    def transform(self, smiles: Sequence[str]) -> np.ndarray:
        n_parts = self._n_parts or max((str(s).count("||") + 1 for s in smiles), default=1)
        dim = self.n_bits * n_parts
        X = np.zeros((len(smiles), dim), dtype=np.float64)
        for i, s in enumerate(smiles):
            comps = [c for c in str(s).split("||") if c != ""]
            if not comps:
                comps = [str(s)]
            for j, comp in enumerate(comps[:n_parts]):
                X[i, j * self.n_bits : (j + 1) * self.n_bits] = self._fp_one(comp)
        return X
