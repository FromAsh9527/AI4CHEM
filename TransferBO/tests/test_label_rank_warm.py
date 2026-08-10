"""A2 rank pooling smoke + matched init with cold."""

from __future__ import annotations

import numpy as np
import pandas as pd

from transferbo.bo.loop import percentile_ranks
from transferbo.data.oracle import PlateOracle
from transferbo.strategies.base import StrategyConfig
from transferbo.strategies.cold_start import ColdStartStrategy
from transferbo.strategies.label_rank_warm import LabelRankWarmStartStrategy


def test_percentile_ranks_basic():
    y = np.array([10.0, 30.0, 20.0])
    r = percentile_ranks(y)
    assert r.shape == (3,)
    assert r[0] < r[2] < r[1]
    assert np.all(r > 0) and np.all(r < 1)


def test_label_rank_warm_matches_cold_init_and_runs():
    rng = np.random.default_rng(0)
    n = 40
    X = rng.normal(size=(n, 8))
    y = rng.uniform(0, 100, size=n)
    target = PlateOracle(
        pd.DataFrame({"response": y, "smiles": [f"c{i}" for i in range(n)]})
    )
    source_df = pd.DataFrame({"response": rng.uniform(0, 100, size=n)})
    X_source = rng.normal(size=(n, 8))
    cfg = StrategyConfig(
        n_init=8,
        budget=14,
        seed=3,
        max_warm_points=12,
        source_fraction=1.0,
        backend="sklearn",
    )
    cold = ColdStartStrategy().run(target_oracle=target, X_target=X, config=cfg)
    # fresh oracle (cold already queried)
    target2 = PlateOracle(
        pd.DataFrame({"response": y, "smiles": [f"c{i}" for i in range(n)]})
    )
    lab = LabelRankWarmStartStrategy().run(
        target_oracle=target2,
        X_target=X,
        config=cfg,
        source_df=source_df,
        X_source=X_source,
    )
    assert cold.meta["init_indices"] == lab.meta["init_indices"]
    assert lab.meta["pool_mode"] == "rank"
    assert len(lab.bo.best_so_far) == 14
    # evaluation curve is raw yield, not ranks in [0,1] only
    assert lab.bo.best_so_far[-1] >= lab.bo.best_so_far[0]
