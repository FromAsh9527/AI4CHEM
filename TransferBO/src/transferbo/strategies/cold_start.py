"""Cold-start: target plate only (random or diversity initial design)."""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from transferbo.bo.loop import run_bo_loop
from transferbo.data.oracle import PlateOracle
from transferbo.representations.base import Representation
from transferbo.strategies.base import (
    BaseStrategy,
    StrategyConfig,
    StrategyResult,
    diversity_init_indices,
    sample_init_indices,
)


class ColdStartStrategy(BaseStrategy):
    """Single-plate BO. Default init is random; set init_mode='diversity' to spread starts."""

    name = "cold_start"

    def __init__(self, *, force_init_mode: str | None = None) -> None:
        self.force_init_mode = force_init_mode

    def run(
        self,
        *,
        target_oracle: PlateOracle,
        X_target: np.ndarray,
        config: StrategyConfig,
        source_df: Optional[pd.DataFrame] = None,
        X_source: Optional[np.ndarray] = None,
        representation: Optional[Representation] = None,
    ) -> StrategyResult:
        rng = np.random.default_rng(config.seed)
        init_mode = (self.force_init_mode or config.init_mode or "random").lower()
        if init_mode == "diversity":
            init_idx = diversity_init_indices(X_target, config.n_init, rng, X_ref=None)
        elif init_mode == "random":
            init_idx = sample_init_indices(target_oracle.n, config.n_init, rng)
        else:
            raise ValueError(f"Unknown init_mode: {init_mode!r}")

        bo = run_bo_loop(
            target_oracle,
            X_target,
            init_indices=init_idx,
            budget=config.budget,
            acquisition=config.acquisition,
            batch_size=config.batch_size,
            ucb_beta=config.ucb_beta,
            backend=config.backend,
            normalize_y=config.normalize_y,
            seed=config.seed,
        )
        return StrategyResult(
            name=self.name if self.force_init_mode is None else f"cold_{init_mode}",
            bo=bo,
            meta={"init_indices": init_idx.tolist(), "init_mode": init_mode},
        )


class ColdDiversityStrategy(ColdStartStrategy):
    """Cold-start with farthest-point / diversity initialisation (CHAOS-style spirit)."""

    name = "cold_diversity"

    def __init__(self) -> None:
        super().__init__(force_init_mode="diversity")
