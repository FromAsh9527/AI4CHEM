"""Tests for S5 init-only and W10 task-ID strategies."""

from __future__ import annotations

import numpy as np
import pandas as pd

from transferbo.data.oracle import PlateOracle
from transferbo.strategies.base import StrategyConfig
from transferbo.strategies.init_only_warm import (
    InitOnlyWarmStartStrategy,
    source_guided_init_indices,
)
from transferbo.strategies.label_taskid_warm import (
    LabelTaskIdWarmStartStrategy,
    append_task_id,
)
from transferbo.strategies.label_warm import LabelWarmStartStrategy
from transferbo.strategies import build_strategy


def test_append_task_id_shape():
    X = np.ones((5, 3))
    out = append_task_id(X, 1.0)
    assert out.shape == (5, 4)
    assert np.allclose(out[:, -1], 1.0)


def test_source_guided_init_maps_top_keys():
    src = pd.DataFrame(
        {
            "candidate_key": ["a", "b", "c", "d"],
            "response": [1.0, 10.0, 3.0, 8.0],
        }
    )
    tgt = pd.DataFrame(
        {
            "candidate_key": ["a", "b", "c", "d"],
            "response": [0.0, 0.0, 0.0, 0.0],
            "smiles": ["s0", "s1", "s2", "s3"],
        }
    )
    idx = source_guided_init_indices(src, tgt, n_init=2, rng=np.random.default_rng(0))
    assert list(idx) == [1, 3]  # b then d


def test_init_only_no_warm_labels_in_meta():
    rng = np.random.default_rng(0)
    n = 30
    keys = [f"k{i}" for i in range(n)]
    target = PlateOracle(
        pd.DataFrame(
            {
                "response": rng.uniform(0, 100, size=n),
                "smiles": keys,
                "candidate_key": keys,
            }
        )
    )
    source_df = pd.DataFrame(
        {
            "response": rng.uniform(0, 100, size=n),
            "candidate_key": keys,
            "smiles": keys,
        }
    )
    X = rng.normal(size=(n, 6))
    cfg = StrategyConfig(n_init=5, budget=8, seed=1, backend="sklearn")
    res = InitOnlyWarmStartStrategy().run(
        target_oracle=target,
        X_target=X,
        config=cfg,
        source_df=source_df,
        X_source=X,
    )
    assert res.meta["used_source_labels"] is False
    assert res.meta["init_from_source_ranking"] is True
    assert len(res.meta["init_indices"]) == 5


def test_taskid_shares_init_with_label_warm():
    rng = np.random.default_rng(0)
    n = 40
    X = rng.normal(size=(n, 8))
    y = rng.uniform(0, 100, size=n)
    target = PlateOracle(
        pd.DataFrame({"response": y, "smiles": [f"c{i}" for i in range(n)]}),
    )
    source_df = pd.DataFrame({"response": rng.uniform(0, 100, size=n)})
    X_source = rng.normal(size=(n, 8))
    cfg = StrategyConfig(
        n_init=8, budget=10, seed=3, max_warm_points=12, source_fraction=1.0, backend="sklearn"
    )
    a1 = LabelWarmStartStrategy().run(
        target_oracle=target, X_target=X, config=cfg, source_df=source_df, X_source=X_source
    )
    # fresh oracle (same labels)
    target2 = PlateOracle(
        pd.DataFrame({"response": y, "smiles": [f"c{i}" for i in range(n)]}),
    )
    tid = LabelTaskIdWarmStartStrategy().run(
        target_oracle=target2, X_target=X, config=cfg, source_df=source_df, X_source=X_source
    )
    assert a1.meta["init_indices"] == tid.meta["init_indices"]
    assert tid.meta["task_id_feature"] is True


def test_build_strategy_names():
    assert build_strategy("init_only_warm").name == "init_only_warm"
    assert build_strategy("label_taskid_warm").name == "label_taskid_warm"
