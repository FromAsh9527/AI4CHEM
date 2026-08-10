#!/usr/bin/env python
"""Fig2: C1 three-representation pair Δfrac by budget (main grid)."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
STATS = ROOT / "results" / "paper_stats"
FIGS = ROOT / "docs" / "figs" / "main"


def main() -> int:
    FIGS.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(STATS / "edbo_suzuki_pair_overall_by_budget.csv")
    d = df[(df.metric == "frac") & (df.budget.isin([30, 40, 50, 100]))].copy()
    reps = ["morgan", "drfp", "dft"]
    budgets = [30, 40, 50, 100]
    colors = {"morgan": "#2F4B7C", "drfp": "#665191", "dft": "#008A5E"}

    fig, ax = plt.subplots(figsize=(6.8, 3.6))
    offset = {"morgan": -0.18, "drfp": 0.0, "dft": 0.18}
    for rep in reps:
        sub = d[d.rep == rep].set_index("budget")
        xs, ys, ylo, yhi = [], [], [], []
        for i, B in enumerate(budgets):
            r = sub.loc[B]
            xs.append(i + offset[rep])
            ys.append(r.delta_mean)
            ylo.append(r.delta_mean - r.delta_ci_lo)
            yhi.append(r.delta_ci_hi - r.delta_mean)
        ax.errorbar(
            xs,
            ys,
            yerr=[ylo, yhi],
            fmt="o-",
            color=colors[rep],
            label=rep.upper() if rep != "morgan" else "Morgan",
            ms=5,
            lw=1.2,
            capsize=3,
        )
    ax.axhline(0, color="#333", ls="--", lw=0.9)
    ax.set_xticks(range(len(budgets)))
    ax.set_xticklabels([f"B={B}" for B in budgets])
    ax.set_ylabel(r"Pair $\Delta\mathrm{frac}$ (label $-$ cold)")
    ax.set_title("C1: raw label pooling vs cold (main grid, pair unit)")
    ax.legend(frameon=False, fontsize=9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    stem = "fig_edbo_suzuki_C1_pair_delta_by_budget"
    fig.savefig(FIGS / f"{stem}.png", dpi=200, bbox_inches="tight")
    fig.savefig(FIGS / f"{stem}.pdf", bbox_inches="tight")
    plt.close(fig)
    print("wrote", FIGS / f"{stem}.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
