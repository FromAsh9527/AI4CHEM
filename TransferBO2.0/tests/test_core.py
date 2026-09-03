"""Unit tests for TransferBO2.0 platform core."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from transferbo2.bo.loop import run_bo_loop
from transferbo2.data.demo import generate_demo_dataset, write_demo_to_db
from transferbo2.data.database import connect, experiments_frame, load_descriptor_matrix
from transferbo2.data.oracle import ReactionOracle
from transferbo2.descriptors.features import align_condition_features, substrate_similarity_map
from transferbo2.metrics.evaluate import negative_transfer_rate, summarize_run
from transferbo2.plate.effects import anchor_plate_offsets, variance_components
from transferbo2.strategies.base import StrategyConfig, available_strategies, get_strategy


@pytest.fixture(scope="module")
def demo_db(tmp_path_factory) -> Path:
    db = tmp_path_factory.mktemp("db") / "test.db"
    csv = tmp_path_factory.mktemp("csv") / "demo_long.csv"
    write_demo_to_db(db, seed=0, processed_csv=csv)
    return db


def test_demo_has_multi_substrate_plate(demo_db):
    with connect(demo_db) as conn:
        df = experiments_frame(conn)
    assert df["substrate_id"].nunique() >= 4
    assert df["plate_id"].nunique() >= 2
    assert (df["is_anchor"] == 1).sum() > 0


def test_plate_audit_runs(demo_db):
    with connect(demo_db) as conn:
        df = experiments_frame(conn)
    vc = variance_components(df)
    assert vc["n"] == len(df)
    off = anchor_plate_offsets(df)
    assert "plate_id" in off.columns


def test_oracle_and_cold_bo(demo_db):
    with connect(demo_db) as conn:
        df = experiments_frame(conn)
    sid = sorted(df["substrate_id"].unique())[0]
    oracle = ReactionOracle(df, sid)
    X, _ = align_condition_features(oracle.meta, oracle.meta)
    rng = np.random.default_rng(0)
    init = rng.choice(oracle.n, size=min(5, oracle.n), replace=False)
    bo = run_bo_loop(X, oracle.y, init, budget=10, seed=0)
    assert len(bo.values) == 10
    assert bo.best_so_far[-1] >= bo.best_so_far[0]


def test_strategies_registry():
    names = available_strategies()
    for required in [
        "random",
        "cold_start",
        "topk_warm",
        "nearest_topk_warm",
        "pooled",
        "sim_weighted",
        "contextual",
        "plate_aware",
        "safe_gate",
    ]:
        assert required in names


def test_loso_transfer_strategies(demo_db):
    with connect(demo_db) as conn:
        df = experiments_frame(conn)
        desc_df = load_descriptor_matrix(conn, entity_type="substrate", name="physchem_v1")
    cols = [c for c in desc_df.columns if c != "entity_id"]
    desc = {str(r["entity_id"]): r[cols].to_numpy(dtype=float) for _, r in desc_df.iterrows()}
    target = sorted(df["substrate_id"].unique())[-1]
    hist = df[df["substrate_id"] != target].reset_index(drop=True)
    oracle = ReactionOracle(df, target)
    X_hist, X_tgt = align_condition_features(hist, oracle.meta)
    cfg = StrategyConfig(n_init=4, budget=8, seed=1, max_warm_points=40)
    for name in ["cold_start", "topk_warm", "sim_weighted", "plate_aware", "safe_gate"]:
        res = get_strategy(name).run(
            X_target=X_tgt,
            y_target=oracle.y,
            condition_ids_target=oracle.condition_ids,
            hist_df=hist,
            X_hist=X_hist,
            desc_by_id=desc,
            target_substrate=target,
            config=cfg,
        )
        assert len(res.bo.values) == 8
        stats = summarize_run(
            res.bo.values,
            y_star=oracle.y_star,
            top_mask=oracle.top_fraction_mask(0.05),
            indices=res.bo.indices,
        )
        assert np.isfinite(stats["auc"])


def test_similarity_and_ntr():
    desc = {"a": np.array([0.0, 0.0]), "b": np.array([0.1, 0.0]), "c": np.array([5.0, 5.0])}
    sims = substrate_similarity_map(desc, "a", ["b", "c"], lengthscale=1.0)
    assert sims["b"] > sims["c"]
    ntr = negative_transfer_rate([1.0, 2.0, 3.0], [2.0, 2.0, 2.0])
    assert 0.0 <= ntr <= 1.0


def test_generate_demo_shapes():
    df, desc, meta = generate_demo_dataset(seed=1, n_substrates=4, n_plates=2, subsample_per_substrate=50)
    assert len(desc) == 4
    assert df["yield"].between(0, 100).all()
    assert meta["reaction_id"]
