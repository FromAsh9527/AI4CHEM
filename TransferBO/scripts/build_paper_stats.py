#!/usr/bin/env python
"""Build hierarchical stats + paper-ready summary tables (CHAOS + Doyle).

Outputs under results/paper_stats/:
  chaos_pair_level.csv / chaos_target_level.csv / chaos_overall.csv
  doyle_pair_level.csv / doyle_target_level.csv / doyle_overall.csv
  HIERARCHICAL_STATS.md
  FROZEN_CLAIMS.md
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def boot_ci(x: np.ndarray, n_boot: int = 2000, seed: int = 0):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    if len(x) == 0:
        return np.nan, np.nan, np.nan
    rng = np.random.default_rng(seed)
    means = [float(np.mean(rng.choice(x, size=len(x), replace=True))) for _ in range(n_boot)]
    return float(np.mean(x)), float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))


def load_chaos_grid(path: Path) -> pd.DataFrame:
    g = pd.read_csv(path)
    g = g.rename(
        columns={
            "source_plate": "source",
            "target_plate": "target",
            "representation": "rep",
            "frac_of_opt": "frac",
            "queries_to_top5": "q5",
        }
    )
    return g


def load_doyle_grid(path: Path) -> pd.DataFrame:
    g = pd.read_csv(path)
    g = g.rename(columns={"source": "source", "target": "target", "rep": "rep"})
    return g


def pair_level(df: pd.DataFrame, strategies: list[str], reps: list[str] | None = None) -> pd.DataFrame:
    if reps is not None:
        df = df[df["rep"].isin(reps)]
    cold = (
        df[df["strategy"] == "cold_start"]
        .groupby(["target", "rep", "seed"], dropna=False)
        .agg(cold_frac=("frac", "mean"), cold_q5=("q5", "median"))
        .reset_index()
    )
    rows = []
    for strat in strategies:
        sub = df[df["strategy"] == strat].merge(cold, on=["target", "rep", "seed"], how="inner")
        if sub.empty:
            continue
        for (src, tgt, rep), g in sub.groupby(["source", "target", "rep"]):
            if src == tgt:
                continue
            dfrac = (g["frac"] - g["cold_frac"]).to_numpy()
            # q5: lower better → positive delta_q5 means transfer used fewer queries
            dq = (g["cold_q5"] - g["q5"]).to_numpy(dtype=float)
            mu, lo, hi = boot_ci(dfrac)
            rows.append(
                {
                    "strategy": strat,
                    "source": src,
                    "target": tgt,
                    "rep": rep,
                    "n_seeds": len(g),
                    "frac_mean": float(g["frac"].mean()),
                    "cold_mean": float(g["cold_frac"].mean()),
                    "delta_frac": mu,
                    "delta_ci_lo": lo,
                    "delta_ci_hi": hi,
                    "win_rate": float((dfrac > 0).mean()),
                    "delta_q5_mean": float(np.nanmean(dq)),
                    "sign": "pos" if lo > 0 else ("neg" if hi < 0 else "unstable"),
                }
            )
    return pd.DataFrame(rows)


def target_level(pair: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (strat, tgt, rep), g in pair.groupby(["strategy", "target", "rep"]):
        mu, lo, hi = boot_ci(g["delta_frac"].to_numpy())
        rows.append(
            {
                "strategy": strat,
                "target": tgt,
                "rep": rep,
                "n_sources": len(g),
                "delta_frac": mu,
                "delta_ci_lo": lo,
                "delta_ci_hi": hi,
                "ntr": float((g["delta_frac"] < -0.02).mean()),
                "pos_rate": float((g["delta_frac"] > 0.02).mean()),
            }
        )
    return pd.DataFrame(rows)


def overall_level(pair: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (strat, rep), g in pair.groupby(["strategy", "rep"]):
        mu, lo, hi = boot_ci(g["delta_frac"].to_numpy())
        rows.append(
            {
                "strategy": strat,
                "rep": rep,
                "n_pairs": len(g),
                "delta_frac": mu,
                "delta_ci_lo": lo,
                "delta_ci_hi": hi,
                "n_pos_stable": int((g["sign"] == "pos").sum()),
                "n_neg_stable": int((g["sign"] == "neg").sum()),
                "n_unstable": int((g["sign"] == "unstable").sum()),
                "ntr_pairs": float((g["delta_frac"] < -0.02).mean()),
                "mean_delta_q5": float(g["delta_q5_mean"].mean()),
            }
        )
    return pd.DataFrame(rows)


def write_md(out: Path, chaos_o: pd.DataFrame, doyle_o: pd.DataFrame, chaos_t: pd.DataFrame, doyle_t: pd.DataFrame) -> None:
    lines = [
        "# Hierarchical statistics (pair → target → overall)",
        "",
        "Inference unit for cross-task claims = **source→target pair** (or target), not seed.",
        "Seed-level variation only quantifies within-task optimizer stochasticity.",
        "",
        "## CHAOS additives (dev plates, morgan+drfp in pair tables; overall below by rep)",
        "",
    ]
    if not chaos_o.empty:
        lines.append(chaos_o.round(3).to_string(index=False))
    lines += ["", "## Doyle BH conditions (8 substrates, ohe)", ""]
    if not doyle_o.empty:
        lines.append(doyle_o.round(3).to_string(index=False))
    lines += ["", "## Target-level heterogeneity (label_warm)", ""]
    for name, tdf in [("CHAOS", chaos_t), ("Doyle", doyle_t)]:
        sub = tdf[tdf["strategy"] == "label_warm"]
        if sub.empty:
            continue
        lines.append(f"### {name}")
        lines.append(sub.round(3).to_string(index=False))
        lines.append("")
    (out / "HIERARCHICAL_STATS.md").write_text("\n".join(lines), encoding="utf-8")


def write_frozen_claims(out: Path) -> None:
    text = """# Frozen claims (do not retune methods against these)

