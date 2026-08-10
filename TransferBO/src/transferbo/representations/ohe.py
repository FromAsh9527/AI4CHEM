"""One-hot encoding over additive identity (negative control for transfer)."""

from __future__ import annotations

from typing import Sequence

import numpy as np

from .base import Representation


class OneHotEncoder(Representation):
    """OHE over the *union* of identities seen at fit time.

    Across plates with disjoint additive IDs / SMILES vocabularies, shared
    support is near-zero — expected to give little/no positive transfer.
    """

    name = "ohe"

    def __init__(self, key: str = "smiles") -> None:
        self.key = key
        self.vocab_: dict[str, int] = {}

    def fit(self, smiles: Sequence[str]) -> "OneHotEncoder":
        self.vocab_ = {s: i for i, s in enumerate(sorted(set(map(str, smiles))))}
        return self

    def transform(self, smiles: Sequence[str]) -> np.ndarray:
        if not self.vocab_:
            raise RuntimeError("OneHotEncoder must be fit before transform")
        n = len(self.vocab_)
        X = np.zeros((len(smiles), n), dtype=np.float64)
        for row, s in enumerate(smiles):
            idx = self.vocab_.get(str(s))
            if idx is not None:
                X[row, idx] = 1.0
        return X
