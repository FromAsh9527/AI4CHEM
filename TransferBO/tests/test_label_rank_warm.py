"""A2 rank pooling smoke + matched init with cold + leakage audit."""

from __future__ import annotations

import numpy as np
import pandas as pd
import transferbo.bo.loop as loop_mod
from transferbo.bo.loop import percentile_ranks, run_bo_loop
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


def test_rank_mode_never_ranks_full_unobserved_board(monkeypatch):
    """Target percentile_ranks must see only currently observed target yields."""
    rng = np.random.default_rng(1)
    n = 30
    X = rng.normal(size=(n, 4))
    y = rng.uniform(0, 10, size=n)
    y[-1] = 1e6  # extreme unobserved point — must not enter rank sets early
    oracle = PlateOracle(
        pd.DataFrame({"response": y, "smiles": [f"c{i}" for i in range(n)]})
    )
    warm_X = rng.normal(size=(8, 4))
    warm_y = percentile_ranks(rng.uniform(0, 10, size=8))
    init = np.arange(5)
    seen_lengths: list[int] = []
    real = loop_mod.percentile_ranks

    def spy(arr):
        seen_lengths.append(len(np.asarray(arr)))
        return real(arr)

    monkeypatch.setattr(loop_mod, "percentile_ranks", spy)
    run_bo_loop(
        oracle,
        X,
        init_indices=init,
        budget=10,
        target_pool_mode="rank",
        warm_X=warm_X,
        warm_y=warm_y,
        seed=0,
    )
    # one call per acquisition after init (budget-init = 5); lengths 5..9
    assert seen_lengths
    assert max(seen_lengths) < n
    assert seen_lengths[0] == 5
    assert seen_lengths[-1] == 9
