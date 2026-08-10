#!/usr/bin/env python
"""Render stand-in paper figures from existing CSVs into exports/paper_figs/ and docs/figs/."""

from __future__ import annotations

import shutil
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "exports" / "paper_figs"
DOCS = ROOT / "docs" / "figs"
TABLES = ROOT / "exports" / "paper_bundle" / "tables"


def load_hm(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, index_col=0)


def plot_hm_ax(ax, df: pd.DataFrame, title: str, vmin: float = -0.4, vmax: float = 0.4):
    data = df.to_numpy(dtype=float)
    im = ax.imshow(data, cmap="RdBu_r", vmin=vmin, vmax=vmax, aspect="equal")
    ax.set_xticks(range(len(df.columns)))
    ax.set_yticks(range(len(df.index)))
    ax.set_xticklabels([c.replace("plate_", "P") for c in df.columns], fontsize=9)
    ax.set_yticklabels([i.replace("plate_", "P") for i in df.index], fontsize=9)
    ax.set_xlabel("Target")
    ax.set_ylabel("Source")
    ax.set_title(title, fontsize=10)
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            v = data[i, j]
            if np.isfinite(v):
                ax.text(
                    j,
                    i,
                    f"{v:+.2f}",
                    ha="center",
                    va="center",
                    fontsize=7,
                    color="white" if abs(v) > 0.18 else "black",
                )
    return im


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)

    # Fig 3
    fig, axes = plt.subplots(1, 2, figsize=(8.2, 3.8), dpi=200)
    im = None
    for ax, fname, title in [
        (axes[0], "heatmap_delta20_label_warm_morgan.csv", "Label-informed vs random cold"),
        (
            axes[1],
            "heatmap_delta20_diversity_warm_morgan.csv",
            "Diversity init vs random cold\n(= cold_diversity on same library)",
        ),
    ]:
        df = load_hm(TABLES / fname)
        im = plot_hm_ax(ax, df, title)
    fig.colorbar(im, ax=axes.ravel().tolist(), fraction=0.03, pad=0.04, label=r"$\Delta$frac vs random cold")
    fig.suptitle("CHAOS development pairs (Morgan); cell = mean over 20 seeds", fontsize=11, y=1.02)
    fig.savefig(OUT / "fig3_chaos_heatmaps_morgan.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)

    # Fig 4: grouped forest by pair
    pair = pd.read_csv(ROOT / "results" / "paper_stats" / "chaos_pair_level.csv")
    pair = pair[pair["target"].isin(["plate_1", "plate_2", "plate_3"])]
    pair = pair[pair["rep"] == "morgan"]
    order_pairs = (
        pair[pair["strategy"] == "label_warm"][["source", "target"]]
        .drop_duplicates()
        .sort_values(["target", "source"])
        .values.tolist()
    )
    strat_order = ["label_warm", "diversity_warm"]
    colors = {"label_warm": "#1b9e77", "diversity_warm": "#d95f02"}
    markers = {"label_warm": "o", "diversity_warm": "s"}
    labels = {"label_warm": "label pooling", "diversity_warm": "diversity FPS"}

    fig, ax = plt.subplots(figsize=(7.8, 5.2), dpi=200)
    y = 0
    yticks, ylabels = [], []
    for src, tgt in order_pairs:
        for strat in strat_order:
            r = pair[(pair.source == src) & (pair.target == tgt) & (pair.strategy == strat)]
            if r.empty:
                continue
            r = r.iloc[0]
            ax.plot([r.delta_ci_lo, r.delta_ci_hi], [y, y], color=colors[strat], lw=1.6)
            ax.plot(r.delta_frac, y, markers[strat], color=colors[strat], ms=5)
            yticks.append(y)
            ylabels.append(f"{src[-1]}→{tgt[-1]} {labels[strat]}")
            y += 1
        y += 0.35
    ax.axvline(0, color="k", lw=0.8, ls="--")
    ax.set_yticks(yticks)
    ax.set_yticklabels(ylabels, fontsize=7)
    ax.set_xlabel(r"$\Delta$frac vs random cold (within-pair seed bootstrap CI)")
    ax.set_title("CHAOS pair-level transfer (Morgan)\nSeeds ≠ independent transfer tasks; inference unit = pair")
    handles = [
        plt.Line2D([0], [0], marker=markers[k], color=colors[k], label=labels[k], ls="")
        for k in strat_order
    ]
    ax.legend(handles=handles, loc="lower right", fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "fig4_chaos_pair_forest_morgan.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)

    # Fig 5: Doyle pair swarm + target bars
    dp = pd.read_csv(ROOT / "results" / "paper_stats" / "doyle_pair_level.csv")
    dt = pd.read_csv(ROOT / "results" / "paper_stats" / "doyle_target_level.csv")
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.0), dpi=200, gridspec_kw={"width_ratios": [1.35, 1]})

    ax = axes[0]
    for strat, c, off in [("label_warm", "#1b9e77", -0.12), ("diversity_warm", "#d95f02", 0.12)]:
        sub = dp[dp.strategy == strat]
        # jitter by target index
        tgt_codes = {t: i for i, t in enumerate(sorted(sub.target.unique()))}
        xs = np.array([tgt_codes[t] for t in sub.target], float) + off
        xs = xs + np.random.default_rng(0).uniform(-0.05, 0.05, size=len(xs))
        ax.scatter(xs, sub.delta_frac, s=18, alpha=0.65, c=c, label=strat if strat != "diversity_warm" else "diversity init")
    ax.axhline(0, color="k", lw=0.8)
    ax.set_xticks(range(8))
    ax.set_xticklabels([f"s{i}" for i in range(1, 9)])
    ax.set_xlabel("Target substrate")
    ax.set_ylabel(r"Pair $\Delta$frac vs random cold")
    ax.set_title("Doyle: 56 directed pairs")
    ax.legend(fontsize=8)

    ax = axes[1]
    lab = dt[dt.strategy == "label_warm"].sort_values("target")
    div = dt[dt.strategy == "diversity_warm"].sort_values("target")
    x = np.arange(len(lab))
    w = 0.38
    ax.bar(
        x - w / 2,
        lab.delta_frac,
        w,
        yerr=[lab.delta_frac - lab.delta_ci_lo, lab.delta_ci_hi - lab.delta_frac],
        color="#1b9e77",
        label="label_warm",
        capsize=2,
        error_kw={"lw": 0.8},
    )
    ax.bar(
        x + w / 2,
        div.delta_frac,
        w,
        yerr=[div.delta_frac - div.delta_ci_lo, div.delta_ci_hi - div.delta_frac],
        color="#d95f02",
        label="diversity init",
        capsize=2,
        error_kw={"lw": 0.8},
    )
    ax.axhline(0, color="k", lw=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels([t.replace("sub_", "") for t in lab.target], fontsize=9)
    ax.set_xlabel("Target")
    ax.set_ylabel(r"Mean $\Delta$frac (over sources)")
    ax.set_title("Target-level summary")
    ax.legend(fontsize=8)
    fig.suptitle("Doyle external validation (error bars: bootstrap over pairs into each target)", fontsize=11)
    fig.tight_layout()
    fig.savefig(OUT / "fig5_doyle_pairs_and_targets.png", bbox_inches="tight", facecolor="white")
    # keep old name as alias copy
    shutil.copy2(OUT / "fig5_doyle_pairs_and_targets.png", OUT / "fig5_doyle_target_bars.png")
    plt.close(fig)

    # Fig 6 heldout
    h = pd.read_csv(TABLES / "heldout_gate_vs_baselines.csv")
    agg = h.groupby("strategy", as_index=False).agg(delta=("delta_vs_cold", "mean"))
    order = ["diversity_warm", "label_warm", "multitask", "transfer_gate"]
    agg = agg.set_index("strategy").loc[[o for o in order if o in set(agg["strategy"])]].reset_index()
    fig, ax = plt.subplots(figsize=(5.5, 3.6), dpi=200)
    cols = {
        "diversity_warm": "#d95f02",
        "label_warm": "#1b9e77",
        "multitask": "#7570b3",
        "transfer_gate": "#666666",
    }
    ax.bar(range(len(agg)), agg["delta"], color=[cols.get(s, "#333") for s in agg["strategy"]])
    ax.axhline(0, color="k", lw=0.8)
    ax.set_xticks(range(len(agg)))
    ax.set_xticklabels(["diversity init", "label", "pooled", "Gate"])
    ax.set_ylabel(r"Mean $\Delta$frac vs random cold")
    ax.set_title("Held-out plate_4: Gate ≈ always-label")
    fig.tight_layout()
    fig.savefig(OUT / "fig6_heldout_gate.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)

    # Fig SI / main: source fraction dose
    sf = pd.read_csv(ROOT / "results" / "stats" / "si_source_frac.csv")
    fig, ax = plt.subplots(figsize=(6.2, 3.8), dpi=200)
    for (src, tgt), g in sf.groupby(["source", "target"]):
        g = g.sort_values("source_fraction")
        ax.plot(
            g.source_fraction,
            g.delta_vs_cold,
            "-o",
            label=f"{src[-1]}→{tgt[-1]}",
            ms=5,
        )
        ax.fill_between(g.source_fraction, g.delta_ci_lo, g.delta_ci_hi, alpha=0.12)
    ax.axhline(0, color="k", lw=0.8, ls="--")
    ax.set_xlabel("Source-label fraction (of plate; then capped)")
    ax.set_ylabel(r"$\Delta$frac vs random cold")
    ax.set_title("ESI/main: source-label dose response (label_warm, Morgan)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "fig_si_source_fraction.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)

    # label vs cold_diversity bars
    ov = pd.read_csv(ROOT / "results" / "paper_stats" / "chaos_label_vs_cold_diversity_overall.csv")
    fig, ax = plt.subplots(figsize=(4.8, 3.6), dpi=200)
    x = np.arange(len(ov))
    ax.bar(
        x,
        ov.delta_vs_colddiv,
        yerr=[ov.delta_vs_colddiv - ov.ci_lo, ov.ci_hi - ov.delta_vs_colddiv],
        color="#1b9e77",
        capsize=3,
        error_kw={"lw": 0.9},
    )
    ax.axhline(0, color="k", lw=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(ov.rep)
    ax.set_ylabel(r"Mean $\Delta$frac (label − cold_diversity)")
    ax.set_title("CHAOS: label_warm vs target diversity init\n(6 pairs; CI over pairs)")
    fig.tight_layout()
    fig.savefig(OUT / "fig_label_vs_cold_diversity.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)

    def _safe_copy(src: Path, dst: Path) -> None:
        try:
            shutil.copy2(src, dst)
        except PermissionError:
            print(f"skip locked: {dst.name}")

    # sync docs/figs
    for p in OUT.glob("*.png"):
        _safe_copy(p, DOCS / p.name)

    # prefer v2 schematic if present in assets
    cand = Path(
        r"C:\Users\ATHENA\.cursor\projects\f-BaiduSyncdisk-zhangzhou-ed-AI-Pharmacy-AI4CHEM-TransferBO\assets\fig1_same_library_transfer_v2.png"
    )
    if cand.exists():
        for dst in [
            OUT / "fig1_same_library_transfer_schematic.png",
            DOCS / "fig1_same_library_transfer_schematic.png",
            OUT / "fig1_same_library_transfer_v2.png",
            DOCS / "fig1_same_library_transfer_v2.png",
        ]:
            if cand.resolve() != dst.resolve():
                _safe_copy(cand, dst)

    print(f"Wrote {OUT} and synced {DOCS}")
    for p in sorted(OUT.glob("*.png")):
        print(" ", p.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
