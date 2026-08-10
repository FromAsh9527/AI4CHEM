"""A3: source-weighted label pooling (matched-init compatible)."""

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


def _weight_token(w: float) -> str:
    """0.25 -> 0p25 ; 0.1 -> 0p1 ; 1.0 -> 1p0"""
    s = f"{w:.6g}"
    return s.replace(".", "p")


class LabelWeightWarmStartStrategy(BaseStrategy):
    """Like label_warm, but source points get inflated GP noise (weaker evidence).

    ``alpha_source = base_noise / source_weight``, ``alpha_target = base_noise``.
    ``source_weight=1`` ≡ A1 raw pooling.
    """

    def __init__(self, source_weight: float = 0.25) -> None:
        if source_weight <= 0:
            raise ValueError(f"source_weight must be > 0, got {source_weight}")
        self.source_weight = float(source_weight)
        self.name = f"label_weight_w{_weight_token(self.source_weight)}"

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
            raise ValueError("label_weight_warm requires source_df and X_source")

        rng = np.random.default_rng(config.seed)
        init_idx = sample_init_indices(target_oracle.n, config.n_init, rng)
        src_rng = np.random.default_rng(config.seed + 1_000_003)
        keep = select_source_indices(
            len(source_df),
            source_fraction=config.source_fraction,
            max_warm_points=config.max_warm_points,
            rng=src_rng,
        )
        warm_X = np.asarray(X_source, dtype=np.float64)[keep]
        warm_y = source_df["response"].to_numpy(dtype=float)[keep]

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
            warm_weight=self.source_weight,
        )
        return StrategyResult(
            name=self.name,
            bo=bo,
            meta={
                "init_indices": init_idx.tolist(),
                "n_source_used": int(len(keep)),
                "used_source_labels": True,
                "pool_mode": "source_weighted",
                "source_weight": self.source_weight,
                "max_warm_points": config.max_warm_points,
            },
        )
