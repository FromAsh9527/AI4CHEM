#!/usr/bin/env python
"""Amination topk ablation + topk_safe_gate (post-FROZEN step 2).

Runs:
  - baselines: random, cold_start (once)
  - topk_warm for each k in topk_grid (job tag strategy name topk_warm_k{k})
  - topk_safe_gate at default topk=5

Example:
  python scripts/run_amination_topk_ablation.py --dry-run
  python scripts/run_amination_topk_ablation.py --skip-existing --workers 1
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from transferbo2.benchmarks.protocols import (  # noqa: E402
    _desc_map,
    _limit_blas_threads,
    _write_job_json,
    loso_job_path,
    rebuild_loso_summary,
    run_loso_once,
)
from transferbo2.data.database import connect, experiments_frame  # noqa: E402
from transferbo2.strategies.base import StrategyConfig  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--config",
        type=Path,
        default=ROOT / "configs" / "amination_topk_ablation.yaml",
    )
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip-existing", action="store_true")
    ap.add_argument("--workers", type=int, default=1, help="reserved; sequential for now")
    args = ap.parse_args()

    for k in (
        "OMP_NUM_THREADS",
        "MKL_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    ):
        os.environ.setdefault(k, "1")
    os.environ.setdefault("PYTHONWARNINGS", "ignore")

    cfg = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    out = Path(cfg.get("out_dir", "results/amination_topk_ablation"))
    out.mkdir(parents=True, exist_ok=True)

    sk_base = {
        "acquisition": cfg.get("acquisition", "ei"),
        "max_warm_points": int(cfg.get("max_warm_points", 100)),
        "gate_spearman_min": float(cfg.get("gate_spearman_min", 0.15)),
        "use_plate_correction": bool(cfg.get("use_plate_correction", False)),
        "warm_strength": float(cfg.get("warm_strength", 0.5)),
        "lengthscale_sub": float(cfg.get("lengthscale_sub", 1.0)),
        "gate_sim_min": float(cfg.get("gate_sim_min", 0.15)),
    }
    n_init = int(cfg.get("n_init", 5))
    budget = int(cfg.get("budget", 20))
    seeds = [int(s) for s in (cfg.get("seeds") or [0, 1, 2, 3, 4])]
    topk_grid = [int(k) for k in (cfg.get("topk_grid") or [1, 3, 5, 10])]
    baselines = list(cfg.get("baseline_strategies") or ["random", "cold_start"])
    gate_name = cfg.get("gate_strategy", "topk_safe_gate")

    with connect(cfg.get("db")) as conn:
        df = experiments_frame(conn)
        desc = _desc_map(conn)
    targets = cfg.get("target_substrates") or sorted(df["substrate_id"].unique())

    # jobs: (strategy_name_for_file, real_strategy, topk, target, seed)
    jobs = []
    for sid in targets:
        for seed in seeds:
            for name in baselines:
                jobs.append((name, name, 5, sid, seed))
            for k in topk_grid:
                tag = f"topk_warm_k{k}"
                jobs.append((tag, "topk_warm", k, sid, seed))
            jobs.append((gate_name, gate_name, 5, sid, seed))

    total = len(jobs)
    if args.skip_existing:
        jobs = [
            j
            for j in jobs
            if not loso_job_path(out, j[0], j[3], j[4]).exists()
        ]
        print(f"Total jobs: {len(jobs)} remaining / {total} (skip-existing)", flush=True)
    else:
        print(f"Total jobs: {total}", flush=True)

    if args.dry_run:
        for j in jobs[:15]:
            print(" ", j, flush=True)
        if len(jobs) > 15:
            print(f"  ... ({len(jobs) - 15} more)", flush=True)
        return 0

    _limit_blas_threads()
    for i, (tag, real, topk, sid, seed) in enumerate(jobs, 1):
        dest = loso_job_path(out, tag, sid, seed)
        if args.skip_existing and dest.exists():
            continue
        print(
            f"[{i}/{len(jobs)}] {tag}  target={sid}  seed={seed}  topk={topk}",
            flush=True,
        )
        sc = StrategyConfig(
            n_init=n_init, budget=budget, seed=int(seed), topk=int(topk), **sk_base
        )
        rec = run_loso_once(
            df, desc, target_substrate=sid, strategy_name=real, config=sc
        )
        rec["strategy"] = tag  # ensure summary uses ablation tag
        _write_job_json(dest, rec)

    summary = rebuild_loso_summary(out)
    # rebuild reads strategy from JSON — we wrote tag into rec["strategy"]
    print(summary.groupby("strategy")[["auc", "final_best", "hit10_top5pct"]].mean())
    (out / "ablation_meta.json").write_text(
        json.dumps(
            {"topk_grid": topk_grid, "gate": gate_name, "n_jobs_planned": total},
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
