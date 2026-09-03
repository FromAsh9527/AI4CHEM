#!/usr/bin/env python
"""W7: run max_warm_points sweep for label_warm (cold once, then each n_s).

Example:
  python scripts/run_nsweep_pilot.py --dry-run
  python scripts/run_nsweep_pilot.py --workers 4 --skip-existing
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from run_experiment import run_one  # noqa: E402
from run_transfer_grid import iter_jobs, job_path, rebuild_tables  # noqa: E402
from transferbo.utils import ensure_dir, load_config, save_json  # noqa: E402
from transferbo.utils.protocol import apply_protocol, load_protocol  # noqa: E402


def _limit_blas_threads() -> None:
    for key in (
        "OMP_NUM_THREADS",
        "MKL_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
    ):
        os.environ.setdefault(key, "1")


def _run_job(strat, rep, source, target, seed, cfg, out_root: str) -> str:
    _limit_blas_threads()
    dest = job_path(Path(out_root), strat, rep, source, target, seed)
    if dest.exists():
        return f"skip {dest.name}"
    run_cfg = dict(cfg)
    run_cfg["representation"] = dict(cfg.get("representation", {}))
    run_cfg["representation"]["name"] = rep
    run_cfg["strategy"] = dict(cfg.get("strategy", {}))
    run_cfg["strategy"]["name"] = strat
    rec = run_one(run_cfg, strategy_name=strat, source=source, target=target, seed=seed)
    rec["meta"] = dict(rec.get("meta") or {})
    rec["meta"]["max_warm_points_cfg"] = run_cfg.get("transfer", {}).get("max_warm_points")
    save_json(rec, dest)
    return dest.name


def _run_item(item) -> str:
    """Top-level worker for Windows spawn (must be picklable)."""
    _tag, cfg, dest, j = item
    strat, rep, source, target, seed = j
    return _run_job(strat, rep, source, target, seed, cfg, dest)


def summarize_nsweep(root: Path, budgets=(30, 40, 50)) -> pd.DataFrame:
    rows = []
    for sub in sorted(root.glob("mw_*")):
        if not sub.is_dir():
            continue
        token = sub.name  # mw_20 / mw_full
        for p in sub.glob("*.json"):
            if p.name.startswith(("grid_", "heatmap", "summary")):
                continue
            d = json.loads(p.read_text(encoding="utf-8"))
            curve = d.get("bo", {}).get("best_so_far") or []
            gbest = float(d.get("global_best") or 1.0)
            for b in budgets:
                if len(curve) < b:
                    continue
                rows.append(
                    {
                        "max_warm_token": token,
                        "strategy": d["strategy"],
                        "representation": d["representation"],
                        "source": d.get("source_plate"),
                        "target": d["target_plate"],
                        "seed": d["seed"],
                        "budget": b,
                        "frac": float(curve[b - 1]) / gbest if gbest else None,
                    }
                )
    return pd.DataFrame(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "configs" / "transfer_grid_edbo_suzuki_nsweep.yaml",
    )
    parser.add_argument("--protocol", type=Path, default=ROOT / "configs" / "protocol.yaml")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--max-runs", type=int, default=None)
    args = parser.parse_args()

    protocol = load_protocol(args.protocol)
    base = apply_protocol(load_config(args.config), protocol)
    sweep = list((base.get("nsweep") or {}).get("max_warm_points") or [150])
    out_root = ensure_dir(Path(base["experiment"]["output_dir"]))

    # cold_start once under mw_ref (independent of n_s)
    cold_cfg = copy.deepcopy(base)
    cold_cfg["grid"] = dict(base["grid"])
    cold_cfg["grid"]["strategies"] = ["cold_start"]
    cold_jobs = list(iter_jobs(cold_cfg))
    cold_dir = ensure_dir(out_root / "mw_ref_cold")

    label_jobs_by_mw = []
    for mw in sweep:
        cfg = copy.deepcopy(base)
        cfg["transfer"] = dict(base.get("transfer", {}))
        cfg["transfer"]["max_warm_points"] = int(mw)
        cfg["grid"] = dict(base["grid"])
        cfg["grid"]["strategies"] = ["label_warm"]
        token = "full" if int(mw) == 0 else str(int(mw))
        sub = ensure_dir(out_root / f"mw_{token}")
        jobs = list(iter_jobs(cfg))
        label_jobs_by_mw.append((token, cfg, sub, jobs))

    all_plan = [("cold", cold_cfg, cold_dir, cold_jobs)] + [
        (f"mw_{t}", c, d, j) for t, c, d, j in label_jobs_by_mw
    ]
    flat = []
    for tag, cfg, dest, jobs in all_plan:
        for j in jobs:
            flat.append((tag, cfg, str(dest), j))

    if args.max_runs is not None:
        flat = flat[: args.max_runs]

    if args.skip_existing:
        keep = []
        for tag, cfg, dest, j in flat:
            strat, rep, source, target, seed = j
            if not job_path(Path(dest), strat, rep, source, target, seed).exists():
                keep.append((tag, cfg, dest, j))
        print(f"Jobs remaining: {len(keep)} / {len(flat)}", flush=True)
        flat = keep
    else:
        print(f"Total jobs: {len(flat)}", flush=True)

    if args.dry_run:
        for tag, _, dest, j in flat[:30]:
            print(tag, dest, j)
        if len(flat) > 30:
            print(f"... ({len(flat) - 30} more)")
        return 0

    workers = max(1, int(args.workers))
    _limit_blas_threads()

    if workers == 1:
        for i, item in enumerate(flat, 1):
            print(f"[{i}/{len(flat)}] {item[0]} {item[3]}", flush=True)
            _run_item(item)
    else:
        done = 0
        with ProcessPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(_run_item, item): item for item in flat}
            for fut in as_completed(futs):
                done += 1
                item = futs[fut]
                try:
                    fut.result()
                except Exception as e:
                    print(f"FAIL {item}: {e}", flush=True)
                    raise
                print(f"[{done}/{len(flat)}] ok {item[0]} {item[3]}", flush=True)

    rebuild_tables(cold_dir)
    for _, _, sub, _ in label_jobs_by_mw:
        rebuild_tables(sub)

    # pair deltas vs cold at primary budgets
    long = summarize_nsweep(out_root)
    if long.empty:
        print("No curves to summarize")
        return 0
    long.to_csv(out_root / "nsweep_long.csv", index=False)

    cold = (
        long[long["strategy"] == "cold_start"]
        .groupby(["representation", "target", "seed", "budget"])["frac"]
        .mean()
        .rename("cold_frac")
    )
    lab = long[long["strategy"] == "label_warm"].copy()
    lab = lab.merge(
        cold.reset_index(),
        on=["representation", "target", "seed", "budget"],
        how="left",
    )
    lab["delta_frac"] = lab["frac"] - lab["cold_frac"]
    pair = (
        lab.groupby(
            ["max_warm_token", "representation", "source", "target", "budget"],
            as_index=False,
        )["delta_frac"]
        .mean()
    )
    pair.to_csv(out_root / "nsweep_pair_delta.csv", index=False)
    primary = (
        pair[pair["budget"].isin([30, 40, 50])]
        .groupby(["max_warm_token", "representation"], as_index=False)["delta_frac"]
        .mean()
        .rename(columns={"delta_frac": "mean_delta_frac_B30_50"})
    )
    primary.to_csv(out_root / "nsweep_primary_summary.csv", index=False)
    note = [
        "# W7 nsweep pilot summary",
        "",
        primary.round(4).to_string(index=False),
        "",
        f"Raw long table: `{out_root / 'nsweep_long.csv'}`",
        "Expand plates/seeds in config for production; 0 = full source.",
    ]
    (out_root / "NSWEEP_NOTE.md").write_text("\n".join(note), encoding="utf-8")
    # copy primary into paper_stats
    stats = ROOT / "results" / "paper_stats"
    stats.mkdir(parents=True, exist_ok=True)
    primary.to_csv(stats / "edbo_suzuki_nsweep_primary_summary.csv", index=False)
    print(primary.round(4).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
