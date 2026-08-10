#!/usr/bin/env python
"""Compare CHAOS transfer deltas: xTB vs fingerprint reps (Morgan/DRFP).

Reads results/transfer_grid_xtb and an existing fingerprint grid (default
results/transfer_grid), prints sign-consistency of label_warm / diversity_warm
vs cold_start on the 6 development pairs.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def load_grid(path: Path) -> pd.DataFrame:
    csv = path / "grid_results.csv"
    if not csv.is_file():
        raise FileNotFoundError(csv)
    return pd.read_csv(csv)


def pair_deltas(df: pd.DataFrame, rep: str) -> pd.DataFrame:
    sub = df[df["representation"] == rep].copy()
    cold = (
        sub[sub["strategy"] == "cold_start"]
        .groupby("target_plate")["frac_of_opt"]
        .mean()
    )
    rows = []
    for (src, tgt, strat), g in sub.groupby(
        ["source_plate", "target_plate", "strategy"]
    ):
        if strat == "cold_start":
            continue
        if src == tgt:
            continue
        val = g["frac_of_opt"].mean()
        base = cold.get(tgt, np.nan)
        rows.append(
            {
                "source": src,
                "target": tgt,
                "strategy": strat,
                "frac_mean": val,
                "cold_frac_mean": base,
                "delta_vs_cold": val - base if pd.notna(base) else np.nan,
                "n": len(g),
            }
        )
    return pd.DataFrame(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--xtb", type=Path, default=ROOT / "results" / "transfer_grid_xtb")
    ap.add_argument(
        "--fp-grid",
        type=Path,
        default=ROOT / "results" / "transfer_grid",
        help="fingerprint grid root with grid_results.csv",
    )
    ap.add_argument("--fp-reps", nargs="+", default=["morgan", "drfp"])
    ap.add_argument(
        "--out",
        type=Path,
        default=ROOT / "results" / "paper_stats" / "chaos_xtb_descriptor_ablation.csv",
    )
    args = ap.parse_args()

    xtb_df = load_grid(args.xtb)
    xtb = pair_deltas(xtb_df, "xtb")
    xtb["representation"] = "xtb"

    frames = [xtb]
    fp_grid = load_grid(args.fp_grid)
    for rep in args.fp_reps:
        if rep not in set(fp_grid["representation"]):
            print(f"skip missing rep in fp grid: {rep}")
            continue
        d = pair_deltas(fp_grid, rep)
        d["representation"] = rep
        frames.append(d)

    all_d = pd.concat(frames, ignore_index=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    all_d.to_csv(args.out, index=False)

    print("=== mean Δfrac vs cold (6 pairs) ===")
    summ = (
        all_d.groupby(["representation", "strategy"])["delta_vs_cold"]
        .agg(["mean", "median", "min", "max", "count"])
        .round(4)
    )
    print(summ.to_string())

    # sign consistency: label > 0 and diversity < 0 on average per pair
    print("\n=== per-pair signs (label / diversity) ===")
    for rep in all_d["representation"].unique():
        sub = all_d[all_d["representation"] == rep]
        lab = sub[sub["strategy"] == "label_warm"].set_index(["source", "target"])[
            "delta_vs_cold"
        ]
        div = sub[sub["strategy"] == "diversity_warm"].set_index(["source", "target"])[
            "delta_vs_cold"
        ]
        pairs = sorted(set(lab.index) | set(div.index))
        n_lab_pos = sum(1 for p in pairs if p in lab.index and lab[p] > 0)
        n_div_neg = sum(1 for p in pairs if p in div.index and div[p] < 0)
        print(
            f"{rep}: label>0 {n_lab_pos}/{len(lab)}; "
            f"diversity<0 {n_div_neg}/{len(div)}; "
            f"mean_label={lab.mean():+.3f}; mean_div={div.mean():+.3f}"
        )

    # label vs diversity (same as label − cold_diversity on this library)
    print("\n=== mean (label − diversity) ≡ label vs cold_diversity ===")
    for rep in all_d["representation"].unique():
        sub = all_d[all_d["representation"] == rep]
        merged = sub[sub["strategy"] == "label_warm"][
            ["source", "target", "delta_vs_cold"]
        ].merge(
            sub[sub["strategy"] == "diversity_warm"][
                ["source", "target", "delta_vs_cold"]
            ],
            on=["source", "target"],
            suffixes=("_lab", "_div"),
        )
        d = merged["delta_vs_cold_lab"] - merged["delta_vs_cold_div"]
        print(
            f"{rep}: mean={d.mean():+.3f}; min={d.min():+.3f}; "
            f"all_pos={bool((d > 0).all())} n={len(d)}"
        )

    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
