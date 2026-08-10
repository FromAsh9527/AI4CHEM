"""Base representation interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Sequence

import numpy as np


class Representation(ABC):
    name: str = "base"

    @abstractmethod
    def fit(self, smiles: Sequence[str]) -> "Representation":
        ...

    @abstractmethod
    def transform(self, smiles: Sequence[str]) -> np.ndarray:
        ...

    def fit_transform(self, smiles: Sequence[str]) -> np.ndarray:
        return self.fit(smiles).transform(smiles)
