#!/usr/bin/env python
"""Fig4: A0–A3 method ladder — pair Δfrac at B=40 vs S0 cold.

Panels: Morgan | DFT
Arms: A1 raw, A2 rank, A3 w=0.25 (representative practical weight)
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
S0 = ROOT / "results" / "external_edbo_suzuki_s0"
A2 = ROOT / "results" / "external_edbo_suzuki_a2"
A3 = ROOT / "results" / "external_edbo_suzuki_a3"
FIGS = ROOT / "docs" / "figs" / "main"
STATS = ROOT / "results" / "paper_stats"
BUDGET = 40
NEAR = 0.02


def load_jsons(root: Path, prefix: str, rep: str) -> pd.DataFrame:
    rows = []
    for p in root.glob(f"{prefix}__{rep}__*.json"):
        d = json.loads(p.read_text(encoding="utf-8"))
        g = float(d["global_best"])
        curve = [float(v) for v in d["bo"]["best_so_far"][:100]]
        rows.append(
            {
                "source": d.get("source_plate"),
                "target": d["target_plate"],
                "seed": int(d["seed"]),
                "global_best": g,
                "curve": curve,
            }
        )
    return pd.DataFrame(rows)


def pair_deltas(lab: pd.DataFrame, cold: pd.DataFrame, arm: str, rep: str) -> pd.DataFrame:
    c = cold.copy()
    c["c"] = [cur[BUDGET - 1] / g for cur, g in zip(c.curve, c.global_best)]
    l = lab.copy()
    l["l"] = [cur[BUDGET - 1] / g for cur, g in zip(l.curve, l.global_best)]
    m = l.merge(
        c[["target", "seed", "c"]].drop_duplicates(["target", "seed"]),
        on=["target", "seed"],
    )
    m["delta"] = m["l"] - m["c"]
    pair = m.groupby(["source", "target"], as_index=False).agg(delta=("delta", "mean"))
    pair["arm"] = arm
    pair["rep"] = rep
    return pair


def boot_ci(x: np.ndarray, seed: int = 40) -> tuple[float, float, float]:
    rng = np.random.default_rng(seed)
    boots = [float(np.mean(rng.choice(x, size=len(x), replace=True))) for _ in range(3000)]
    return float(np.mean(x)), float(np.quantile(boots, 0.025)), float(np.quantile(boots, 0.975))


def main() -> int:
    FIGS.mkdir(parents=True, exist_ok=True)
    arms = [
        ("A1 raw", S0, "label_warm"),
        ("A2 rank", A2, "label_rank_warm"),
        ("A3 w=0.25", A3, "label_weight_w0p25"),
    ]
    frames = []
    for rep in ("morgan", "dft"):
        cold = load_jsons(S0, "cold_start", rep)
        if cold.empty:
            raise SystemExit(f"missing S0 cold for {rep}")
        for arm_name, root, pref in arms:
            lab = load_jsons(root, pref, rep)
            if lab.empty:
                raise SystemExit(f"missing {pref} {rep} in {root}")
            frames.append(pair_deltas(lab, cold, arm_name, rep))
    df = pd.concat(frames, ignore_index=True)
    out_csv = STATS / "edbo_suzuki_ladder_pair_delta_B40.csv"
    df.to_csv(out_csv, index=False)

    arm_order = ["A1 raw", "A2 rank", "A3 w=0.25"]
    colors = {"A1 raw": "#2F4B7C", "A2 rank": "#665191", "A3 w=0.25": "#A05195"}

    fig, axes = plt.subplots(1, 2, figsize=(8.2, 3.6), sharey=True)
    summary_rows = []
    for ax, rep in zip(axes, ("morgan", "dft")):
        sub = df[df.rep == rep]
        for i, arm in enumerate(arm_order):
            x = sub.loc[sub.arm == arm, "delta"].to_numpy(float)
            mu, lo, hi = boot_ci(x, seed=40 + i)
            summary_rows.append(
                {
                    "arm": arm,
                    "rep": rep,
                    "budget": BUDGET,
                    "n_pairs": len(x),
                    "delta_mean": mu,
                    "delta_ci_lo": lo,
                    "delta_ci_hi": hi,
                    "n_neg": int((x < -NEAR).sum()),
                    "n_pos": int((x > NEAR).sum()),
                }
            )
            jitter = (np.random.default_rng(i + 7).random(len(x)) - 0.5) * 0.18
            ax.scatter(
                np.full(len(x), i) + jitter,
                x,
                s=14,
                alpha=0.45,
                c=colors[arm],
                edgecolors="none",
                zorder=2,
            )
            ax.errorbar(
                i,
                mu,
                yerr=[[mu - lo], [hi - mu]],
                fmt="o",
                color="black",
                ms=5,
                lw=1.2,
                capsize=3,
                zorder=3,
            )
        ax.axhline(0.0, color="#333333", lw=0.9, ls="--", zorder=1)
        ax.axhspan(-NEAR, NEAR, color="#cccccc", alpha=0.35, zorder=0)
        ax.set_xticks(range(len(arm_order)))
        ax.set_xticklabels(arm_order, fontsize=9)
        ax.set_title(rep.upper() if rep != "morgan" else "Morgan", fontsize=11)
        ax.set_xlim(-0.5, len(arm_order) - 0.5)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
    axes[0].set_ylabel(r"Pair $\Delta\mathrm{frac}$ at $B=40$" + "\n(vs S0 cold)", fontsize=10)
    fig.suptitle(
        "Method ladder vs matched-init cold (pair means over seeds)",
        fontsize=11,
        y=1.02,
    )
    fig.tight_layout()
    stem = "fig_edbo_suzuki_ladder_A1A2A3_B40"
    fig.savefig(FIGS / f"{stem}.png", dpi=200, bbox_inches="tight")
    fig.savefig(FIGS / f"{stem}.pdf", bbox_inches="tight")
    plt.close(fig)

    summ = pd.DataFrame(summary_rows)
    summ.to_csv(STATS / "edbo_suzuki_ladder_pair_overall_B40.csv", index=False)
    print(summ.round(4).to_string(index=False))
    print("wrote", FIGS / f"{stem}.png")
    print("wrote", out_csv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
