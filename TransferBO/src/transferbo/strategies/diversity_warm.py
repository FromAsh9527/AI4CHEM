"""Diversity warm-start: use source structure coverage, not source labels."""

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
)


class DiversityWarmStartStrategy(BaseStrategy):
    name = "diversity_warm"

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
        init_idx = diversity_init_indices(
            X_target, config.n_init, rng, X_ref=X_source
        )
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
            # deliberately no warm labels
        )
        return StrategyResult(
            name=self.name,
            bo=bo,
            meta={"init_indices": init_idx.tolist(), "used_source_labels": False},
        )
