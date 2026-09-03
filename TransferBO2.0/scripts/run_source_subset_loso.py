#!/usr/bin/env python
"""Run LOSO with restricted historical source subsets (P1 BO track).

Uses subset_replicate=0 only (one fixed subset per target × n_sources).

  python scripts/run_source_subset_loso.py --config configs/amination_p1_source_robustness_hpc.yaml --dry-run
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
import yaml

from transferbo2.benchmarks.protocols import run_loso_once
from transferbo2.benchmarks.source_subset import sample_source_subset
from transferbo2.data.database import connect, experiments_frame
from transferbo2.strategies.base import StrategyConfig

ROOT = Path(__file__).resolve().parents[1]


def subset_job_path(
    out_root: Path, strategy: str, target: str, n_s: str, subset_rep: int, seed: int
) -> Path:
    return out_root / f"{strategy}__ns{n_s}__rep{subset_rep}__{target}__seed{seed}.json"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--skip-existing", action="store_true")
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--target", type=str, default=None, help="Single target substrate")
    args = p.parse_args()

    cfg = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    out_dir = Path(cfg["out_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    db = cfg.get("db", "data/db/transferbo2.db")
    with connect(db) as conn:
        df = experiments_frame(conn)

    targets = cfg.get("target_substrates") or sorted(df["substrate_id"].unique())
    if args.target:
        targets = [args.target]

    seeds = [int(s) for s in (cfg.get("seeds") or [0, 1, 2, 3, 4])]
    if args.seed is not None:
        seeds = [int(args.seed)]

    strategies = cfg.get("strategies") or ["topk_warm", "cold_start", "random"]
    bo_ns = [str(x) for x in (cfg.get("bo_source_counts") or ["1", "3", "all"])]
    subset_seed_base = int(cfg.get("subset_seed_base", 0))
    subset_rep = 0

    sk = {
        "acquisition": cfg.get("acquisition", "ei"),
        "topk": int(cfg.get("topk", 5)),
        "max_warm_points": int(cfg.get("max_warm_points", 100)),
        "gate_spearman_min": float(cfg.get("gate_spearman_min", 0.15)),
        "use_plate_correction": bool(cfg.get("use_plate_correction", False)),
        "warm_strength": float(cfg.get("warm_strength", 0.5)),
        "lengthscale_sub": float(cfg.get("lengthscale_sub", 1.0)),
    }

    jobs = []
    for target in targets:
        all_sources = [s for s in sorted(df["substrate_id"].unique()) if s != target]
        for n_s in bo_ns:
            subset = sample_source_subset(
                all_sources, n_s, subset_seed=subset_seed_base + subset_rep, target=target
            )
            for strat in strategies:
                for seed in seeds:
                    jobs.append((target, n_s, subset, strat, seed))

    print(f"Total jobs: {len(jobs)}", flush=True)
    if args.dry_run:
        for row in jobs[:15]:
            print(" ", row[:4], f"seed={row[4]}", flush=True)
        if len(jobs) > 15:
            print(f"  ... ({len(jobs) - 15} more)", flush=True)
        return

    from transferbo2.benchmarks.protocols import _desc_map, _load_condition_matrix

    with connect(db) as conn:
        desc = _desc_map(conn, name=cfg.get("substrate_descriptor", "hashed_smiles_v1"))
        dft_matrix = _load_condition_matrix(
            conn,
            condition_features=cfg.get("condition_features", "ohe"),
            dft_csv=cfg.get("dft_csv"),
        )

    rows = []
    for target, n_s, subset, strat, seed in jobs:
        dest = subset_job_path(out_dir, strat, target, n_s, subset_rep, seed)
        if args.skip_existing and dest.exists():
            continue
        scfg = StrategyConfig(
            n_init=int(cfg.get("n_init", 5)),
            budget=int(cfg.get("budget", 20)),
            seed=seed,
            **sk,
        )
        rec = run_loso_once(
            df,
            desc,
            target_substrate=target,
            strategy_name=strat,
            config=scfg,
            condition_features=cfg.get("condition_features", "ohe"),
            dft_matrix=dft_matrix,
            history_substrates=subset,
        )
        rec["meta"] = {
            **(rec.get("meta") or {}),
            "n_sources": n_s,
            "subset_replicate": subset_rep,
            "history_substrates": list(subset),
        }
        dest.write_text(json.dumps(rec, indent=2), encoding="utf-8")
        rows.append(
            {
                "strategy": strat,
                "target_substrate": target,
                "seed": seed,
                "n_sources": n_s,
                "auc": rec["stats"]["auc"],
                "final_best": rec["stats"]["final_best"],
            }
        )

    if rows:
        summary = pd.DataFrame(rows)
        summary.to_csv(out_dir / "subset_loso_summary.csv", index=False)
        print(summary.groupby(["strategy", "n_sources"])["auc"].mean(), flush=True)


if __name__ == "__main__":
    main()
