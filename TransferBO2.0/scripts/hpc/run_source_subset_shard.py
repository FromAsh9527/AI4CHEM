#!/usr/bin/env python
"""Seed-shard runner for P1 source-subset LOSO (HPC dsub).

  python scripts/hpc/run_source_subset_shard.py \\
      --config configs/amination_p1_source_robustness_hpc.yaml \\
      --shard-id 0 --n-shards 5 --dry-run
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--shard-id", type=int, required=True)
    ap.add_argument("--n-shards", type=int, default=5)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if not (0 <= args.shard_id < args.n_shards):
        raise SystemExit(f"shard-id must be in [0, {args.n_shards})")

    cfg_path = args.config if args.config.is_absolute() else ROOT / args.config
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    seeds = [int(s) for s in (cfg.get("seeds") or [0, 1, 2, 3, 4])]
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

    print(
        f"config={cfg_path.name} shard={args.shard_id}/{args.n_shards} "
        f"seeds={mine} workers={args.workers}",
        flush=True,
    )
    for seed in mine:
        cmd = [
            sys.executable,
            str(ROOT / "scripts" / "run_source_subset_loso.py"),
            "--config",
            str(cfg_path),
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
