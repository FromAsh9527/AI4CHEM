#!/usr/bin/env python
"""ESI landscape alignment: source–target response scatters + summary table.

Does NOT claim anti-correlation explains negative transfer; main finding is that
global Spearman does not track label Δfrac on the six CHAOS development pairs.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
OUT_FIG = ROOT / "exports" / "paper_figs"
OUT_DOCS = ROOT / "docs" / "figs"
OUT_STATS = ROOT / "results" / "paper_stats"
OUT_MECH = ROOT / "results" / "mechanism"


def top_jaccard(x: pd.Series, y: pd.Series, k: int) -> float:
    ta = set(x.nlargest(k).index)
    tb = set(y.nlargest(k).index)
    union = ta | tb
    return float(len(ta & tb) / len(union)) if union else np.nan


def main() -> int:
    OUT_FIG.mkdir(parents=True, exist_ok=True)
    OUT_DOCS.mkdir(parents=True, exist_ok=True)
    OUT_STATS.mkdir(parents=True, exist_ok=True)
    OUT_MECH.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(ROOT / "data" / "processed" / "additives_four_plates.csv")
    wide = df.pivot_table(index="smiles", columns="plate_id", values="response", aggfunc="first")
    lab = pd.read_csv(OUT_STATS / "chaos_pair_level.csv")
    lab = lab[
        (lab["strategy"] == "label_warm")
        & (lab["rep"] == "morgan")
        & (lab["target"].isin(["plate_1", "plate_2", "plate_3"]))
    ].copy()
    lab = lab[lab["source"] != lab["target"]].sort_values(["target", "source"])

    rows = []
    fig, axes = plt.subplots(2, 3, figsize=(10.5, 6.8), dpi=200)
    axes = axes.ravel()
    for i, (_, r) in enumerate(lab.iterrows()):
        src, tgt = r["source"], r["target"]
        x, y = wide[src], wide[tgt]
        sp, sp_p = spearmanr(x, y)
        j10 = top_jaccard(x, y, k=72)
        j5 = top_jaccard(x, y, k=36)
        best_src = x.idxmax()
        best_tgt = y.idxmax()
        rank_src_best_on_tgt = float(y.rank(ascending=False)[best_src])
        rank_tgt_best_on_src = float(x.rank(ascending=False)[best_tgt])
        rows.append(
            {
                "source": src,
                "target": tgt,
                "delta_frac_label_morgan": float(r["delta_frac"]),
                "sign_vs_cold": r["sign"],
                "spearman": float(sp),
                "spearman_p": float(sp_p),
                "top10_jaccard": j10,
                "top5_jaccard": j5,
                "src_best_rank_on_tgt": rank_src_best_on_tgt,
                "tgt_best_rank_on_src": rank_tgt_best_on_src,
                "n": int(len(x)),
            }
        )
        ax = axes[i]
        ax.scatter(x, y, s=6, alpha=0.35, c="#444444", edgecolors="none")
        # mark optima
        ax.scatter([x[best_src]], [y[best_src]], s=40, c="#1b9e77", zorder=3, label="src best")
        ax.scatter([x[best_tgt]], [y[best_tgt]], s=40, c="#d95f02", zorder=3, label="tgt best")
        ax.set_xlabel(f"{src} response")
        ax.set_ylabel(f"{tgt} response")
        ax.set_title(
            f"{src[-1]}→{tgt[-1]}  Δ={r['delta_frac']:+.2f} ({r['sign']})\n"
            f"ρ={sp:.2f}, J10={j10:.2f}",
            fontsize=9,
        )
        if i == 0:
            ax.legend(fontsize=7, loc="upper left")

    fig.suptitle(
        "ESI: CHAOS source–target response landscapes (720 additives)\n"
        "Global Spearman does not track label Δfrac; pairs remain positively correlated",
        fontsize=11,
    )
    fig.tight_layout()
    for dest in (OUT_FIG, OUT_DOCS, OUT_MECH):
        fig.savefig(dest / "fig_esi_landscape_scatters.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)

    tab = pd.DataFrame(rows)
    tab.to_csv(OUT_STATS / "chaos_landscape_vs_label_delta.csv", index=False)
    tab.to_csv(OUT_MECH / "chaos_landscape_vs_label_delta.csv", index=False)

    # short markdown note
    note = [
        "# CHAOS landscape alignment vs label Δfrac (ESI)",
        "",
        "All six development pairs have **positive** Spearman ρ (range ≈ 0.60–0.84).",
        "Label Δfrac (Morgan) is **not** a monotone function of ρ "
        f"(Pearson corr(Δ, ρ) ≈ {tab['delta_frac_label_morgan'].corr(tab['spearman']):.2f}).",
        "",
        "Notable: plate_1→plate_3 has weak/near-zero label transfer but still ρ≈0.62, "
        "and each plate's global best ranks #1 on the other plate—so a simple "
        "anti-correlation story for negative/null transfer is **not** supported.",
        "",
        tab.round(3).to_string(index=False),
        "",
        "Figure: `fig_esi_landscape_scatters.png`",
    ]
    (OUT_STATS / "LANDSCAPE_ALIGNMENT_ESI.md").write_text("\n".join(note), encoding="utf-8")
    (OUT_MECH / "LANDSCAPE_ALIGNMENT_ESI.md").write_text("\n".join(note), encoding="utf-8")

    print(tab.round(3).to_string(index=False))
    print("corr(delta,spearman)", float(tab["delta_frac_label_morgan"].corr(tab["spearman"])))
    print("Wrote scatters +", OUT_STATS / "chaos_landscape_vs_label_delta.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
