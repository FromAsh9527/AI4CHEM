#!/usr/bin/env python
"""Ceiling / headroom figures for EDBO Suzuki (C1 support).

Headroom at budget B for target t:
  h_t(B) = 1 - mean_seed cold_frac(t, B)

Shows that mid-budget negative Δfrac is not solely a B=100 ceiling artefact.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parents[1]
GRID = ROOT / "results" / "external_edbo_suzuki"
STATS = ROOT / "results" / "paper_stats"
FIGS = ROOT / "docs" / "figs"
REPS = ("morgan", "drfp", "dft")
BUDGETS = (40, 50, 100)
NEAR = 0.02


def load_cold_target_curves(rep: str) -> pd.DataFrame:
    rows = []
    for p in GRID.glob(f"cold_start__{rep}__*.json"):
        d = json.loads(p.read_text(encoding="utf-8"))
        curve = [float(v) for v in d["bo"]["best_so_far"][:100]]
        gbest = float(d["global_best"])
        rows.append(
            {
                "rep": rep,
                "target": d["target_plate"],
                "seed": int(d["seed"]),
                "global_best": gbest,
                "curve": curve,
            }
        )
    return pd.DataFrame(rows)


def cold_headroom_table(cold: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (rep, tgt), g in cold.groupby(["rep", "target"]):
        gbest = float(g["global_best"].iloc[0])
        for B in BUDGETS:
            ys = np.asarray([c[B - 1] for c in g["curve"]], float)
            frac = ys / gbest
            rows.append(
                {
                    "rep": rep,
                    "target": tgt,
                    "budget": B,
                    "n_seeds": len(g),
                    "cold_yield_mean": float(ys.mean()),
                    "cold_frac_mean": float(frac.mean()),
                    "headroom": float(1.0 - frac.mean()),
                    "global_best": gbest,
                }
            )
    return pd.DataFrame(rows)


def merge_delta(head: pd.DataFrame, pair_by_tgt: pd.DataFrame) -> pd.DataFrame:
    d = pair_by_tgt[pair_by_tgt.metric == "frac"][
        ["rep", "target", "budget", "delta_mean", "delta_ci_lo", "delta_ci_hi"]
    ].rename(columns={"delta_mean": "delta_frac"})
    y = pair_by_tgt[pair_by_tgt.metric == "yield"][
        ["rep", "target", "budget", "delta_mean"]
    ].rename(columns={"delta_mean": "delta_yield"})
    out = head.merge(d, on=["rep", "target", "budget"], how="left")
    out = out.merge(y, on=["rep", "target", "budget"], how="left")
    return out


def plot_headroom_vs_delta(df: pd.DataFrame, out: Path) -> None:
    """Scatter: headroom vs Δfrac, columns=budget, rows=rep."""
    fig, axes = plt.subplots(
        len(REPS), len(BUDGETS), figsize=(10.5, 8.2), dpi=140, sharex=True, sharey=True
    )
    for i, rep in enumerate(REPS):
        for j, B in enumerate(BUDGETS):
            ax = axes[i, j]
            g = df[(df.rep == rep) & (df.budget == B)]
            ax.axhline(0, color="#666", lw=0.8)
            ax.axvline(0, color="#666", lw=0.8, alpha=0.4)
            colors = np.where(
                g.delta_frac > NEAR,
                "#2F6FED",
                np.where(g.delta_frac < -NEAR, "#C45C26", "#8A94A6"),
            )
            ax.scatter(g.headroom, g.delta_frac, c=colors, s=42, zorder=3)
            for r in g.itertuples(index=False):
                ax.text(
                    r.headroom + 0.002,
                    r.delta_frac,
                    r.target.replace("suz_", ""),
                    fontsize=6,
                    color="#444",
                    va="center",
                )
            if i == 0:
                ax.set_title(f"B={B}", fontsize=11)
            if j == 0:
                ax.set_ylabel(f"{rep}\nΔfrac (pair→tgt)")
            if i == len(REPS) - 1:
                ax.set_xlabel("headroom = 1 − cold frac")
    fig.suptitle(
        "EDBO Suzuki · cold headroom vs label−cold Δfrac (target means)",
        y=1.01,
    )
    fig.legend(
        [
            Line2D([0], [0], marker="o", color="w", markerfacecolor="#2F6FED", markersize=7),
            Line2D([0], [0], marker="o", color="w", markerfacecolor="#8A94A6", markersize=7),
            Line2D([0], [0], marker="o", color="w", markerfacecolor="#C45C26", markersize=7),
        ],
        [f"Δ>+{NEAR}", "near 0", f"Δ<−{NEAR}"],
        loc="upper right",
        frameon=False,
        ncol=3,
        fontsize=8,
    )
    fig.tight_layout()
    fig.savefig(out.with_suffix(".png"), bbox_inches="tight")
    fig.savefig(out.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)


def plot_cold_frac_bars(df: pd.DataFrame, out: Path) -> None:
    """Per-target cold frac at B=40/50/100, one panel per rep."""
    targets = sorted(df.target.unique())
    x = np.arange(len(targets))
    width = 0.25
    fig, axes = plt.subplots(1, 3, figsize=(12.5, 4.0), dpi=140, sharey=True)
    for ax, rep in zip(axes, REPS):
        for k, B in enumerate(BUDGETS):
            g = df[(df.rep == rep) & (df.budget == B)].set_index("target").loc[targets]
            ax.bar(
                x + (k - 1) * width,
                g.cold_frac_mean,
                width=width,
                label=f"B={B}",
                color=["#9BB5F5", "#2F6FED", "#1A3A7A"][k],
                edgecolor="none",
            )
        ax.axhline(1.0, color="#999", ls="--", lw=0.8)
        ax.set_xticks(x)
        ax.set_xticklabels([t.replace("suz_", "") for t in targets], rotation=45, ha="right")
        ax.set_ylim(0.55, 1.02)
        ax.set_title(rep)
        ax.set_xlabel("target")
        if ax is axes[0]:
            ax.set_ylabel("cold best-so-far / global best")
        ax.legend(frameon=False, fontsize=8)
    fig.suptitle("EDBO Suzuki · cold-start ceiling by target", y=1.02)
    fig.tight_layout()
    fig.savefig(out.with_suffix(".png"), bbox_inches="tight")
    fig.savefig(out.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)


def plot_delta_yield_by_target(df: pd.DataFrame, B: int, out: Path) -> None:
    """Grouped bars: absolute Δyield by target × rep at fixed B."""
    targets = sorted(df.target.unique())
    x = np.arange(len(targets))
    width = 0.25
    fig, ax = plt.subplots(figsize=(9.5, 4.2), dpi=140)
    colors = {"morgan": "#2F6FED", "drfp": "#0D9488", "dft": "#C97A1A"}
    for k, rep in enumerate(REPS):
        g = df[(df.rep == rep) & (df.budget == B)].set_index("target").loc[targets]
        ax.bar(
            x + (k - 1) * width,
            g.delta_yield,
            width=width,
            label=rep,
            color=colors[rep],
            edgecolor="none",
        )
    ax.axhline(0, color="#333", lw=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels([t.replace("suz_", "") for t in targets], rotation=45, ha="right")
    ax.set_ylabel("Δyield (pp), pair→target mean")
    ax.set_xlabel("target")
    ax.set_title(f"EDBO Suzuki · absolute label−cold Δyield @ B={B}")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(out.with_suffix(".png"), bbox_inches="tight")
    fig.savefig(out.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)


def plot_headroom_summary(df: pd.DataFrame, out: Path) -> None:
    """One-panel summary at B=40: headroom vs Δfrac, color=rep, annotate targets."""
    g = df[df.budget == 40]
    fig, ax = plt.subplots(figsize=(6.4, 4.8), dpi=140)
    colors = {"morgan": "#2F6FED", "drfp": "#0D9488", "dft": "#C97A1A"}
    ax.axhline(0, color="#666", lw=0.8)
    for rep in REPS:
        sub = g[g.rep == rep]
        ax.scatter(
            sub.headroom,
            sub.delta_frac,
            s=55,
            c=colors[rep],
            label=rep,
            zorder=3,
            alpha=0.9,
        )
    # mean per rep
    for rep in REPS:
        sub = g[g.rep == rep]
        ax.scatter(
            [sub.headroom.mean()],
            [sub.delta_frac.mean()],
            s=120,
            c=colors[rep],
            marker="D",
            edgecolors="k",
            linewidths=0.6,
            zorder=4,
        )
    ax.set_xlabel("headroom = 1 − mean cold frac @ B=40")
    ax.set_ylabel("Δfrac (label − cold), target mean")
    ax.set_title("EDBO Suzuki · mid-budget headroom vs transfer (B=40)")
    ax.legend(frameon=False, title="◇ = rep mean")
    fig.tight_layout()
    fig.savefig(out.with_suffix(".png"), bbox_inches="tight")
    fig.savefig(out.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", nargs="+", default=list(REPS))
    args = ap.parse_args()
    STATS.mkdir(parents=True, exist_ok=True)
    FIGS.mkdir(parents=True, exist_ok=True)

    cold_frames = [load_cold_target_curves(r) for r in args.reps]
    cold = pd.concat(cold_frames, ignore_index=True)
    head = cold_headroom_table(cold)

    pair_tgt = pd.read_csv(STATS / "edbo_suzuki_pair_by_target_by_budget.csv")
    # ensure yield rows exist for requested budgets
    merged = merge_delta(head, pair_tgt)
    merged.to_csv(STATS / "edbo_suzuki_headroom_by_target.csv", index=False)

    plot_headroom_vs_delta(
        merged, FIGS / "fig_edbo_suzuki_headroom_vs_delta_frac"
    )
    plot_headroom_summary(
        merged, FIGS / "fig_edbo_suzuki_headroom_vs_delta_frac_B40"
    )
    plot_cold_frac_bars(merged, FIGS / "fig_edbo_suzuki_cold_ceiling_by_target")
    plot_delta_yield_by_target(
        merged, 40, FIGS / "fig_edbo_suzuki_delta_yield_by_target_B40"
    )
    plot_delta_yield_by_target(
        merged, 100, FIGS / "fig_edbo_suzuki_delta_yield_by_target_B100"
    )

    # short note
    note = STATS / "edbo_suzuki_headroom_NOTE.md"
    lines = [
        "# EDBO Suzuki ceiling / headroom",
        "",
        "Unit: target-level (mean of inbound pair effects for Δ; mean of 20 cold seeds for frac).",
        "",
        "## Key reading",
        "",
        "- At B=100, cold frac is typically ≳0.99 → little room for positive Δfrac.",
        "- At B=40/50, headroom is larger and target-mean Δfrac remains ≤0 across reps.",
        "- Therefore C1 mid-budget negatives are **not** explained solely by final ceiling.",
        "",
        "## Cold frac (mean over targets)",
        "",
    ]
    summ = (
        merged.groupby(["rep", "budget"])[["cold_frac_mean", "headroom", "delta_frac"]]
        .mean()
        .round(4)
        .reset_index()
    )
    lines.append("```")
    lines.append(summ.to_string(index=False))
    lines.append("```")
    note.write_text("\n".join(lines), encoding="utf-8")

    print(summ.to_string(index=False))
    print(f"\nwrote {STATS / 'edbo_suzuki_headroom_by_target.csv'}")
    print(f"wrote figs under {FIGS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
