"""Offline oracle for sequential BO replay on a target substrate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Sequence

import numpy as np
import pandas as pd


CONDITION_COLS = [
    "catalyst",
    "ligand",
    "base",
    "solvent",
    "temperature_c",
    "time_h",
    "equiv",
]


@dataclass
class ReactionOracle:
    """Lookup yields for a fixed target substrate (optionally fixed plate)."""

    df: pd.DataFrame
    substrate_id: str
    plate_id: Optional[str] = None
    response_col: str = "yield"

    def __post_init__(self) -> None:
        mask = self.df["substrate_id"] == self.substrate_id
        if self.plate_id is not None:
            mask &= self.df["plate_id"] == self.plate_id
        self._sub = self.df.loc[mask].copy()
        if self._sub.empty:
            raise ValueError(f"No rows for substrate={self.substrate_id} plate={self.plate_id}")
        # one row per condition (mean over replicates)
        g = (
            self._sub.groupby("condition_id", as_index=False)
            .agg({self.response_col: "mean", **{c: "first" for c in CONDITION_COLS if c in self._sub}})
        )
        self.condition_ids = g["condition_id"].to_numpy()
        self.y = g[self.response_col].to_numpy(dtype=float)
        self.meta = g
        self._id_to_idx: Dict[str, int] = {cid: i for i, cid in enumerate(self.condition_ids)}

    @property
    def n(self) -> int:
        return len(self.condition_ids)

    @property
    def y_star(self) -> float:
        return float(np.max(self.y))

    def observe(self, indices: Sequence[int]) -> np.ndarray:
        idx = np.asarray(indices, dtype=int)
        return self.y[idx].copy()

    def observe_condition_ids(self, condition_ids: Sequence[str]) -> np.ndarray:
        idx = [self._id_to_idx[c] for c in condition_ids]
        return self.observe(idx)

    def top_fraction_mask(self, frac: float = 0.05) -> np.ndarray:
        thr = np.quantile(self.y, 1.0 - frac)
        return self.y >= thr
