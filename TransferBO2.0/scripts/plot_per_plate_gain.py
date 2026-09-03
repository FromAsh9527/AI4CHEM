#!/usr/bin/env python
"""Plot per-plate mean ΔAUC vs cold for amination & Suzuki LOSO full."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "results/figures/per_plate_gain_data.json").read_text(encoding="utf-8"))
OUT = ROOT / "results" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

STRATS = ["topk_warm", "nearest_topk_warm", "sim_weighted", "safe_gate", "random"]
LABELS = {
    "topk_warm": "topk_warm",
    "nearest_topk_warm": "nearest_topk",
    "sim_weighted": "sim_weighted",
    "safe_gate": "safe_gate",
    "random": "random",
}
COLORS = {
    "topk_warm": "#1f4e79",
    "nearest_topk_warm": "#2e75b6",
    "sim_weighted": "#5b9bd5",
    "safe_gate": "#9dc3e6",
    "random": "#a6a6a6",
}


def short(t: str) -> str:
    return t.replace("sub_", "").replace("suz_", "")


def plot_dataset(key: str, title: str, fname: str) -> None:
    d = DATA[key]
    targets = d["targets"]
    labs = [short(t) for t in targets]
    x = np.arange(len(labs))
    width = 0.16

    fig, ax = plt.subplots(figsize=(12, 5.2), dpi=140)
    for i, st in enumerate(STRATS):
        vals = d["mean_dauc"][st]
        ax.bar(
            x + (i - 2) * width,
            vals,
            width,
            label=LABELS[st],
            color=COLORS[st],
            edgecolor="none",
        )
    ax.axhline(0, color="#333", linewidth=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(labs)
    ax.set_xlabel("Target substrate / task (plate)")
    ax.set_ylabel(r"Mean $\Delta$AUC vs cold_start")
    ax.set_title(title)
    ax.legend(
        frameon=False,
        ncol=5,
        loc="upper center",
        bbox_to_anchor=(0.5, 1.14),
        fontsize=9,
    )
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT / fname, bbox_inches="tight")
    plt.close(fig)

    mat = np.array([d["mean_dauc"][st] for st in STRATS])
    fig, ax = plt.subplots(figsize=(11, 3.8), dpi=140)
    vmax = float(np.nanmax(np.abs(mat))) or 1.0
    im = ax.imshow(mat, aspect="auto", cmap="RdBu_r", vmin=-vmax, vmax=vmax)
    ax.set_xticks(range(len(labs)))
    ax.set_xticklabels(labs)
    ax.set_yticks(range(len(STRATS)))
    ax.set_yticklabels([LABELS[s] for s in STRATS])
    ax.set_xlabel("Target substrate / task (plate)")
    ax.set_title(title.replace("grouped bars", "heatmap"))
    cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    cbar.set_label(r"Mean $\Delta$AUC vs cold")
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            v = mat[i, j]
            ax.text(
                j,
                i,
                f"{v:.0f}",
                ha="center",
                va="center",
                fontsize=7,
                color="white" if abs(v) > vmax * 0.55 else "#222",
            )
    fig.tight_layout()
    fig.savefig(OUT / fname.replace(".png", "_heatmap.png"), bbox_inches="tight")
    plt.close(fig)

    cr = d["cold_vs_random"]
    fig, ax = plt.subplots(figsize=(10, 4.2), dpi=140)
    vals = [r["cold_minus_random"] for r in cr]
    cols = ["#1f4e79" if v >= 0 else "#c0504d" for v in vals]
    ax.bar(labs, vals, color=cols, edgecolor="none")
    ax.axhline(0, color="#333", linewidth=0.8)
    ax.set_xlabel("Target substrate / task (plate)")
    ax.set_ylabel("Mean AUC(cold) − AUC(random)")
    ax.set_title(title.split(":")[0] + ": cold vs random by plate")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT / fname.replace(".png", "_cold_vs_random.png"), bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    plot_dataset(
        "amination_v1_full",
        "Amination LOSO full: per-plate mean ΔAUC vs cold (5 seeds)",
        "amination_v1_full_per_plate_dauc.png",
    )
    plot_dataset(
        "suzuki_v1_full",
        "Suzuki LOSO full: per-plate mean ΔAUC vs cold (5 seeds)",
        "suzuki_v1_full_per_plate_dauc.png",
    )
    print(f"Wrote figures under {OUT}")


if __name__ == "__main__":
    main()
