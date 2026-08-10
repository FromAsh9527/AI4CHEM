"""Retrospective oracle: looking up true labels stands in for wet experiments."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class PlateOracle:
    """Hide target-plate labels; reveal them only when 'queried'."""

    plate: pd.DataFrame
    response_col: str = "response"
    _revealed: set[int] = field(default_factory=set, init=False)

    def __post_init__(self) -> None:
        self.plate = self.plate.reset_index(drop=True)
        self.y_true = self.plate[self.response_col].to_numpy(dtype=float)
        self.n = len(self.plate)

    @property
    def smiles(self) -> list[str]:
        return self.plate["smiles"].astype(str).tolist()

    @property
    def additive_ids(self) -> list:
        if "additive_id" in self.plate.columns:
            return self.plate["additive_id"].tolist()
        return list(range(self.n))

    def query(self, indices: list[int] | np.ndarray) -> np.ndarray:
        indices = np.asarray(indices, dtype=int)
        for i in indices:
            if i < 0 or i >= self.n:
                raise IndexError(f"Index {i} out of range [0, {self.n})")
            self._revealed.add(int(i))
        return self.y_true[indices].copy()

    def revealed_mask(self) -> np.ndarray:
        mask = np.zeros(self.n, dtype=bool)
        mask[list(self._revealed)] = True
        return mask

    def unrevealed_indices(self) -> np.ndarray:
        return np.where(~self.revealed_mask())[0]

    def top_frac_threshold(self, frac: float = 0.05) -> float:
        """Response threshold for top-`frac` of the full plate (maximisation)."""
        k = max(1, int(np.ceil(self.n * frac)))
        return float(np.partition(self.y_true, -k)[-k])

    def global_best(self) -> float:
        return float(np.max(self.y_true))
