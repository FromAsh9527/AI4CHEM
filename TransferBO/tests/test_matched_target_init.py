"""Matched-target-init: label_warm must share cold_start init indices for same seed."""

from __future__ import annotations

import numpy as np
import pandas as pd

from transferbo.data.oracle import PlateOracle
from transferbo.strategies.base import StrategyConfig
from transferbo.strategies.cold_start import ColdStartStrategy
from transferbo.strategies.label_warm import LabelWarmStartStrategy


def test_label_and_cold_share_target_init_indices():
    rng = np.random.default_rng(0)
    n = 40
    X = rng.normal(size=(n, 8))
    y = rng.uniform(0, 100, size=n)
    target = PlateOracle(
        pd.DataFrame({"response": y, "smiles": [f"c{i}" for i in range(n)]}),
        response_col="response",
    )
    source_df = pd.DataFrame({"response": rng.uniform(0, 100, size=n)})
    X_source = rng.normal(size=(n, 8))

    cfg = StrategyConfig(
        n_init=10,
        budget=12,
        seed=7,
        max_warm_points=15,
        source_fraction=1.0,
        backend="sklearn",
    )
    cold = ColdStartStrategy().run(
        target_oracle=target, X_target=X, config=cfg
    )
    lab = LabelWarmStartStrategy().run(
        target_oracle=target,
        X_target=X,
        config=cfg,
        source_df=source_df,
        X_source=X_source,
    )
    assert cold.meta["init_indices"] == lab.meta["init_indices"]
