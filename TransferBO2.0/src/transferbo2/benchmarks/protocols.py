"""Benchmark runners: LOSO / LOPO / dual."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from transferbo2.data.database import connect, experiments_frame, load_descriptor_matrix
from transferbo2.data.oracle import ReactionOracle
from transferbo2.descriptors.features import align_condition_features
from transferbo2.metrics.evaluate import negative_transfer_rate, summarize_run
from transferbo2.strategies.base import StrategyConfig, available_strategies, get_strategy


def _desc_map(conn, name: str = "physchem_v1") -> Dict[str, np.ndarray]:
    df = load_descriptor_matrix(conn, entity_type="substrate", name=name)
    if df.empty:
        return {}
    cols = [c for c in df.columns if c != "entity_id"]
    out: Dict[str, np.ndarray] = {}
    for _, row in df.iterrows():
        out[str(row["entity_id"])] = row[cols].to_numpy(dtype=float)
    return out


def _build_features(hist_df: pd.DataFrame, target_meta: pd.DataFrame):
    X_hist, X_tgt = align_condition_features(hist_df, target_meta)
    return X_hist, X_tgt


def run_loso_once(
    df: pd.DataFrame,
    desc_by_id: Dict[str, np.ndarray],
    *,
    target_substrate: str,
    strategy_name: str,
    config: StrategyConfig,
    target_plate: Optional[str] = None,
) -> dict:
    oracle = ReactionOracle(df, target_substrate, plate_id=target_plate)
    hist = df[df["substrate_id"] != target_substrate].copy()
    if hist.empty:
        raise ValueError("No historical substrates left for LOSO")
    X_hist, X_tgt = _build_features(hist, oracle.meta)
    strategy = get_strategy(strategy_name)
    result = strategy.run(
        X_target=X_tgt,
        y_target=oracle.y,
        condition_ids_target=oracle.condition_ids,
        hist_df=hist.reset_index(drop=True),
        X_hist=X_hist,
        desc_by_id=desc_by_id,
        target_substrate=target_substrate,
        config=config,
    )
    stats = summarize_run(
        result.bo.values,
        y_star=oracle.y_star,
        top_mask=oracle.top_fraction_mask(0.05),
        indices=result.bo.indices,
    )
    return {
        "strategy": strategy_name,
        "target_substrate": target_substrate,
        "target_plate": target_plate,
        "seed": config.seed,
        "stats": stats,
        "meta": result.meta,
        "bo": result.bo.to_dict(),
    }


def run_loso_grid(
    db_path: Optional[str | Path] = None,
    *,
    strategies: Sequence[str],
    target_substrates: Optional[Sequence[str]] = None,
    seeds: Sequence[int] = (0, 1, 2),
    n_init: int = 5,
    budget: int = 20,
    out_dir: Optional[str | Path] = None,
) -> pd.DataFrame:
    with connect(db_path) as conn:
        df = experiments_frame(conn)
        desc = _desc_map(conn)
    if target_substrates is None:
        target_substrates = sorted(df["substrate_id"].unique())
    rows = []
    records = []
    for sid in target_substrates:
        for name in strategies:
            cold_aucs = []
            tr_aucs = []
            for seed in seeds:
                cfg = StrategyConfig(n_init=n_init, budget=budget, seed=int(seed))
                rec = run_loso_once(df, desc, target_substrate=sid, strategy_name=name, config=cfg)
                records.append(rec)
                rows.append(
                    {
                        "strategy": name,
                        "target_substrate": sid,
                        "seed": seed,
                        "auc": rec["stats"]["auc"],
                        "final_best": rec["stats"]["final_best"],
                        "hit10_top5pct": rec["stats"]["hit10_top5pct"],
                        "T_0.95": rec["stats"].get("T_0.95"),
                    }
                )
                if name == "cold_start":
                    cold_aucs.append(rec["stats"]["auc"])
                else:
                    tr_aucs.append(rec["stats"]["auc"])
    summary = pd.DataFrame(rows)
    if out_dir is not None:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        summary.to_csv(out / "loso_summary.csv", index=False)
        (out / "loso_records.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
    return summary


def run_lopo_once(
    df: pd.DataFrame,
    desc_by_id: Dict[str, np.ndarray],
    *,
    target_plate: str,
    strategy_name: str,
    config: StrategyConfig,
    target_substrate: str,
) -> dict:
    """Train on other plates; evaluate BO on target substrate restricted to target plate."""
    hist = df[df["plate_id"] != target_plate].copy()
    oracle = ReactionOracle(df, target_substrate, plate_id=target_plate)
    X_hist, X_tgt = _build_features(hist, oracle.meta)
    strategy = get_strategy(strategy_name)
    result = strategy.run(
        X_target=X_tgt,
        y_target=oracle.y,
        condition_ids_target=oracle.condition_ids,
        hist_df=hist.reset_index(drop=True),
        X_hist=X_hist,
        desc_by_id=desc_by_id,
        target_substrate=target_substrate,
        config=config,
    )
    stats = summarize_run(
        result.bo.values,
        y_star=oracle.y_star,
        top_mask=oracle.top_fraction_mask(0.05),
        indices=result.bo.indices,
    )
    return {
        "strategy": strategy_name,
        "target_substrate": target_substrate,
        "target_plate": target_plate,
        "seed": config.seed,
        "stats": stats,
        "meta": result.meta,
    }
