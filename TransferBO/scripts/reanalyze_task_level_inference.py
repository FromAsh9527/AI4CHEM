#!/usr/bin/env python
"""Task-level re-inference for EDBO Suzuki (P0 / W1).

Addresses crossed dependence among 56 directed pairs (only ~8 tasks):
  - target-level aggregation (mean over sources into each target)
  - pair / target / source weighted overall means
  - cluster bootstrap (resample tasks, keep induced pairs)
  - leave-one-task-out (LOT)

Inputs (offline CSVs; no main-grid re-run):
  results/paper_stats/edbo_suzuki_pair_level_deltas.csv   (C1)
  results/paper_stats/edbo_suzuki_ladder_pair_delta_B40.csv (S0 ladder @ B=40)

Outputs under results/paper_stats/:
  edbo_suzuki_task_level_*.csv
  edbo_suzuki_task_level_INFERENCE_NOTE.md
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
STATS = ROOT / "results" / "paper_stats"
NEAR0 = 0.02
N_BOOT = 3000
PRIMARY_BUDGETS = (30, 40, 50)


def boot_mean_ci(x: np.ndarray, *, n_boot: int = N_BOOT, seed: int = 0):
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) == 0:
        return np.nan, np.nan, np.nan
    rng = np.random.default_rng(seed)
    means = [float(np.mean(rng.choice(x, size=len(x), replace=True))) for _ in range(n_boot)]
    return float(np.mean(x)), float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))


def sign_counts(x: np.ndarray, near: float):
    x = np.asarray(x, dtype=float)
    return {
        "n": int(len(x)),
        "n_pos": int((x > near).sum()),
        "n_neg": int((x < -near).sum()),
        "n_near0": int((np.abs(x) <= near).sum()),
        "min": float(np.min(x)) if len(x) else np.nan,
        "max": float(np.max(x)) if len(x) else np.nan,
        "median": float(np.median(x)) if len(x) else np.nan,
    }


def cluster_boot_tasks(
    pair_df: pd.DataFrame,
    *,
    delta_col: str = "delta",
    n_boot: int = N_BOOT,
    seed: int = 0,
):
    """Resample task IDs; keep pairs whose source and target are both in the resampled set.

    Reports mean of pair deltas within each bootstrap replicate (pair-weighted inside cluster draw).
    Also reports mean of target-aggregated effects under the same task draws.
    """
    tasks = sorted(set(pair_df["source"]) | set(pair_df["target"]))
    rng = np.random.default_rng(seed)
    pair_means = []
    tgt_means = []
    for _ in range(n_boot):
        draw = rng.choice(tasks, size=len(tasks), replace=True)
        # multiset of tasks → keep pairs with both ends in unique set of draw
        keep = set(draw)
        sub = pair_df[pair_df["source"].isin(keep) & pair_df["target"].isin(keep)]
        if sub.empty:
            continue
        pair_means.append(float(sub[delta_col].mean()))
        tgt = sub.groupby("target")[delta_col].mean()
        tgt_means.append(float(tgt.mean()))
    def _ci(arr):
        if not arr:
            return np.nan, np.nan, np.nan
        a = np.asarray(arr, dtype=float)
        return float(np.mean(a)), float(np.quantile(a, 0.025)), float(np.quantile(a, 0.975))

    return _ci(pair_means), _ci(tgt_means)


def weighted_summaries(
    pair_df: pd.DataFrame, *, delta_col: str = "delta", near0: float = NEAR0
) -> dict:
    d = pair_df[delta_col].to_numpy(float)
    pair_mu, pair_lo, pair_hi = boot_mean_ci(d, seed=11)
    by_tgt = pair_df.groupby("target")[delta_col].mean()
    by_src = pair_df.groupby("source")[delta_col].mean()
    tgt_mu, tgt_lo, tgt_hi = boot_mean_ci(by_tgt.to_numpy(float), seed=12)
    src_mu, src_lo, src_hi = boot_mean_ci(by_src.to_numpy(float), seed=13)
    (c_pair_mu, c_pair_lo, c_pair_hi), (c_tgt_mu, c_tgt_lo, c_tgt_hi) = cluster_boot_tasks(
        pair_df, delta_col=delta_col, seed=21
    )
    sc_pair = sign_counts(d, near0)
    sc_tgt = sign_counts(by_tgt.to_numpy(float), near0)
    return {
        "n_pairs": int(len(pair_df)),
        "n_targets": int(by_tgt.shape[0]),
        "n_sources": int(by_src.shape[0]),
        "pair_weighted_mean": pair_mu,
        "pair_boot_lo": pair_lo,
        "pair_boot_hi": pair_hi,
        "target_weighted_mean": tgt_mu,
        "target_boot_lo": tgt_lo,
        "target_boot_hi": tgt_hi,
        "source_weighted_mean": src_mu,
        "source_boot_lo": src_lo,
        "source_boot_hi": src_hi,
        "cluster_pair_mean": c_pair_mu,
        "cluster_pair_lo": c_pair_lo,
        "cluster_pair_hi": c_pair_hi,
        "cluster_target_mean": c_tgt_mu,
        "cluster_target_lo": c_tgt_lo,
        "cluster_target_hi": c_tgt_hi,
        "pair_n_pos": sc_pair["n_pos"],
        "pair_n_neg": sc_pair["n_neg"],
        "pair_n_near0": sc_pair["n_near0"],
        "target_n_pos": sc_tgt["n_pos"],
        "target_n_neg": sc_tgt["n_neg"],
        "target_n_near0": sc_tgt["n_near0"],
        "target_min": sc_tgt["min"],
        "target_max": sc_tgt["max"],
        "target_median": sc_tgt["median"],
        "window_mean_B30_50_pair": np.nan,  # filled by caller when multi-B
    }


def leave_one_task_out(pair_df: pd.DataFrame, *, delta_col: str = "delta") -> pd.DataFrame:
    tasks = sorted(set(pair_df["source"]) | set(pair_df["target"]))
    rows = []
    for drop in tasks:
        sub = pair_df[(pair_df["source"] != drop) & (pair_df["target"] != drop)]
        if sub.empty:
            continue
        by_tgt = sub.groupby("target")[delta_col].mean()
        rows.append(
            {
                "left_out_task": drop,
                "n_pairs_remain": int(len(sub)),
                "n_targets_remain": int(by_tgt.shape[0]),
                "pair_mean": float(sub[delta_col].mean()),
                "target_mean": float(by_tgt.mean()),
            }
        )
    return pd.DataFrame(rows)


def analyze_block(
    pair_df: pd.DataFrame,
    *,
    block: str,
    rep: str,
    budget: int | str,
    delta_col: str = "delta",
    near0: float = NEAR0,
) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    """Return overall row, per-target table, LOT table."""
    overall = weighted_summaries(pair_df, delta_col=delta_col, near0=near0)
    overall.update({"block": block, "rep": rep, "budget": budget})
    by_tgt = (
        pair_df.groupby("target", as_index=False)
        .agg(
            n_sources=(delta_col, "size"),
            delta_mean=(delta_col, "mean"),
            delta_median=(delta_col, "median"),
            delta_std=(delta_col, "std"),
        )
        .sort_values("target")
    )
    by_tgt.insert(0, "block", block)
    by_tgt.insert(1, "rep", rep)
    by_tgt.insert(2, "budget", budget)
    lot = leave_one_task_out(pair_df, delta_col=delta_col)
    lot.insert(0, "block", block)
    lot.insert(1, "rep", rep)
    lot.insert(2, "budget", budget)
    return overall, by_tgt, lot


def load_c1_pairs(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = df[(df["metric"] == "frac")].copy()
    df = df.rename(columns={"delta_mean": "delta"})
    return df


def load_ladder_b40(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--near0", type=float, default=NEAR0)
    args = ap.parse_args()
    near0 = float(args.near0)

    STATS.mkdir(parents=True, exist_ok=True)
    c1_path = STATS / "edbo_suzuki_pair_level_deltas.csv"
    ladder_path = STATS / "edbo_suzuki_ladder_pair_delta_B40.csv"
    if not c1_path.exists():
        raise SystemExit(f"missing {c1_path}")

    overall_rows = []
    tgt_rows = []
    lot_rows = []
    window_rows = []

    c1 = load_c1_pairs(c1_path)
    for rep in sorted(c1["rep"].unique()):
        for B in PRIMARY_BUDGETS + (100,):
            sub = c1[(c1["rep"] == rep) & (c1["budget"] == B)][
                ["source", "target", "delta"]
            ]
            if sub.empty:
                continue
            ov, tgt, lot = analyze_block(
                sub, block="C1_main", rep=rep, budget=B, near0=near0
            )
            overall_rows.append(ov)
            tgt_rows.append(tgt)
            lot_rows.append(lot)

        # primary window mean over B=30,40,50 (pair-level then average budgets equally)
        win_pairs = []
        for B in PRIMARY_BUDGETS:
            sub = c1[(c1["rep"] == rep) & (c1["budget"] == B)][
                ["source", "target", "delta"]
            ].rename(columns={"delta": f"d{B}"})
            win_pairs.append(sub)
        merged = win_pairs[0]
        for extra in win_pairs[1:]:
            merged = merged.merge(extra, on=["source", "target"], how="inner")
        merged["delta"] = merged[[f"d{B}" for B in PRIMARY_BUDGETS]].mean(axis=1)
        ov, tgt, lot = analyze_block(
            merged[["source", "target", "delta"]],
            block="C1_main",
            rep=rep,
            budget="mean_30_50",
            near0=near0,
        )
        overall_rows.append(ov)
        tgt_rows.append(tgt)
        lot_rows.append(lot)
        window_rows.append(
            {
                "block": "C1_main",
                "rep": rep,
                "primary_metric": "mean_delta_frac_B30_50",
                "pair_weighted_mean": ov["pair_weighted_mean"],
                "target_weighted_mean": ov["target_weighted_mean"],
                "cluster_target_mean": ov["cluster_target_mean"],
                "cluster_target_lo": ov["cluster_target_lo"],
                "cluster_target_hi": ov["cluster_target_hi"],
            }
        )

    if ladder_path.exists():
        ladder = load_ladder_b40(ladder_path)
        for (arm, rep), g in ladder.groupby(["arm", "rep"]):
            sub = g[["source", "target", "delta"]].copy()
            block = f"S0_ladder:{arm}"
            ov, tgt, lot = analyze_block(
                sub, block=block, rep=rep, budget=40, near0=near0
            )
            overall_rows.append(ov)
            tgt_rows.append(tgt)
            lot_rows.append(lot)

    overall = pd.DataFrame(overall_rows)
    by_tgt = pd.concat(tgt_rows, ignore_index=True)
    lot = pd.concat(lot_rows, ignore_index=True)
    window = pd.DataFrame(window_rows)

    out_ov = STATS / "edbo_suzuki_task_level_overall.csv"
    out_tgt = STATS / "edbo_suzuki_task_level_by_target.csv"
    out_lot = STATS / "edbo_suzuki_task_level_lot.csv"
    out_win = STATS / "edbo_suzuki_task_level_primary_window.csv"
    overall.to_csv(out_ov, index=False)
    by_tgt.to_csv(out_tgt, index=False)
    lot.to_csv(out_lot, index=False)
    window.to_csv(out_win, index=False)

    # Headline for note
    def _fmt_block(df, block_pred, rep, budget):
        rows = df[
            df["block"].map(block_pred)
            & (df["rep"] == rep)
            & (df["budget"].astype(str) == str(budget))
        ]
        return rows.iloc[0] if len(rows) else None

    lines = [
        "# Task-level inference note (W1 / P0)",
        "",
        f"**Near-zero threshold:** `|Δ| ≤ {near0}`",
        f"**Bootstrap:** {N_BOOT} resamples; pair IID bootstrap vs **task-cluster** bootstrap.",
        "",
        "## Why this exists",
        "",
        "56 directed pairs are crossed: each of ~8 tasks appears in many pairs sharing",
        "the same cold baseline. Pair-IID bootstrap can understate uncertainty.",
        "Effective chemical N ≈ n_tasks (≈8), not n_pairs (56).",
        "",
        "## Methods",
        "",
        "1. **Target-weighted:** mean over targets of (mean Δ over sources→that target).",
        "2. **Source-weighted:** mean over sources of (mean Δ over that source→targets).",
        "3. **Pair-weighted:** mean over 56 pairs (legacy reporting unit).",
        "4. **Cluster bootstrap:** resample task IDs with replacement; keep pairs with both",
        "   ends in the resampled task set; report pair-mean and target-mean of survivors.",
        "5. **LOT:** drop one task (all pairs touching it), recompute pair/target means.",
        "6. **Primary window:** equal average of pair Δ at B=30,40,50 (pre-registered).",
        "",
        "## Headline (C1 main, frac)",
        "",
        "| Rep | Budget | Pair mean | Target mean | Cluster target mean [CI] |",
        "|---|---:|---:|---:|---:|",
    ]
    for rep in sorted(c1["rep"].unique()):
        for B in list(PRIMARY_BUDGETS) + ["mean_30_50"]:
            r = overall[
                (overall.block == "C1_main")
                & (overall.rep == rep)
                & (overall.budget.astype(str) == str(B))
            ]
            if r.empty:
                continue
            row = r.iloc[0]
            lines.append(
                f"| {rep} | {B} | {row.pair_weighted_mean:+.4f} | "
                f"{row.target_weighted_mean:+.4f} | "
                f"{row.cluster_target_mean:+.4f} "
                f"[{row.cluster_target_lo:+.4f}, {row.cluster_target_hi:+.4f}] |"
            )

    lines += [
        "",
        "## LOT stability (C1, B=40): target_mean range when leaving one task out",
        "",
    ]
    for rep in sorted(c1["rep"].unique()):
        sub = lot[(lot.block == "C1_main") & (lot.rep == rep) & (lot.budget.astype(str) == "40")]
        if sub.empty:
            continue
        lines.append(
            f"- **{rep}:** target_mean LOT min/max = "
            f"{sub.target_mean.min():+.4f} / {sub.target_mean.max():+.4f} "
            f"(full target_mean = "
            f"{overall[(overall.block=='C1_main')&(overall.rep==rep)&(overall.budget.astype(str)=='40')].iloc[0].target_weighted_mean:+.4f})"
        )

    if ladder_path.exists():
        lines += ["", "## S0 ladder @ B=40 (target-weighted / cluster-target)", ""]
        lines.append("| Arm | Rep | Target mean | Cluster target [CI] |")
        lines.append("|---|---|---:|---:|")
        for _, row in overall[overall.block.str.startswith("S0_ladder")].iterrows():
            lines.append(
                f"| {row.block.replace('S0_ladder:','')} | {row.rep} | "
                f"{row.target_weighted_mean:+.4f} | "
                f"{row.cluster_target_mean:+.4f} "
                f"[{row.cluster_target_lo:+.4f}, {row.cluster_target_hi:+.4f}] |"
            )

    # Go/no-go hint
    lines += ["", "## Go/no-go hint (descriptive)", ""]
    flags = []
    for rep in sorted(c1["rep"].unique()):
        r = overall[
            (overall.block == "C1_main")
            & (overall.rep == rep)
            & (overall.budget.astype(str) == "mean_30_50")
        ]
        if r.empty:
            continue
        row = r.iloc[0]
        still_neg = row.cluster_target_mean < 0 and row.cluster_target_hi < 0
        flags.append((rep, still_neg, row.cluster_target_mean, row.cluster_target_hi))
        lines.append(
            f"- C1 `{rep}` primary window cluster-target: "
            f"{row.cluster_target_mean:+.4f} CI=[{row.cluster_target_lo:+.4f},"
            f" {row.cluster_target_hi:+.4f}] → "
            f"{'STABLE NEG (CI excludes 0)' if still_neg else 'WEAK / CI includes 0 or non-neg'}"
        )

    lines += [
        "",
        "## Artifacts",
        "",
        f"- `{out_ov.name}`",
        f"- `{out_tgt.name}`",
        f"- `{out_lot.name}`",
        f"- `{out_win.name}`",
        "",
        "## Claiming language",
        "",
        "Prefer: *under task-level / cluster-bootstrap summaries, mid-budget effects remain*",
        "negative / near-negative*. Avoid treating n=56 pairs as IID for SEM/CI.",
    ]
    note = STATS / "edbo_suzuki_task_level_INFERENCE_NOTE.md"
    note.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"wrote {out_ov}")
    print(f"wrote {out_tgt}")
    print(f"wrote {out_lot}")
    print(f"wrote {out_win}")
    print(f"wrote {note}")
    print("\n=== primary window (C1) ===")
    print(window.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
