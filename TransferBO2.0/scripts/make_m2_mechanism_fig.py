"""M2 mechanism figure: why Morgan raises the nearest-neighbor AUC.

Key finding (results/step2_m2/summary.md, locked as M2-C): Morgan swaps the
nearest source (100% on amidation) and raises the TOP-5 MAXIMUM yield landed
in the init list (init_best), while the GLOBAL Spearman of the neighbor's
ranking actually DROPS (amination 0.761 -> 0.503). AUC gain comes from the
init channel (M1), so what matters is the top hit, not overall rank corr.

Figure: per library, hashed-NN vs Morgan-NN —
  (a) init_best (what AUC eats)   (b) top-5 max yield   (c) Spearman rank corr
Plot from results/step2_m2/json_init_*.csv + summary.md numbers.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import rcParams

rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial"]
rcParams["axes.unicode_minus"] = False
rcParams["figure.dpi"] = 150

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "figures"

# per-library aggregate (from summary.md; init_best recomputed from CSVs below)
TOP5_MAX = {  # (hashed_NN, morgan_NN, pooled)
    "amination": (62.62, 68.60, 65.72),
    "suzuki": (68.15, 78.69, 70.19),
}
SPEARMAN = {  # (hashed_NN, morgan_NN, pooled)
    "amination": (0.761, 0.503, 0.735),
    "suzuki": (0.337, 0.369, 0.432),
}
SWAP = {"amination": "换源 100%", "suzuki": "换源 42%"}


def main() -> int:
    fig, axes = plt.subplots(1, 3, figsize=(13.0, 4.1))
    libs = ["amination", "suzuki"]
    ib = {lib: [] for lib in libs}
    for lib in libs:
        df = pd.read_csv(ROOT / "results" / "step2_m2" / f"json_init_{lib}.csv")
        ib[lib] = [df["hashed_nn_init_best"].mean(), df["morgan_nn_init_best"].mean(),
                   df["hashed_topk_init_best"].mean()]

    titles = ["(a) init_best：近邻 top-5 落到靶上的最好条件\n（AUC 直接吃的就是它）",
              "(b) top-5 最高产：清单第 1 名的质量",
              "(c) 全局排序 Spearman：近邻排序 vs 靶排序\n（相关性 ≠ 增益来源）"]
    x = np.arange(len(libs))
    colors = ["#8c8c8c", "#1f77b4", "#ff7f0e"]
    labels = ["hashed 近邻", "Morgan 近邻", "池化 topk（参考）"]

    for k, ax in enumerate(axes):
        for j, lib in enumerate(libs):
            if k == 0:
                vals = ib[lib]
            elif k == 1:
                vals = TOP5_MAX[lib]
            else:
                vals = SPEARMAN[lib]
            for i, v in enumerate(vals):
                ax.bar(j - 0.25 + i * 0.25, v, 0.23, color=colors[i], alpha=0.9)
        ax.set_xticks(x); ax.set_xticklabels(libs)
        ax.set_title(titles[k], fontsize=9.5)
        ax.grid(axis="y", alpha=0.25)
        # annotate values
        for j, lib in enumerate(libs):
            vals = ib[lib] if k == 0 else (TOP5_MAX[lib] if k == 1 else SPEARMAN[lib])
            for i, v in enumerate(vals):
                ax.annotate(f"{v:.2f}" if k == 2 else f"{v:.1f}",
                            (j - 0.25 + i * 0.25, v), ha="center",
                            va="bottom" if v >= 0 else "top", fontsize=7.5, color="#333")
        if k == 0:
            # highlight Morgan > pooled on amidation (the "overtake")
            ax.annotate("Morgan 超车池化", (0 - 0.25 + 1 * 0.25, ib["amination"][1]),
                        xytext=(20, 8), textcoords="offset points", fontsize=8.5,
                        color="#1f77b4", fontweight="bold",
                        arrowprops=dict(arrowstyle="->", color="#1f77b4", lw=0.8))
            ax.annotate(SWAP["amination"], (0, ib["amination"][1]), xytext=(0, -14),
                        textcoords="offset points", ha="center", fontsize=8.5, color="#1f77b4")
            ax.annotate(SWAP["suzuki"], (1, ib["suzuki"][1]), xytext=(0, -14),
                        textcoords="offset points", ha="center", fontsize=8.5, color="#1f77b4")
    fig.legend([plt.Rectangle((0, 0), 1, 1, color=c) for c in colors], labels,
               loc="upper center", ncol=3, fontsize=9.5, frameon=False,
               bbox_to_anchor=(0.5, 0.96))
    fig.suptitle("M2 机制：Morgan 近邻翻盘 = 换源 + init max 提高，而非全局排序更准 (M2-C)",
                 fontsize=13, y=0.995)
    # reserve top 20% for title + legend; panels live below
    fig.subplots_adjust(top=0.78, bottom=0.12, left=0.06, right=0.98, wspace=0.22)
    out = OUT / "step2_m2_morgan_mechanism.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
