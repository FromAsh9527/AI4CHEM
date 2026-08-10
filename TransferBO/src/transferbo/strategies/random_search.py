"""Random search baseline on the target plate."""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from transferbo.bo.loop import BOLoopResult
from transferbo.data.oracle import PlateOracle
from transferbo.representations.base import Representation
from transferbo.strategies.base import BaseStrategy, StrategyConfig, StrategyResult


class RandomStrategy(BaseStrategy):
    name = "random"

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
        budget = min(config.budget, target_oracle.n)
        order = rng.permutation(target_oracle.n)[:budget]
        y = target_oracle.query(order)

        result = BOLoopResult(n_init=0)
        running = -np.inf
        for idx, yi in zip(order, y):
            result.queried_indices.append(int(idx))
            result.responses.append(float(yi))
            running = max(running, float(yi))
            result.best_so_far.append(running)

        return StrategyResult(name=self.name, bo=result, meta={"order": order.tolist()})
