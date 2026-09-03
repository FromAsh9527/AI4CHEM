#!/usr/bin/env python
"""Run one or more strategies on a LOSO target (smoke / single experiment)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from transferbo2.benchmarks.protocols import run_loso_once, _desc_map
from transferbo2.data.database import DEFAULT_DB, connect, experiments_frame
from transferbo2.strategies.base import StrategyConfig, available_strategies


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("--db", type=Path, default=None)
    args = p.parse_args()
    cfg = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    db = Path(cfg.get("db", args.db or DEFAULT_DB))

    with connect(db) as conn:
        df = experiments_frame(conn)
        desc = _desc_map(conn)

    target = cfg.get("target_substrate") or sorted(df["substrate_id"].unique())[-1]
    strategies = cfg.get("strategies") or ["cold_start", "plate_aware"]
    seeds = cfg.get("seeds") or [0]
    sc_kwargs = dict(
        n_init=int(cfg.get("n_init", 5)),
        budget=int(cfg.get("budget", 20)),
        acquisition=cfg.get("acquisition", "ei"),
        topk=int(cfg.get("topk", 5)),
        max_warm_points=int(cfg.get("max_warm_points", 120)),
        gate_spearman_min=float(cfg.get("gate_spearman_min", 0.2)),
        use_plate_correction=bool(cfg.get("use_plate_correction", True)),
    )

    out_dir = Path(cfg.get("out_dir", "results/smoke"))
    out_dir.mkdir(parents=True, exist_ok=True)
    all_recs = []
    for name in strategies:
        if name not in available_strategies():
            raise SystemExit(f"Unknown strategy {name}. Available: {available_strategies()}")
        for seed in seeds:
            sc = StrategyConfig(seed=int(seed), **sc_kwargs)
            rec = run_loso_once(df, desc, target_substrate=target, strategy_name=name, config=sc)
            all_recs.append(rec)
            print(
                f"{name:18s} seed={seed} AUC={rec['stats']['auc']:.1f} "
                f"best={rec['stats']['final_best']:.2f} hit10={rec['stats']['hit10_top5pct']}"
            )

    (out_dir / "run.json").write_text(json.dumps(all_recs, indent=2), encoding="utf-8")
    print(f"Wrote {out_dir / 'run.json'}")


if __name__ == "__main__":
    main()
