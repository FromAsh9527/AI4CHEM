#!/usr/bin/env python
"""Directed pair grid (TransferBO 1.0-style: one source → one target).

Examples:
  python scripts/run_pair.py --config configs/amination_pair_v1_pilot.yaml --dry-run
  python scripts/run_pair.py --config configs/suzuki_pair_v1_full.yaml --skip-existing --workers 16
"""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from transferbo2.benchmarks.protocols import (
    BASELINE_STRATEGIES,
    DEFAULT_TRANSFER_STRATEGIES,
    rebuild_pair_summary,
    run_pair_grid,
)
from transferbo2.data.database import DEFAULT_DB


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--skip-existing", action="store_true")
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--rebuild-only", action="store_true")
    args = p.parse_args()
    cfg = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    out_dir = Path(cfg.get("out_dir", "results/pair"))

    if args.rebuild_only:
        summary = rebuild_pair_summary(out_dir)
        print(summary.groupby("strategy")[["auc", "final_best"]].mean())
        print(f"Rebuilt {out_dir / 'pair_summary.csv'} n={len(summary)}")
        return

    sk = {
        "acquisition": cfg.get("acquisition", "ei"),
        "topk": int(cfg.get("topk", 5)),
        "max_warm_points": int(cfg.get("max_warm_points", 120)),
        "gate_spearman_min": float(cfg.get("gate_spearman_min", 0.2)),
        "use_plate_correction": bool(cfg.get("use_plate_correction", False)),
        "warm_strength": float(cfg.get("warm_strength", 0.5)),
        "lengthscale_sub": float(cfg.get("lengthscale_sub", 1.0)),
        "gate_sim_min": float(cfg.get("gate_sim_min", 0.15)),
        "similarity_metric": str(cfg.get("similarity_metric", "rbf")),
    }

    summary = run_pair_grid(
        cfg.get("db", DEFAULT_DB),
        target_substrates=cfg.get("target_substrates"),
        source_substrates=cfg.get("source_substrates"),
        seeds=cfg.get("seeds") or [0, 1, 2],
        baseline_strategies=cfg.get("baseline_strategies") or list(BASELINE_STRATEGIES),
        transfer_strategies=cfg.get("transfer_strategies")
        or list(DEFAULT_TRANSFER_STRATEGIES),
        n_init=int(cfg.get("n_init", 5)),
        budget=int(cfg.get("budget", 20)),
        out_dir=out_dir,
        strategy_kwargs=sk,
        skip_existing=args.skip_existing,
        workers=args.workers,
        dry_run=args.dry_run,
        substrate_descriptor=str(cfg.get("substrate_descriptor", "hashed_smiles_v1")),
        condition_features=str(cfg.get("condition_features", "ohe")),
        dft_csv=cfg.get("dft_csv"),
    )
    if not args.dry_run and not summary.empty:
        print(summary.groupby("strategy")[["auc", "final_best", "hit10_top5pct"]].mean())
    print(f"Wrote {out_dir}")


if __name__ == "__main__":
    main()
