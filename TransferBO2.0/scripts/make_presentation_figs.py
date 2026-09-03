"""Generate presentation figures for the TransferBO2.0 report PPT (2026-08-24).

Figures (all data from frozen results, bootstrap CIs as computed in the paper):
  fig1_main_forest.png   四库 topk vs cold / vs random（AUC@20 差异森林图）
  fig2_bsf_amination.png 胺化 best-so-far 曲线（topk / cold / random）
  fig3_init_final.png    init_best 与 final_best 对比（更快而非更高）
  fig4_rank_pres.png     五库排序保持 ρ + 池化 top-5 在靶内落位（vs 随机期望）
  fig5_four_arms.png     四臂 warm 续跑实验（B vs A、C vs A、C vs B）
  fig6_quadrant.png      双通道象限图（初始化价值 × 续跑价值）
"""

from __future__ import annotations

import json
import glob
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import rcParams

rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial"]
rcParams["axes.unicode_minus"] = False
rcParams["figure.dpi"] = 160

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "presentation"
OUT.mkdir(parents=True, exist_ok=True)

LIBS = [
    ("胺化", "Pd C–N", "results/amination_v1_full"),
    ("硼化", "Ni C–B", "results/p4_borylation/loso"),
    ("EDBO Suzuki", "Pd C–C", "results/suzuki_v1_full_rt/suzuki_v1_full"),
    ("HiTEA Suzuki", "Pd C–C", "results/p4_hitea/loso"),
]
LIBCOLOR = {"胺化": "#1f77b4", "硼化": "#2ca02c", "EDBO Suzuki": "#ff7f0e", "HiTEA Suzuki": "#9467bd"}


def load_bsf(dirp: str, strat: str) -> dict:
    """target -> mean BSF array over seeds."""
    rows = {}
    for p in glob.glob(str(ROOT / dirp / "*.json")):
        try:
            r = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        if r.get("strategy") != strat or "bo" not in r:
            continue
        bsf = np.asarray(r["bo"].get("best_so_far") or [], dtype=float)
        if len(bsf) < 20:
            continue
        rows.setdefault(r["target_substrate"], []).append(bsf)
    return {t: np.mean(np.vstack(v), axis=0) for t, v in rows.items()}


def boot_ci(d: np.ndarray, n_boot: int = 5000, seed: int = 20260824) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    boot = np.array([d[rng.integers(0, len(d), size=len(d))].mean() for _ in range(n_boot)])
    return np.quantile(boot, [0.025, 0.975])


def summarize(lib: str, dirp: str) -> dict:
    tk = load_bsf(dirp, "topk_warm")
    cold = load_bsf(dirp, "cold_start")
    rnd = load_bsf(dirp, "random")
    tg = sorted(set(tk) & set(cold) & set(rnd))
    a = np.array([tk[t].sum() for t in tg])
    b = np.array([cold[t].sum() for t in tg])
    c = np.array([rnd[t].sum() for t in tg])
    lo1, hi1 = boot_ci(a - b)
    lo2, hi2 = boot_ci(a - c)
    return {
        "lib": lib, "n": len(tg),
        "d_cold": float((a - b).mean()), "ci_cold": (float(lo1), float(hi1)),
        "d_random": float((a - c).mean()), "ci_random": (float(lo2), float(hi2)),
        "bsf_tk": {t: tk[t] for t in tg}, "bsf_cold": {t: cold[t] for t in tg},
        "bsf_rnd": {t: rnd[t] for t in tg},
        "init_tk": float(np.mean([tk[t][:5].max() for t in tg])),
        "init_cold": float(np.mean([cold[t][:5].max() for t in tg])),
        "final_tk": float(np.mean([tk[t][-1] for t in tg])),
        "final_cold": float(np.mean([cold[t][-1] for t in tg])),
    }


