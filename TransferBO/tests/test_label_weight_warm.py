"""A3 source-weighted pooling smoke + matched init."""

from __future__ import annotations

import numpy as np
import pandas as pd

from transferbo.data.oracle import PlateOracle
from transferbo.strategies import build_strategy
from transferbo.strategies.base import StrategyConfig
from transferbo.strategies.cold_start import ColdStartStrategy


def test_build_weight_strategy_name():
    s = build_strategy("label_weight_w0p25")
    assert s.name == "label_weight_w0p25"
    assert abs(s.source_weight - 0.25) < 1e-12


def test_label_weight_matches_cold_init_and_runs():
    rng = np.random.default_rng(0)
    n = 40
    X = rng.normal(size=(n, 8))
    y = rng.uniform(0, 100, size=n)
    df = pd.DataFrame({"response": y, "smiles": [f"c{i}" for i in range(n)]})
    cfg = StrategyConfig(
        n_init=8,
        budget=14,
        seed=4,
        max_warm_points=12,
        source_fraction=1.0,
        backend="sklearn",
    )
    cold = ColdStartStrategy().run(
        target_oracle=PlateOracle(df.copy()), X_target=X, config=cfg
    )
    lab = build_strategy("label_weight_w0p1").run(
        target_oracle=PlateOracle(df.copy()),
        X_target=X,
        config=cfg,
        source_df=pd.DataFrame({"response": rng.uniform(0, 100, size=n)}),
        X_source=rng.normal(size=(n, 8)),
    )
    assert cold.meta["init_indices"] == lab.meta["init_indices"]
    assert lab.meta["source_weight"] == 0.1
    assert len(lab.bo.best_so_far) == 14
