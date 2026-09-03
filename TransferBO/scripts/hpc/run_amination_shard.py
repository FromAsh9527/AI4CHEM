#!/usr/bin/env python
"""Split EDBO amination min S0 into seed shards for array / dsub jobs.

Example:
  python scripts/hpc/run_amination_shard.py --shard-id 0 --n-shards 20 --dry-run
  python scripts/hpc/run_amination_shard.py --shard-id $SLURM_ARRAY_TASK_ID --n-shards 20 --workers 32
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shard-id", type=int, required=True)
    ap.add_argument("--n-shards", type=int, default=20)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--config",
        type=Path,
        default=ROOT / "configs" / "transfer_grid_edbo_amination_min_s0.yaml",
    )
    args = ap.parse_args()
    if not (0 <= args.shard_id < args.n_shards):
        raise SystemExit(f"shard-id must be in [0, {args.n_shards})")

    seeds = list(range(20))
    mine = [s for s in seeds if s % args.n_shards == args.shard_id]
    if not mine:
        print(f"shard {args.shard_id}: no seeds")
        return 0

    env = os.environ.copy()
    env.setdefault("PYTHONWARNINGS", "ignore")
    env.setdefault("OMP_NUM_THREADS", "1")
    env.setdefault("MKL_NUM_THREADS", "1")
    env.setdefault("OPENBLAS_NUM_THREADS", "1")
    env["PYTHONPATH"] = str(ROOT / "src") + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )

    print(f"shard={args.shard_id}/{args.n_shards} seeds={mine} workers={args.workers}")
    for seed in mine:
        cmd = [
            sys.executable,
            str(ROOT / "scripts" / "run_transfer_grid.py"),
            "--config",
            str(args.config),
            "--skip-existing",
            "--workers",
            str(args.workers),
            "--seed",
            str(seed),
        ]
        print(" ", " ".join(cmd), flush=True)
        if args.dry_run:
            continue
        subprocess.check_call(cmd, cwd=str(ROOT), env=env)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
