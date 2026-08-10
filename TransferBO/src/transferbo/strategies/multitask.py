"""Simple multi-task: joint training on source+target observations during BO."""

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
    sample_init_indices,
    select_source_indices,
)


class SimpleMultiTaskStrategy(BaseStrategy):
    """Shared feature-space GP: concatenate source labels as standing prior data.

    This is a deliberately simple multi-task baseline (shared kernel in joint
    feature space). More structured multi-task GPs can replace this later.
    """

    name = "multitask"

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
        if source_df is None or X_source is None:
            raise ValueError("multitask requires source_df and X_source")

        rng = np.random.default_rng(config.seed)
        keep = select_source_indices(
            len(source_df),
            source_fraction=config.source_fraction,
            max_warm_points=config.max_warm_points,
            rng=rng,
        )
        warm_X = np.asarray(X_source, dtype=np.float64)[keep]
        warm_y = source_df["response"].to_numpy(dtype=float)[keep]

        init_idx = sample_init_indices(target_oracle.n, config.n_init, rng)
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
            warm_X=warm_X,
            warm_y=warm_y,
        )
        return StrategyResult(
            name=self.name,
            bo=bo,
            meta={
                "init_indices": init_idx.tolist(),
                "n_source_used": int(len(keep)),
                "max_warm_points": config.max_warm_points,
                "note": "shared-kernel joint GP; not a full ICM multi-task GP",
            },
        )
