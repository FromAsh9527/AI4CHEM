#!/usr/bin/env python
"""Summarize EDBO DFT validation grids vs cold (frac + absolute yield)."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def summarize(grid_csv: Path, name: str) -> pd.DataFrame:
    df = pd.read_csv(grid_csv)
    cold = (
        df[df.strategy == "cold_start"]
        .groupby("target_plate")
        .agg(cold_frac=("frac_of_opt", "mean"), cold_best=("best_final", "mean"))
    )
    rows = []
    for (src, tgt, strat, rep), g in df.groupby(
        ["source_plate", "target_plate", "strategy", "representation"]
    ):
        if strat == "cold_start":
            continue
        rows.append(
            {
                "dataset": name,
                "source": src,
                "target": tgt,
                "strategy": strat,
                "rep": rep,
                "frac_mean": g.frac_of_opt.mean(),
                "best_mean": g.best_final.mean(),
                "cold_frac": cold.loc[tgt, "cold_frac"],
                "cold_best": cold.loc[tgt, "cold_best"],
                "delta_frac": g.frac_of_opt.mean() - cold.loc[tgt, "cold_frac"],
                "delta_yield": g.best_final.mean() - cold.loc[tgt, "cold_best"],
                "n": len(g),
            }
        )
    return pd.DataFrame(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--suzuki",
        type=Path,
        default=ROOT / "results/external_edbo_suzuki/grid_results.csv",
    )
    ap.add_argument(
        "--amination",
        type=Path,
        default=ROOT / "results/external_edbo_amination/grid_results.csv",
    )
    ap.add_argument(
        "--suzuki-only",
        action="store_true",
        help="Summarize Suzuki grid only (skip amination even if present).",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=ROOT / "results/paper_stats/edbo_validation_summary.csv",
    )
    args = ap.parse_args()

    frames = []
    paths = [(args.suzuki, "suzuki")]
    if not args.suzuki_only:
        paths.append((args.amination, "amination"))
    for path, name in paths:
        if not path.is_file():
            print(f"missing {path}")
            continue
        frames.append(summarize(path, name))

    if not frames:
        print("no grids yet")
        return 1
    all_df = pd.concat(frames, ignore_index=True)
    if args.suzuki_only:
        args.out = args.out.with_name("edbo_suzuki_validation_summary.csv")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    all_df.to_csv(args.out, index=False)

    print("=== overall mean Δ (pairs) by representation ===")
    ov = (
        all_df.groupby(["dataset", "rep", "strategy"])[["delta_frac", "delta_yield"]]
        .agg(["mean", "median"])
        .round(4)
    )
    print(ov.to_string())
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
