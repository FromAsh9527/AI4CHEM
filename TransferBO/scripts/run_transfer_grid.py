#!/usr/bin/env python
"""Run transfer / warm-start grid (W3).

Examples:
  python scripts/run_transfer_grid.py --dry-run
  python scripts/run_transfer_grid.py --seed 0
  python scripts/run_transfer_grid.py --skip-existing
  python scripts/run_transfer_grid.py --skip-existing --workers 14
"""

from __future__ import annotations

import argparse
import itertools
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
from transferbo.metrics.transfer import pivot_gain, transfer_gain_matrix  # noqa: E402
from transferbo.utils import ensure_dir, load_config, save_json  # noqa: E402
from transferbo.utils.protocol import (  # noqa: E402
    apply_protocol,
    assert_not_tuning_heldout,
    load_protocol,
)


def _limit_blas_threads() -> None:
    """Avoid oversubscription when many workers each call sklearn."""
    for key in (
        "OMP_NUM_THREADS",
        "MKL_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
    ):
        os.environ.setdefault(key, "1")


def _run_one_job(
    strat: str,
    rep: str,
    source: str | None,
    target: str,
    seed: int,
    cfg: dict,
    out_root: str,
) -> str:
    """Worker entry (must be top-level for Windows spawn)."""
    _limit_blas_threads()
    out = Path(out_root)
    dest = job_path(out, strat, rep, source, target, seed)
    if dest.exists():
        return f"skip {dest.name}"
    run_cfg = dict(cfg)
    run_cfg["representation"] = dict(cfg.get("representation", {}))
    run_cfg["representation"]["name"] = rep
    run_cfg["strategy"] = dict(cfg.get("strategy", {}))
    run_cfg["strategy"]["name"] = strat
    rec = run_one(
        run_cfg, strategy_name=strat, source=source, target=target, seed=seed
    )
    save_json(rec, dest)
    return dest.name


def iter_jobs(cfg: dict):
    grid = cfg.get("grid", {})
    strategies = grid.get("strategies", ["cold_start"])
    representations = grid.get("representations", ["morgan"])
    plates = grid.get("plates", ["plate_1"])
    include_same = bool(grid.get("include_same_plate", False))
    seeds = cfg.get("seeds", [0])

    for strat, rep, target, seed in itertools.product(
        strategies, representations, plates, seeds
    ):
        if strat in ("cold_start", "random"):
            yield strat, rep, None, target, seed
            continue
        for source in plates:
            if source == target and not include_same:
                continue
            yield strat, rep, source, target, seed


def job_path(out_root: Path, strat: str, rep: str, source: str | None, target: str, seed: int) -> Path:
    return out_root / f"{strat}__{rep}__{source or 'none'}__{target}__seed{seed}.json"


