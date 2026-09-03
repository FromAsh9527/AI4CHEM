"""P0 shared-init strategies: init matching and basic behaviour."""

from __future__ import annotations

from pathlib import Path

import pytest

from transferbo2.data.database import connect, experiments_frame, load_descriptor_matrix
from transferbo2.data.demo import write_demo_to_db
from transferbo2.data.oracle import ReactionOracle
from transferbo2.descriptors.features import align_condition_features
from transferbo2.strategies.base import StrategyConfig, available_strategies, get_strategy
from transferbo2.strategies import select_cold_init, select_topk_init


@pytest.fixture(scope="module")
def demo_db() -> Path:
    import shutil
    root = Path("results") / "_p0_test_tmp"
    root.mkdir(parents=True, exist_ok=True)
    db = root / "test.db"
    csv = root / "demo_long.csv"
    if db.exists():
        db.unlink()
    write_demo_to_db(db, seed=0, processed_csv=csv)
    return db


@pytest.fixture(scope="module")
def loso_context(demo_db):
    with connect(demo_db) as conn:
        df = experiments_frame(conn)
        desc_df = load_descriptor_matrix(conn, entity_type="substrate", name="physchem_v1")
    cols = [c for c in desc_df.columns if c != "entity_id"]
    desc = {str(r["entity_id"]): r[cols].to_numpy(dtype=float) for _, r in desc_df.iterrows()}
    target = sorted(df["substrate_id"].unique())[-1]
    hist = df[df["substrate_id"] != target].reset_index(drop=True)
    oracle = ReactionOracle(df, target)
    X_hist, X_tgt = align_condition_features(hist, oracle.meta)
    return {
        "df": df,
        "target": target,
        "hist": hist,
        "oracle": oracle,
        "X_hist": X_hist,
        "X_tgt": X_tgt,
        "desc": desc,
    }


def test_p0_strategies_registered():
    names = available_strategies()
    for required in ("cold_random_post", "topk_random_post", "topk_only"):
        assert required in names


def test_cold_init_matches_between_ei_and_random_post(loso_context):
    ctx = loso_context
    cfg = StrategyConfig(n_init=4, budget=10, seed=7)
    kw = dict(
        X_target=ctx["X_tgt"],
        y_target=ctx["oracle"].y,
        condition_ids_target=ctx["oracle"].condition_ids,
        hist_df=ctx["hist"],
        X_hist=ctx["X_hist"],
        desc_by_id=ctx["desc"],
        target_substrate=ctx["target"],
        config=cfg,
    )
    cold = get_strategy("cold_start").run(**kw)
    cold_rp = get_strategy("cold_random_post").run(**kw)
    expected = select_cold_init(len(ctx["oracle"].y), cfg.n_init, cfg.seed)
    assert cold.meta["init_indices"] == expected.tolist()
    assert cold_rp.meta["init_indices"] == expected.tolist()
    assert cold.bo.indices[: cfg.n_init] == cold_rp.bo.indices[: cfg.n_init]


def test_topk_init_matches_between_ei_and_random_post(loso_context):
    ctx = loso_context
    cfg = StrategyConfig(n_init=4, budget=10, seed=3, topk=4)
    kw = dict(
        X_target=ctx["X_tgt"],
        y_target=ctx["oracle"].y,
        condition_ids_target=ctx["oracle"].condition_ids,
        hist_df=ctx["hist"],
        X_hist=ctx["X_hist"],
        desc_by_id=ctx["desc"],
        target_substrate=ctx["target"],
        config=cfg,
    )
    topk = get_strategy("topk_warm").run(**kw)
    topk_rp = get_strategy("topk_random_post").run(**kw)
    expected = select_topk_init(
        ctx["hist"],
        ctx["oracle"].condition_ids,
        topk=cfg.topk,
        n_init=cfg.n_init,
        seed=cfg.seed,
        use_plate_correction=cfg.use_plate_correction,
    )
    assert topk.meta["init_indices"] == expected.tolist()
    assert topk_rp.meta["init_indices"] == expected.tolist()
    assert topk.bo.indices[: cfg.n_init] == topk_rp.bo.indices[: cfg.n_init]


def test_topk_only_budget_is_n_init(loso_context):
    ctx = loso_context
    cfg = StrategyConfig(n_init=4, budget=20, seed=1, topk=4)
    res = get_strategy("topk_only").run(
        X_target=ctx["X_tgt"],
        y_target=ctx["oracle"].y,
        condition_ids_target=ctx["oracle"].condition_ids,
        hist_df=ctx["hist"],
        X_hist=ctx["X_hist"],
        desc_by_id=ctx["desc"],
        target_substrate=ctx["target"],
        config=cfg,
    )
    assert len(res.bo.values) == cfg.n_init
    assert res.meta["budget_effective"] == cfg.n_init


def test_cold_random_post_fills_budget(loso_context):
    ctx = loso_context
    cfg = StrategyConfig(n_init=4, budget=10, seed=5)
    res = get_strategy("cold_random_post").run(
        X_target=ctx["X_tgt"],
        y_target=ctx["oracle"].y,
        condition_ids_target=ctx["oracle"].condition_ids,
        hist_df=ctx["hist"],
        X_hist=ctx["X_hist"],
        desc_by_id=ctx["desc"],
        target_substrate=ctx["target"],
        config=cfg,
    )
    assert len(res.bo.values) == cfg.budget
