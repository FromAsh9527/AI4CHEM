#!/usr/bin/env python
"""Statistical summaries for main grid + SI (CIs, paired deltas).

Writes:
  results/stats/transfer_dev_stats.csv
  results/stats/si_ucb_vs_ei.csv
  results/stats/si_source_frac.csv
  results/stats/STATS_REPORT.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def bootstrap_ci(x: np.ndarray, *, n_boot: int = 2000, seed: int = 0, alpha: float = 0.05):
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) == 0:
        return np.nan, np.nan, np.nan
    rng = np.random.default_rng(seed)
    means = []
    for _ in range(n_boot):
        means.append(float(np.mean(rng.choice(x, size=len(x), replace=True))))
    lo, hi = np.quantile(means, [alpha / 2, 1 - alpha / 2])
    return float(np.mean(x)), float(lo), float(hi)


def paired_delta_ci(a: np.ndarray, b: np.ndarray, **kw):
    """CI for mean(a-b); a,b aligned by seed order."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    d = a - b
    return bootstrap_ci(d, **kw)


def load_grid(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def stats_dev_transfer(grid: pd.DataFrame) -> pd.DataFrame:
    cold = (
        grid[grid["strategy"] == "cold_start"]
        .groupby(["target_plate", "representation", "seed"])["frac_of_opt"]
        .mean()
        .rename("cold_frac")
        .reset_index()
    )
    rows = []
    transfer = grid[grid["strategy"].isin(["diversity_warm", "label_warm", "multitask"])]
    for (strat, rep, src, tgt), g in transfer.groupby(
        ["strategy", "representation", "source_plate", "target_plate"]
    ):
        if src == tgt:
            continue
        m = g.merge(cold, on=["target_plate", "representation", "seed"], how="inner")
        if m.empty:
            continue
        mean, lo, hi = paired_delta_ci(m["frac_of_opt"].to_numpy(), m["cold_frac"].to_numpy())
        rows.append(
            {
                "strategy": strat,
                "representation": rep,
                "source": src,
                "target": tgt,
                "n": len(m),
                "frac_mean": float(m["frac_of_opt"].mean()),
                "cold_mean": float(m["cold_frac"].mean()),
                "delta_mean": mean,
                "delta_ci95_lo": lo,
                "delta_ci95_hi": hi,
                "sign_stable": (lo > 0) or (hi < 0),
                "positive": bool(lo > 0),
                "negative": bool(hi < 0),
            }
        )
    return pd.DataFrame(rows)


def overall_by_strategy(dev: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for strat, g in dev.groupby("strategy"):
        mean, lo, hi = bootstrap_ci(g["delta_mean"].to_numpy())
        rows.append(
            {
                "strategy": strat,
                "n_cells": len(g),
                "mean_delta": mean,
                "ci95_lo": lo,
                "ci95_hi": hi,
                "n_pos_stable": int(g["positive"].sum()),
                "n_neg_stable": int(g["negative"].sum()),
                "n_unstable": int((~g["sign_stable"]).sum()),
            }
        )
    return pd.DataFrame(rows)


def si_ucb_compare(si_dir: Path, grid: pd.DataFrame) -> pd.DataFrame:
    ucb_path = si_dir / "ucb_results.csv"
    if not ucb_path.exists():
        return pd.DataFrame()
    ucb = pd.read_csv(ucb_path)
    rows = []
    # cold under UCB
    cold_u = (
        ucb[ucb["strategy"] == "cold_start"]
        .groupby(["target_plate", "seed"])["frac_of_opt"]
        .mean()
        .rename("cold_ucb")
        .reset_index()
    )
    cold_e = (
        grid[grid["strategy"] == "cold_start"]
        .groupby(["target_plate", "representation", "seed"])["frac_of_opt"]
        .mean()
        .rename("cold_ei")
        .reset_index()
    )
    for (strat, src, tgt), g in ucb[ucb["strategy"] != "cold_start"].groupby(
        ["strategy", "source_plate", "target_plate"]
    ):
        mu = g.merge(cold_u, on=["target_plate", "seed"], how="inner")
        if mu.empty:
            continue
        d_u, lo_u, hi_u = paired_delta_ci(mu["frac_of_opt"].to_numpy(), mu["cold_ucb"].to_numpy())
        # EI counterpart from main grid
        ei = grid[
            (grid["strategy"] == strat)
            & (grid["source_plate"] == src)
            & (grid["target_plate"] == tgt)
            & (grid["representation"] == "morgan")
        ]
        ei = ei.merge(
            cold_e[cold_e["representation"] == "morgan"],
            on=["target_plate", "seed"],
            how="inner",
        )
        if ei.empty:
            d_e = lo_e = hi_e = np.nan
        else:
            d_e, lo_e, hi_e = paired_delta_ci(ei["frac_of_opt"].to_numpy(), ei["cold_ei"].to_numpy())
        rows.append(
            {
                "strategy": strat,
                "source": src,
                "target": tgt,
                "n_ucb": len(mu),
                "delta_ucb": d_u,
                "delta_ucb_ci_lo": lo_u,
                "delta_ucb_ci_hi": hi_u,
                "delta_ei": d_e,
                "delta_ei_ci_lo": lo_e,
                "delta_ei_ci_hi": hi_e,
                "sign_flip": bool(
                    np.isfinite(d_u)
                    and np.isfinite(d_e)
                    and ((d_u > 0 and d_e < 0) or (d_u < 0 and d_e > 0))
                ),
            }
        )
    return pd.DataFrame(rows)


def si_frac_table(si_dir: Path, grid: pd.DataFrame) -> pd.DataFrame:
    path = si_dir / "source_frac_results.csv"
    if not path.exists():
        return pd.DataFrame()
    sf = pd.read_csv(path)
    cold = (
        grid[
            (grid["strategy"] == "cold_start")
            & (grid["representation"] == "morgan")
        ]
        .groupby(["target_plate", "seed"])["frac_of_opt"]
        .mean()
        .rename("cold")
        .reset_index()
    )
    rows = []
    for (src, tgt, frac), g in sf.groupby(["source_plate", "target_plate", "source_fraction"]):
        m = g.merge(cold, on=["target_plate", "seed"], how="inner")
        if m.empty:
            continue
        d, lo, hi = paired_delta_ci(m["frac_of_opt"].to_numpy(), m["cold"].to_numpy())
        rows.append(
            {
                "source": src,
                "target": tgt,
                "source_fraction": frac,
                "n": len(m),
                "frac_mean": float(m["frac_of_opt"].mean()),
                "delta_vs_cold": d,
                "delta_ci_lo": lo,
                "delta_ci_hi": hi,
            }
        )
    # also attach frac=1.0 from main grid for the same pairs
    for src, tgt in sf[["source_plate", "target_plate"]].drop_duplicates().itertuples(index=False):
        ei = grid[
            (grid["strategy"] == "label_warm")
            & (grid["representation"] == "morgan")
            & (grid["source_plate"] == src)
            & (grid["target_plate"] == tgt)
        ].merge(cold, on=["target_plate", "seed"], how="inner")
        if ei.empty:
            continue
        d, lo, hi = paired_delta_ci(ei["frac_of_opt"].to_numpy(), ei["cold"].to_numpy())
        rows.append(
            {
                "source": src,
                "target": tgt,
                "source_fraction": 1.0,
                "n": len(ei),
                "frac_mean": float(ei["frac_of_opt"].mean()),
                "delta_vs_cold": d,
                "delta_ci_lo": lo,
                "delta_ci_hi": hi,
            }
        )
    return pd.DataFrame(rows).sort_values(["source", "target", "source_fraction"])


def write_report(out: Path, overall: pd.DataFrame, ucb: pd.DataFrame, frac: pd.DataFrame, budget: pd.DataFrame, ninit: pd.DataFrame) -> None:
    lines = [
        "# Experimental stats report",
        "",
        "## Dev-fold transfer (EI, paired Δfrac vs cold, 95% bootstrap CI)",
        "",
    ]
    if not overall.empty:
        lines.append(overall.to_string(index=False))
        lines.append("")
    lines.append("## SI: UCB vs EI (sign flips?)")
    lines.append("")
    if ucb.empty:
        lines.append("_pending — run `python scripts/run_si_suite.py --block ucb`_")
    else:
        lines.append(ucb.to_string(index=False))
        flips = int(ucb["sign_flip"].sum()) if "sign_flip" in ucb.columns else 0
        lines.append("")
        lines.append(f"Sign flips vs EI: **{flips}** / {len(ucb)}")
    lines.append("")
    lines.append("## SI: source_fraction scan (label_warm, morgan)")
    lines.append("")
    if frac.empty:
        lines.append("_pending_")
    else:
        lines.append(frac.to_string(index=False))
    lines.append("")
    lines.append("## SI: budget=50 / n_init=10")
    lines.append("")
    if budget.empty and ninit.empty:
        lines.append("_pending_")
    else:
        if not budget.empty:
            lines.append("### budget=50")
            lines.append(budget.to_string(index=False))
            lines.append("")
        if not ninit.empty:
            lines.append("### n_init=10")
            lines.append(ninit.to_string(index=False))
    (out / "STATS_REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def summarize_simple_si(path: Path, cold_grid: pd.DataFrame, strategy_filter=None) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    if strategy_filter:
        df = df[df["strategy"].isin(strategy_filter)]
    cold = (
        cold_grid[
            (cold_grid["strategy"] == "cold_start")
            & (cold_grid["representation"] == "morgan")
        ]
        .groupby(["target_plate", "seed"])["frac_of_opt"]
        .mean()
        .rename("cold")
        .reset_index()
    )
    # For SI blocks that include their own cold rows, prefer those
    rows = []
    has_cold = (df["strategy"] == "cold_start").any()
    if has_cold:
        cold_si = (
            df[df["strategy"] == "cold_start"]
            .groupby(["target_plate", "seed", "tag"])["frac_of_opt"]
            .mean()
            .rename("cold")
            .reset_index()
        )
    for keys, g in df[df["strategy"] != "cold_start"].groupby(
        ["strategy", "source_plate", "target_plate", "tag"], dropna=False
    ):
        strat, src, tgt, tag = keys
        if has_cold:
            m = g.merge(
                cold_si[cold_si["tag"] == tag][["target_plate", "seed", "cold"]],
                on=["target_plate", "seed"],
                how="inner",
            )
        else:
            m = g.merge(cold, on=["target_plate", "seed"], how="inner")
        if m.empty:
            continue
        d, lo, hi = paired_delta_ci(m["frac_of_opt"].to_numpy(), m["cold"].to_numpy())
        rows.append(
            {
                "strategy": strat,
                "source": src,
                "target": tgt,
                "tag": tag,
                "n": len(m),
                "delta_vs_cold": d,
                "delta_ci_lo": lo,
                "delta_ci_hi": hi,
            }
        )
    return pd.DataFrame(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--grid", type=Path, default=ROOT / "results/transfer_grid/grid_results.csv")
    ap.add_argument("--si", type=Path, default=ROOT / "results/si")
    ap.add_argument("--out", type=Path, default=ROOT / "results/stats")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    grid = load_grid(args.grid)
    dev = stats_dev_transfer(grid)
    dev.to_csv(args.out / "transfer_dev_stats.csv", index=False)
    overall = overall_by_strategy(dev)
    overall.to_csv(args.out / "transfer_dev_overall.csv", index=False)

    ucb = si_ucb_compare(args.si, grid)
    if not ucb.empty:
        ucb.to_csv(args.out / "si_ucb_vs_ei.csv", index=False)

    frac = si_frac_table(args.si, grid)
    if not frac.empty:
        frac.to_csv(args.out / "si_source_frac.csv", index=False)

    budget = summarize_simple_si(args.si / "budget50_results.csv", grid)
    if not budget.empty:
        budget.to_csv(args.out / "si_budget50.csv", index=False)
    ninit = summarize_simple_si(args.si / "ninit10_results.csv", grid)
    if not ninit.empty:
        ninit.to_csv(args.out / "si_ninit10.csv", index=False)

    write_report(args.out, overall, ucb, frac, budget, ninit)
    print(f"Wrote stats -> {args.out}")
    print(overall.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
