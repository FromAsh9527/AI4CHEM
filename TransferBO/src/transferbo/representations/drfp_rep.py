"""Optional DRFP reaction fingerprints (requires `pip install drfp`)."""

from __future__ import annotations

from typing import Sequence

import numpy as np

from .base import Representation


class DRFPEncoder(Representation):
    """Encode reaction SMILES with DRFP; falls back to molecule SMILES if needed."""

    name = "drfp"

    def __init__(self, n_bits: int = 2048) -> None:
        self.n_bits = n_bits

    def fit(self, smiles: Sequence[str]) -> "DRFPEncoder":
        return self

    def transform(self, smiles: Sequence[str]) -> np.ndarray:
        try:
            from drfp import DrfpEncoder
        except ImportError as e:
            raise ImportError(
                "DRFP representation requires the `drfp` package: pip install drfp"
            ) from e

        # DRFP expects reaction SMILES; for additive-only plates we pass mol SMILES
        # as a degenerate reaction — callers should supply true reaction SMILES when available.
        fps = DrfpEncoder.encode(list(map(str, smiles)), n_folded_length=self.n_bits)
        return np.asarray(fps, dtype=np.float64)
