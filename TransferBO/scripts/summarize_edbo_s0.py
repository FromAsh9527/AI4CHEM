#!/usr/bin/env python
"""Summarize S0 matched-init EDBO Suzuki (Morgan + DFT) vs main unmatched grid."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

NEAR = 0.02
BUDGETS = [30, 40, 50, 100]
ROOT = Path(__file__).resolve().parents[1]
S0 = ROOT / "results" / "external_edbo_suzuki_s0"
MAIN = ROOT / "results" / "external_edbo_suzuki"
STATS = ROOT / "results" / "paper_stats"


def load(root: Path, rep: str) -> pd.DataFrame:
    rows = []
    for p in root.glob("*.json"):
        if f"__{rep}__" not in p.name:
            continue
        if not (p.name.startswith("cold_start") or p.name.startswith("label_warm")):
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        g = float(d["global_best"])
        curve = [float(v) for v in d["bo"]["best_so_far"][:100]]
        rows.append(
            {
                "strategy": d["strategy"],
                "source": d.get("source_plate"),
                "target": d["target_plate"],
                "seed": int(d["seed"]),
                "global_best": g,
                "curve": curve,
                "init": tuple((d.get("meta") or {}).get("init_indices") or []),
            }
        )
    return pd.DataFrame(rows)


def audit(df: pd.DataFrame) -> tuple[int, int]:
    cold = {
        (r.target, r.seed): r.init
        for r in df[df.strategy == "cold_start"].itertuples(index=False)
    }
    match = tot = 0
    for r in df[df.strategy == "label_warm"].itertuples(index=False):
        tot += 1
        if cold.get((r.target, r.seed)) == r.init:
            match += 1
    return match, tot


def boot_ci(x: np.ndarray, seed: int = 0):
    rng = np.random.default_rng(seed)
    boots = [
        float(np.mean(rng.choice(x, size=len(x), replace=True))) for _ in range(3000)
    ]
    return float(np.mean(x)), float(np.quantile(boots, 0.025)), float(np.quantile(boots, 0.975))


def pair_table(df: pd.DataFrame, rep: str, grid: str) -> pd.DataFrame:
    rows = []
    for B in BUDGETS:
        cold = df[df.strategy == "cold_start"].copy()
        lab = df[df.strategy == "label_warm"].copy()
        cold["c"] = [c[B - 1] / g for c, g in zip(cold.curve, cold.global_best)]
        lab["l"] = [c[B - 1] / g for c, g in zip(lab.curve, lab.global_best)]
        mrg = lab.merge(
            cold[["target", "seed", "c"]].drop_duplicates(["target", "seed"]),
            on=["target", "seed"],
        )
        mrg["delta"] = mrg["l"] - mrg["c"]
        pair = mrg.groupby(["source", "target"], as_index=False).agg(
            delta_mean=("delta", "mean"), n_seeds=("delta", "size")
        )
        x = pair.delta_mean.to_numpy(float)
        mu, lo, hi = boot_ci(x, seed=B + 17)
        rows.append(
            {
                "grid": grid,
                "rep": rep,
                "budget": B,
                "n_pairs": len(pair),
                "delta_mean": mu,
                "delta_median": float(np.median(x)),
                "delta_ci_lo": lo,
                "delta_ci_hi": hi,
                "n_pos": int((x > NEAR).sum()),
                "n_neg": int((x < -NEAR).sum()),
                "n_near0": int((np.abs(x) <= NEAR).sum()),
            }
        )
    return pd.DataFrame(rows)


def main() -> int:
    STATS.mkdir(parents=True, exist_ok=True)
    overall = []
    audits = []
    for rep in ("morgan", "dft"):
        for grid, root in (("s0", S0), ("main", MAIN)):
            df = load(root, rep)
            m, t = audit(df)
            audits.append(
                {
                    "grid": grid,
                    "rep": rep,
                    "n_label": t,
                    "n_match": m,
                    "pct_match": (100.0 * m / t) if t else np.nan,
                    "n_cold": int((df.strategy == "cold_start").sum()),
                }
            )
            print(f"{grid}/{rep}: cold={(df.strategy=='cold_start').sum()} label={t} init_match={m}/{t}")
            overall.append(pair_table(df, rep, grid))

    ov = pd.concat(overall, ignore_index=True)
    au = pd.DataFrame(audits)
    ov.to_csv(STATS / "edbo_suzuki_s0_vs_main_pair_overall.csv", index=False)
    au.to_csv(STATS / "edbo_suzuki_s0_init_match_audit.csv", index=False)

    print("\n=== pair Δfrac overall ===")
    show = ov[ov.budget.isin([40, 100])][
        ["grid", "rep", "budget", "delta_mean", "delta_ci_lo", "delta_ci_hi", "n_pos", "n_neg", "n_near0"]
    ]
    print(show.round(4).to_string(index=False))

    note = STATS / "edbo_suzuki_s0_NOTE.md"
    note.write_text(
        "\n".join(
            [
                "# S0 matched-target-init (EDBO Suzuki)",
                "",
                "- Dir: `results/external_edbo_suzuki_s0/`",
                "- Reps: Morgan + DFT; cold 160 + label 1120 each.",
                "- Init match: 100% on S0; 0% on main grid.",
                "",
                "## Pair-mean Δfrac (bootstrap over 56 pairs)",
                "",
                "```",
                ov.round(4).to_string(index=False),
                "```",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"\nwrote {STATS / 'edbo_suzuki_s0_vs_main_pair_overall.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
