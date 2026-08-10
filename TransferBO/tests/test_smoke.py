"""Smoke tests that run without the full Science/CHAOS dataset."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from transferbo.bo import expected_improvement
from transferbo.data import PlateOracle
from transferbo.metrics import best_so_far_summary, queries_to_threshold
from transferbo.representations import build_representation
from transferbo.strategies import StrategyConfig, build_strategy


def _toy_plate(n: int = 40, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    smiles = [f"C{'C' * (i % 5)}O" for i in range(n)]
    # Make SMILES chemically valid-ish with simple alcohols / alkanes fallback
    base = ["CCO", "CCCO", "CCCCO", "c1ccccc1", "CCOC", "CCN", "CC(=O)O", "c1ccncc1"]
    smiles = [base[i % len(base)] for i in range(n)]
    y = rng.random(n)
    y[0] = 0.99
    return pd.DataFrame(
        {
            "additive_id": [f"A{i}" for i in range(n)],
            "smiles": smiles,
            "plate_id": "plate_1",
            "response": y,
        }
    )


def test_ei_prefers_high_mean():
    mean = np.array([0.1, 0.9])
    std = np.array([0.1, 0.1])
    ei = expected_improvement(mean, std, best_f=0.5)
    assert ei[1] > ei[0]


def test_morgan_and_cold_start_loop():
    df = _toy_plate()
    rep = build_representation("morgan", radius=2, n_bits=128)
    X = rep.fit_transform(df["smiles"].tolist())
    oracle = PlateOracle(df)
    strategy = build_strategy("cold_start")
    cfg = StrategyConfig(n_init=5, budget=12, backend="sklearn", seed=0, batch_size=1)
    result = strategy.run(target_oracle=oracle, X_target=X, config=cfg)
    assert len(result.bo.queried_indices) == 12
    assert result.bo.best_so_far == sorted(result.bo.best_so_far)
    assert result.bo.best_so_far[-1] >= result.bo.best_so_far[0]


def test_label_warm_uses_source():
    tgt = _toy_plate(n=30, seed=1)
    src = _toy_plate(n=30, seed=2)
    src["plate_id"] = "plate_2"
    rep = build_representation("morgan", n_bits=64)
    fit = tgt["smiles"].tolist() + src["smiles"].tolist()
    rep.fit(fit)
    X_t = rep.transform(tgt["smiles"].tolist())
    X_s = rep.transform(src["smiles"].tolist())
    oracle = PlateOracle(tgt)
    strategy = build_strategy("label_warm")
    cfg = StrategyConfig(n_init=4, budget=10, backend="sklearn", seed=1)
    result = strategy.run(
        target_oracle=oracle,
        X_target=X_t,
        config=cfg,
        source_df=src,
        X_source=X_s,
    )
    assert result.meta["used_source_labels"] is True
    assert len(result.bo.best_so_far) == 10


def test_metrics_queries_to_threshold():
    curves = [[0.1, 0.2, 0.8], [0.05, 0.9]]
    q = queries_to_threshold(curves, 0.75)
    assert q[0] == 3
    assert q[1] == 2
    summary = best_so_far_summary(curves, budget=3)
    assert len(summary) == 3
    assert summary["mean"].iloc[-1] == pytest.approx((0.8 + 0.9) / 2)