Date: 2026-07-31

## Scope
- Main campaign: CHAOS four additive plates (held-out plate_4 frozen after Gate).
- External same-library campaign: Doyle Ahneman BH (8 substrates × 240 shared conditions).
- Gate: W8 **No-Go** (no value vs always-label); not a main claim.

## Claims eligible for the paper

**C1 (what to transfer).** On same-library cross-task HTE, **label-informed warm-start** is on average better than cold-start BO; a simple pooled/shared-kernel joint GP behaves like label warm-start and is **not** claimed as a full multi-task GP.

**C2 (structure-only transfer).** **Diversity / structure-only warm-start** is not a safe default: it is on average worse than cold on final performance in both CHAOS and Doyle.

**C3 (heterogeneity).** Average gains hide source→target heterogeneity; some pairs show negative transfer. The scientific question is *when* label transfer helps, not whether it always helps.

**C4 (robustness, SI).** On CHAOS locked pairs, main signs survive UCB, short budget (50), and smaller n_init (10); more source labels generally help on positive pairs. Edge pairs can sit near zero.

**C5 (external).** Doyle same-library validation supports C1–C3 directionally (label Δfrac ≈ +0.06 on pairs; diversity ≈ −0.06), without requiring CHAOS’s effect size.

**C6 (Gate).** A plate-level TransferGate trained on few development pairs did not beat always-label on held-out plate_4; reported as a negative / limited attempt.

## Non-claims
- Not claiming first BO on additives / first transfer BO.
- Not claiming SURF same-library validation (failed audit: no shared condition library).
- Not claiming deployable Gate features that use full target labels (those are post-hoc only).
"""
    (out / "FROZEN_CLAIMS.md").write_text(text, encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chaos", type=Path, default=ROOT / "results/transfer_grid/grid_results.csv")
    ap.add_argument("--doyle", type=Path, default=ROOT / "results/external_doyle/grid_results.csv")
    ap.add_argument("--out", type=Path, default=ROOT / "results/paper_stats")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    chaos = load_chaos_grid(args.chaos)
    # exclude same-plate cold duplicates handled in pair_level; restrict transfer strategies
    chaos_pair = pair_level(
        chaos,
        strategies=["label_warm", "diversity_warm", "multitask"],
        reps=["morgan", "drfp"],
    )
    # drop held-out targets from main narrative tables? keep all but flag — use only plate_1/2/3 as target for chaos "main"
    chaos_pair_dev = chaos_pair[chaos_pair["target"].isin(["plate_1", "plate_2", "plate_3"])]
    chaos_t = target_level(chaos_pair_dev)
    chaos_o = overall_level(chaos_pair_dev)
    chaos_pair.to_csv(args.out / "chaos_pair_level.csv", index=False)
    chaos_t.to_csv(args.out / "chaos_target_level.csv", index=False)
    chaos_o.to_csv(args.out / "chaos_overall.csv", index=False)

    doyle_pair = pd.DataFrame()
    doyle_t = pd.DataFrame()
    doyle_o = pd.DataFrame()
    if args.doyle.exists():
        doyle = load_doyle_grid(args.doyle)
        doyle_pair = pair_level(doyle, strategies=["label_warm", "diversity_warm"])
        doyle_t = target_level(doyle_pair)
        doyle_o = overall_level(doyle_pair)
        doyle_pair.to_csv(args.out / "doyle_pair_level.csv", index=False)
        doyle_t.to_csv(args.out / "doyle_target_level.csv", index=False)
        doyle_o.to_csv(args.out / "doyle_overall.csv", index=False)

    write_md(args.out, chaos_o, doyle_o, chaos_t, doyle_t)
    write_frozen_claims(args.out)

    # merge mechanism correlations pointer
    mech = ROOT / "results/mechanism/feature_delta_correlations.csv"
    if mech.exists():
        pd.read_csv(mech).to_csv(args.out / "chaos_mechanism_correlations.csv", index=False)

    print(f"Wrote {args.out}")
    print("--- CHAOS overall ---")
    print(chaos_o.round(3).to_string(index=False))
    if not doyle_o.empty:
        print("--- Doyle overall ---")
        print(doyle_o.round(3).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
