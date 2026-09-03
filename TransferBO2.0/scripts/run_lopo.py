#!/usr/bin/env python
"""Leave-one-plate-out smoke runner."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from transferbo2.benchmarks.protocols import _desc_map, run_lopo_once
from transferbo2.data.database import DEFAULT_DB, connect, experiments_frame
from transferbo2.strategies.base import StrategyConfig


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--config", type=Path, default=Path("configs/smoke.yaml"))
    args = p.parse_args()
    cfg = yaml.safe_load(args.config.read_text(encoding="utf-8")) if args.config.exists() else {}
    db = Path(cfg.get("db", DEFAULT_DB))
    with connect(db) as conn:
        df = experiments_frame(conn)
        desc = _desc_map(conn)
    target_plate = cfg.get("target_plate") or sorted(df["plate_id"].unique())[-1]
    # pick a substrate that has non-anchor rows on that plate
    cand = df[(df["plate_id"] == target_plate) & (df["is_anchor"] == 0)]["substrate_id"]
    target_sub = cfg.get("target_substrate") or (cand.iloc[0] if len(cand) else df["substrate_id"].iloc[0])
    strategies = cfg.get("strategies") or ["cold_start", "plate_aware"]
    out = []
    for name in strategies:
        sc = StrategyConfig(
            n_init=int(cfg.get("n_init", 5)),
            budget=int(cfg.get("budget", 15)),
            seed=0,
            max_warm_points=int(cfg.get("max_warm_points", 80)),
        )
        rec = run_lopo_once(
            df,
            desc,
            target_plate=target_plate,
            strategy_name=name,
            config=sc,
            target_substrate=target_sub,
        )
        out.append(rec)
        print(f"{name:18s} plate={target_plate} sub={target_sub} AUC={rec['stats']['auc']:.1f}")
    path = Path(cfg.get("out_dir", "results/lopo_smoke"))
    path.mkdir(parents=True, exist_ok=True)
    (path / "lopo.json").write_text(json.dumps(out, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
