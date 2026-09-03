"""W10: light task-aware baseline — append a binary task-ID feature while pooling labels."""

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


def append_task_id(X: np.ndarray, task_value: float) -> np.ndarray:
    X = np.asarray(X, dtype=np.float64)
    col = np.full((len(X), 1), float(task_value), dtype=np.float64)
    return np.hstack([X, col])


class LabelTaskIdWarmStartStrategy(BaseStrategy):
    """Like label_warm, but source/target rows carry an extra task indicator feature.

    Source points get task_id=0, target points get task_id=1. This is a minimal
    task-aware control (not a full MTGP / ICM).
    """

    name = "label_taskid_warm"

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
            raise ValueError("label_taskid_warm requires source_df and X_source")

        rng = np.random.default_rng(config.seed)
        init_idx = sample_init_indices(target_oracle.n, config.n_init, rng)
        src_rng = np.random.default_rng(config.seed + 1_000_003)
        keep = select_source_indices(
            len(source_df),
            source_fraction=config.source_fraction,
            max_warm_points=config.max_warm_points,
            rng=src_rng,
        )
        warm_X = append_task_id(np.asarray(X_source, dtype=np.float64)[keep], 0.0)
        warm_y = source_df["response"].to_numpy(dtype=float)[keep]
        X_tgt = append_task_id(X_target, 1.0)

        bo = run_bo_loop(
            target_oracle,
            X_tgt,
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
                "used_source_labels": True,
                "task_id_feature": True,
                "max_warm_points": config.max_warm_points,
                "note": "binary task-ID feature; not full MTGP",
            },
        )