def main() -> int:
    res = {name: summarize(name, d) for name, _, d in LIBS}

    # ---------- fig1: main forest ----------
    fig, axes = plt.subplots(1, 2, figsize=(9.8, 3.8), sharey=True)
    for ax, key, title in zip(axes, ["d_cold", "d_random"],
                              ["top-5 清单 vs 冷启动 (cold)", "top-5 清单 vs 随机 (random)"]):
        ys = np.arange(len(res))[::-1]
        for y, (name, r) in zip(ys, res.items()):
            lo, hi = r[f"ci_{'cold' if key == 'd_cold' else 'random'}"]
            ax.errorbar(r[key], y, xerr=[[r[key] - lo], [hi - r[key]]], fmt="o",
                        color=LIBCOLOR[name], markersize=7, capsize=4, linewidth=2)
            ax.annotate(f"{name}\n{'+' if r[key] >= 0 else ''}{r[key]:.0f}  [{lo:+.0f}, {hi:+.0f}]",
                        (r[key], y), textcoords="offset points", xytext=(8, -4), fontsize=8)
        ax.axvline(0, color="gray", ls="--", lw=1)
        ax.set_xlabel("AUC@20 差异（配对标靶 bootstrap 95% CI）")
        ax.set_title(title, fontsize=10, pad=10)
        ax.set_yticks([])
        ax.set_xlim(-45, 350)
    fig.suptitle("主发现：多源池化 top-5 条件清单是唯一跨库一致的正策略", fontsize=12, y=1.02)
    fig.tight_layout()
    fig.savefig(OUT / "fig1_main_forest.png", bbox_inches="tight")
    plt.close(fig)

    # ---------- fig2: amination BSF curve ----------
    am = res["胺化"]
    steps = np.arange(1, 21)
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    for strat, data, color, ls in [("topk_warm", am["bsf_tk"], LIBCOLOR["胺化"], "-"),
                                   ("cold_start", am["bsf_cold"], "#888888", "--"),
                                   ("random", am["bsf_rnd"], "#cccccc", ":")]:
        mean = np.mean([data[t] for t in data], axis=0)
        ax.plot(steps, mean, color=color, ls=ls, lw=2.2, label=strat)
    ax.fill_between(steps, np.mean([am["bsf_cold"][t] for t in am["bsf_cold"]], axis=0),
                    np.mean([am["bsf_tk"][t] for t in am["bsf_tk"]], axis=0),
                    color=LIBCOLOR["胺化"], alpha=0.12)
    ax.set_xlabel("实验步数（前 5 步 = 清单 init）")
    ax.set_ylabel("best-so-far（靶级均值，产率%）")
    ax.set_title("胺化：清单在第 1 轮即拉开差距（更快而非更高）", fontsize=11)
    ax.legend(fontsize=9, loc="lower right")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(OUT / "fig2_bsf_amination.png", bbox_inches="tight")
    plt.close(fig)

    # ---------- fig3: init vs final ----------
    names = list(res.keys())
    init_d = [res[n]["init_tk"] - res[n]["init_cold"] for n in names]
    final_d = [res[n]["final_tk"] - res[n]["final_cold"] for n in names]
    x = np.arange(len(names))
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    b1 = ax.bar(x - 0.19, init_d, 0.38, label="init_best 差异（第 1 轮最好）", color="#1f77b4", alpha=0.85)
    b2 = ax.bar(x + 0.19, final_d, 0.38, label="final_best 差异（20 步终点）", color="#d62728", alpha=0.85)
    for bars in (b1, b2):
        for bar in bars:
            ax.annotate(f"{bar.get_height():+.1f}", (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                        ha="center", va="bottom" if bar.get_height() >= 0 else "top", fontsize=8)
    ax.axhline(0, color="gray", lw=1)
    ax.set_xticks(x); ax.set_xticklabels(names, fontsize=9)
    ax.set_ylabel("vs 冷启动（AUC 单位）")
    ax.set_title("更快而非更高：优势集中在起点，终点基本拉平", fontsize=11)
    ax.legend(fontsize=9)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(OUT / "fig3_init_final.png", bbox_inches="tight")
    plt.close(fig)

    # ---------- fig4: rank preservation ----------
    rho = {"胺化": 0.577, "硼化": 0.361, "EDBO Suzuki": 0.264, "HiTEA Suzuki": 0.088, "CHAOS (1-D)": 0.694}
    names4 = list(rho.keys())
    fig, ax = plt.subplots(figsize=(6.8, 3.4))
    colors = [LIBCOLOR.get(n, "#8c564b") for n in names4]
    ax.barh(np.arange(len(names4)), list(rho.values()), color=colors, alpha=0.9)
    for i, v in enumerate(rho.values()):
        ax.annotate(f"{v:.3f}", (v, i), textcoords="offset points", xytext=(5, -4), fontsize=9)
    ax.set_yticks(np.arange(len(names4))); ax.set_yticklabels(names4, fontsize=9)
    ax.set_xlabel("跨底物条件排序 Spearman ρ")
    ax.set_xlim(0, 0.8)
    ax.axvline(0.5, color="gray", ls="--", lw=1)
    ax.annotate("ρ = 0.5", (0.5, len(names4) - 0.4), fontsize=8, color="gray")
    ax.set_title("排序保持假说：五库全部为正，一维空间最高", fontsize=11)
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(OUT / "fig4_rank_pres.png", bbox_inches="tight")
    plt.close(fig)

    # ---------- fig5: four arms ----------
    arms = [("B vs A（历史 top-5 行 warm）", -59.1, -139.0, -3.6),
            ("C vs A（全部历史 warm）", -28.5, -66.2, 4.3),
            ("C vs B（warm 广度 vs 精度）", 53.3, -13.8, 222.6)]
    fig, ax = plt.subplots(figsize=(7.0, 3.4))
    ys = np.arange(len(arms))[::-1]
    for y, (label, m, lo, hi) in zip(ys, arms):
        ax.errorbar(m, y, xerr=[[m - lo], [hi - m]], fmt="o", color="#d62728" if m < 0 else "#1f77b4",
                    markersize=8, capsize=4, linewidth=2)
        ax.annotate(f"{label}\n{m:+.1f}  [{lo:+.1f}, {hi:+.1f}]", (m, y), textcoords="offset points",
                    xytext=(10, -6), fontsize=8.5)
    ax.axvline(0, color="gray", ls="--", lw=1)
    ax.set_yticks([])
    ax.set_ylim(-0.7, 2.9)
    ax.set_xlabel("AUC@20 差异（Suzuki 类 n=23，配对 bootstrap 95% CI）")
    ax.set_title("把历史产率喂进后段 GP：显著变差（warm 续跑四臂实验）", fontsize=11, pad=10)
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(OUT / "fig5_four_arms.png", bbox_inches="tight")
    plt.close(fig)

    # ---------- fig6: quadrant ----------
    # x = init channel (carried Δ / total), y = continuation channel (topk post)
    quad = {
        "胺化": (278.5, 51.7), "硼化": (185.9, 51.2),
        "EDBO Suzuki": (133.7, 189.0), "HiTEA": (45.8, 92.8),
    }
    fig, ax = plt.subplots(figsize=(6.4, 5.2))
    for name, (x, y) in quad.items():
        ax.scatter(x, y, s=180, color=LIBCOLOR.get(name, "#333"), zorder=3)
        ax.annotate(name, (x, y), textcoords="offset points", xytext=(8, 6), fontsize=9.5)
    ax.axvline(120, color="gray", ls="--", lw=1)
    ax.axhline(90, color="gray", ls="--", lw=1)
    ax.set_xlabel("初始化通道（carried Δ，起点优势）")
    ax.set_ylabel("续跑通道（topk post，后段增益）")
    ax.set_title("双通道机制：价值位置是库相关的\n（高init×低续跑 → 清单即结论；低init×高续跑 → EI 必选）", fontsize=10.5)
    ax.set_xlim(-20, 320); ax.set_ylim(20, 220)
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(OUT / "fig6_quadrant.png", bbox_inches="tight")
    plt.close(fig)

    print("figures written to", OUT)
    for p in sorted(OUT.glob("*.png")):
        print(" ", p.name, p.stat().st_size // 1024, "KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