def rebuild_tables(out_root: Path) -> None:
    rows = []
    for p in out_root.glob("*.json"):
        if p.name.startswith("grid_") or p.name.startswith("heatmap") or p.name.startswith("summary"):
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        rows.append(
            {
                "source_plate": d.get("source_plate") or d.get("target_plate"),
                "target_plate": d["target_plate"],
                "strategy": d["strategy"],
                "representation": d["representation"],
                "seed": d["seed"],
                "queries_to_top5": d.get("metrics", {}).get("queries_to_top5"),
                "queries_to_top1": d.get("metrics", {}).get("queries_to_top1"),
                "best_final": d.get("best_final"),
                "global_best": d.get("global_best"),
                "frac_of_opt": (
                    d["best_final"] / d["global_best"]
                    if d.get("global_best")
                    else None
                ),
            }
        )
    if not rows:
        return
    df = pd.DataFrame(rows)
    df.to_csv(out_root / "grid_results.csv", index=False)

    # gain on queries_to_top5 (lower queries => higher gain)
    agg_q = (
        df.groupby(
            ["source_plate", "target_plate", "strategy", "representation"], as_index=False
        )["queries_to_top5"].median()
    )
    gain_q = transfer_gain_matrix(agg_q.to_dict(orient="records"), value_key="queries_to_top5")
    if not gain_q.empty:
        gain_q.to_csv(out_root / "transfer_gain_queries.csv", index=False)

    # alternative: mean frac_of_opt (higher better) — report delta vs cold
    cold = (
        df[df["strategy"] == "cold_start"]
        .groupby(["target_plate", "representation"])["frac_of_opt"]
        .mean()
    )
    rows2 = []
    for (src, tgt, strat, rep), g in df.groupby(
        ["source_plate", "target_plate", "strategy", "representation"]
    ):
        if strat == "cold_start":
            continue
        base = cold.get((tgt, rep), float("nan"))
        val = g["frac_of_opt"].mean()
        rows2.append(
            {
                "source_plate": src,
                "target_plate": tgt,
                "strategy": strat,
                "representation": rep,
                "frac_mean": val,
                "cold_frac_mean": base,
                "delta_vs_cold": val - base if pd.notna(base) and pd.notna(val) else None,
            }
        )
    if rows2:
        delta = pd.DataFrame(rows2)
        delta.to_csv(out_root / "transfer_delta_frac.csv", index=False)
        for strat in sorted(delta["strategy"].unique()):
            for rep in sorted(delta["representation"].unique()):
                sub = delta[(delta["strategy"] == strat) & (delta["representation"] == rep)]
                if sub.empty:
                    continue
                mat = sub.pivot_table(
                    index="source_plate", columns="target_plate", values="delta_vs_cold"
                )
                mat.to_csv(out_root / f"heatmap_delta_{strat}_{rep}.csv")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="TransferBO grid runner")
    parser.add_argument("--config", type=Path, default=ROOT / "configs" / "transfer_grid.yaml")
    parser.add_argument("--protocol", type=Path, default=ROOT / "configs" / "protocol.yaml")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-runs", type=int, default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--allow-heldout", action="store_true")
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Parallel processes (set >1 to saturate CPU; each worker uses 1 BLAS thread).",
    )
    args = parser.parse_args(argv)

    protocol = load_protocol(args.protocol)
    cfg = apply_protocol(load_config(args.config), protocol)
    jobs = list(iter_jobs(cfg))
    if args.seed is not None:
        jobs = [j for j in jobs if j[4] == args.seed]
    if args.max_runs is not None:
        jobs = jobs[: args.max_runs]

    out_root = ensure_dir(
        Path(cfg.get("experiment", {}).get("output_dir", "results/transfer_grid"))
    )

    if args.skip_existing:
        before = len(jobs)
        jobs = [
            j
            for j in jobs
            if not job_path(out_root, j[0], j[1], j[2], j[3], j[4]).exists()
        ]
        print(f"Total jobs: {len(jobs)} remaining / {before} (skip-existing)", flush=True)
    else:
        print(f"Total jobs: {len(jobs)}", flush=True)

    for _, _, _, target, _ in jobs:
        assert_not_tuning_heldout(
            target=target,
            protocol=protocol,
            allow_heldout_eval=args.allow_heldout,
            purpose="transfer_grid",
        )

    if args.dry_run:
        for j in jobs[:20]:
            print(" ", j)
        if len(jobs) > 20:
            print(f"  ... ({len(jobs) - 20} more)")
        return 0

    workers = max(1, int(args.workers))
    print(f"Workers: {workers}", flush=True)

    if workers == 1:
        _limit_blas_threads()
        for i, (strat, rep, source, target, seed) in enumerate(jobs, 1):
            print(
                f"[{i}/{len(jobs)}] {strat} | {rep} | {source} -> {target} | seed={seed}",
                flush=True,
            )
            _run_one_job(strat, rep, source, target, seed, cfg, str(out_root))
    else:
        _limit_blas_threads()
        done = 0
        with ProcessPoolExecutor(max_workers=workers) as ex:
            futs = {
                ex.submit(
                    _run_one_job, strat, rep, source, target, seed, cfg, str(out_root)
                ): (strat, rep, source, target, seed)
                for strat, rep, source, target, seed in jobs
            }
            for fut in as_completed(futs):
                strat, rep, source, target, seed = futs[fut]
                done += 1
                try:
                    _ = fut.result()
                except Exception as e:
                    print(
                        f"[{done}/{len(jobs)}] FAIL {strat}|{rep}|{source}->{target}|seed={seed}: {e}",
                        flush=True,
                    )
                    raise
                print(
                    f"[{done}/{len(jobs)}] {strat} | {rep} | {source} -> {target} | seed={seed}",
                    flush=True,
                )

    rebuild_tables(out_root)
    print(f"Done. Results in {out_root}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
