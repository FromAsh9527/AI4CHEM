#!/usr/bin/env python
"""Run single-plate baseline suite (W1–2).

By default only uses protocol.dev_targets (skips held-out unless --allow-heldout).

Examples:
  python scripts/run_baseline_suite.py --dry-run
  python scripts/run_baseline_suite.py --seeds 0,1,2
  python scripts/run_baseline_suite.py --all-seeds
  python scripts/run_baseline_suite.py --all-seeds --reps morgan,drfp --strategies cold_diversity --no-random --skip-existing
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from run_experiment import run_one  # noqa: E402
from transferbo.utils import ensure_dir, load_config, save_json  # noqa: E402
from transferbo.utils.protocol import (  # noqa: E402
    apply_protocol,
    assert_not_tuning_heldout,
    load_protocol,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Baseline suite runner")
    parser.add_argument("--config", type=Path, default=ROOT / "configs" / "baseline.yaml")
    parser.add_argument("--protocol", type=Path, default=ROOT / "configs" / "protocol.yaml")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--seeds", type=str, default="0", help="Comma list, e.g. 0,1,2")
    parser.add_argument("--all-seeds", action="store_true")
    parser.add_argument("--allow-heldout", action="store_true")
    parser.add_argument("--targets", type=str, default=None)
    parser.add_argument(
        "--reps",
        type=str,
        default="ohe,morgan",
        help="Comma list of representations for BO strategies",
    )
    parser.add_argument(
        "--strategies",
        type=str,
        default=None,
        help="Comma list of BO strategies, e.g. cold_start,cold_diversity",
    )
    parser.add_argument("--no-random", action="store_true")
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip jobs whose output JSON already exists",
    )
    args = parser.parse_args(argv)

    cfg = apply_protocol(load_config(args.config), load_protocol(args.protocol))
    protocol = load_protocol(args.protocol)

    if args.targets:
        targets = [t.strip() for t in args.targets.split(",") if t.strip()]
    else:
        targets = list(protocol.get("dev_targets") or ["plate_1", "plate_2", "plate_3"])

    representations = [r.strip() for r in args.reps.split(",") if r.strip()]
    bo_strategies = (
        [s.strip() for s in args.strategies.split(",") if s.strip()]
        if args.strategies
        else ["cold_start"]
    )
    seeds = (
        list(cfg.get("seeds", list(range(20))))
        if args.all_seeds
        else [int(s) for s in args.seeds.split(",") if s.strip() != ""]
    )

    jobs: list[tuple[str, str, str, int]] = []
    for target in targets:
        assert_not_tuning_heldout(
            target=target,
            protocol=protocol,
            allow_heldout_eval=args.allow_heldout,
            purpose="baseline",
        )
        for seed in seeds:
            if not args.no_random:
                jobs.append(("random", "morgan", target, seed))
            for strat in bo_strategies:
                for rep in representations:
                    jobs.append((strat, rep, target, seed))

    out_root = ensure_dir(
        Path(cfg.get("experiment", {}).get("output_dir", "results/baseline")) / "suite"
    )
    if args.skip_existing:
        before = len(jobs)
        jobs = [
            (strat, rep, target, seed)
            for strat, rep, target, seed in jobs
            if not (out_root / f"{strat}__{rep}__{target}__seed{seed}.json").exists()
        ]
        print(f"Jobs: {len(jobs)} remaining / {before} total (skip-existing)", flush=True)
    else:
        print(f"Jobs: {len(jobs)}", flush=True)

    if args.dry_run:
        for j in jobs[:15]:
            print(" ", j)
        if len(jobs) > 15:
            print(f"  ... +{len(jobs) - 15} more")
        return 0

    for i, (strat, rep, target, seed) in enumerate(jobs, 1):
        print(f"[{i}/{len(jobs)}] {strat} | {rep} | {target} | seed={seed}", flush=True)
        run_cfg = dict(cfg)
        run_cfg["representation"] = dict(cfg.get("representation", {}))
        run_cfg["representation"]["name"] = rep
        run_cfg["strategy"] = dict(cfg.get("strategy", {}))
        run_cfg["strategy"]["name"] = strat
        rec = run_one(run_cfg, strategy_name=strat, source=None, target=target, seed=seed)
        save_json(rec, out_root / f"{strat}__{rep}__{target}__seed{seed}.json")

    all_rows = []
    for p in out_root.glob("*.json"):
        if p.name.startswith("index"):
            continue
        parts = p.stem.split("__")
        if len(parts) != 4:
            continue
        strat, rep, target, seed_s = parts
        d = json.loads(p.read_text(encoding="utf-8"))
        all_rows.append(
            {
                "strategy": strat,
                "representation": rep,
                "target": target,
                "seed": int(seed_s.replace("seed", "")),
                "queries_to_top5": d.get("metrics", {}).get("queries_to_top5"),
                "best_final": d.get("best_final"),
                "path": str(p),
            }
        )
    pd.DataFrame(all_rows).to_csv(out_root / "baseline_index.csv", index=False)
    print(f"Done. Index at {out_root / 'baseline_index.csv'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
