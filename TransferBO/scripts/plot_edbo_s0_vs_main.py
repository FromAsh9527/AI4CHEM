#!/usr/bin/env python
"""Fig3: S0 matched-init vs main-grid raw pooling (compact).

Uses precomputed `edbo_suzuki_s0_vs_main_pair_overall.csv`.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
STATS = ROOT / "results" / "paper_stats"
FIGS = ROOT / "docs" / "figs" / "main"


def main() -> int:
    FIGS.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(STATS / "edbo_suzuki_s0_vs_main_pair_overall.csv")
    d = df[df.budget.isin([40, 100])].copy()
    d["label"] = d["grid"].map({"s0": "S0 matched init", "main": "Main (unmatched)"}).fillna(d.grid)

    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.2), sharey=False)
    for ax, rep in zip(axes, ("morgan", "dft")):
        sub = d[d.rep == rep]
        xs, labels = [], []
        for i, (grid, B) in enumerate([("main", 40), ("s0", 40), ("main", 100), ("s0", 100)]):
            r = sub[(sub.grid == grid) & (sub.budget == B)].iloc[0]
            mu, lo, hi = r.delta_mean, r.delta_ci_lo, r.delta_ci_hi
            ax.errorbar(
                i,
                mu,
                yerr=[[mu - lo], [hi - mu]],
                fmt="o",
                color="#2F4B7C" if grid == "main" else "#008A5E",
                ms=6,
                lw=1.3,
                capsize=3,
            )
            xs.append(i)
            labels.append(f"{'Main' if grid=='main' else 'S0'}\nB={B}")
        ax.axhline(0, color="#333", ls="--", lw=0.9)
        ax.set_xticks(xs)
        ax.set_xticklabels(labels, fontsize=8)
        ax.set_title(rep.upper() if rep != "morgan" else "Morgan", fontsize=11)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
    axes[0].set_ylabel(r"Pair $\Delta\mathrm{frac}$ (label $-$ cold)", fontsize=10)
    fig.suptitle("Init robustness: main grid vs S0 matched target init", fontsize=11, y=1.03)
    fig.tight_layout()
    stem = "fig_edbo_suzuki_s0_vs_main_pair_delta"
    fig.savefig(FIGS / f"{stem}.png", dpi=200, bbox_inches="tight")
    fig.savefig(FIGS / f"{stem}.pdf", bbox_inches="tight")
    plt.close(fig)
    print("wrote", FIGS / f"{stem}.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
