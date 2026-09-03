"""Generate one visualization per experiment for the full TransferBO2.0 result inventory.

Every experiment gets its own figure saved under results/figures/<exp>_<name>.png.
Data sources: per-job JSONs (AUC/BSF) and analysis CSVs. All numbers use the
locked bootstrap convention (seed per library as in make_paper_numbers_manifest.py).

Experiments covered (matching docs/28_experiment_catalog.md):
  step1_amination / step1_suzuki          Step1 effect LOSO (hashed, 6 strategies)
  step1b_repA_amination / repA_suzuki     Morgan substrate representation
  step1b_repB_dft_suzuki                  DFT condition pilot
  step1b_repB_morgan_amination/suzuki     Morgan both representation
  ablation_topk_amination                 topk ablation (k/N)
  pair_amination / pair_suzuki            single-source pair pilots
  step2_m1_amination / m1_suzuki          init vs BO decomposition
  step2_m2_pool_vs_nearest                pooling vs nearest (M2)
  p0_suzuki_shared_init                   P0 matched-post audit (Suzuki)
  p0_amination_matched_init               amidation matched-init C1/C2
  p1p2_source_robustness                  source-count threshold curves
  p4_borylation / p4_hitea                external holdouts (main table + per-target)
  mixed: rank_preservation                rank preservation + dual channel
  strategy_list_rules                     list aggregation rules
  strategy_continuation                   continuation decision (C1 by library)
  strategy_probe_gate                     probe gate G0/G1/G2/G3
  rankmed_audit_compare                   rank_median vs mean (AUC layer)
  continuation_arms                       four-arm warm experiment
  chaos_validation                        1-D boundary validation
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
rcParams["figure.dpi"] = 150

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "results" / "figures"
FIG.mkdir(parents=True, exist_ok=True)

N_BOOT = 5000
STRAT_COLOR = {
    "topk_warm": "#1f77b4", "nearest_topk_warm": "#ff7f0e", "sim_weighted": "#2ca02c",
    "safe_gate": "#d62728", "cold_start": "#7f7f7f", "random": "#c7c7c7",
    "topk_random_post": "#9467bd", "cold_random_post": "#8c564b",
    "topk_warm_warmtop5": "#e377c2", "topk_warm_warmall": "#bcbd22",
}
LIB_COLOR = {"amination": "#1f77b4", "suzuki": "#ff7f0e", "borylation": "#2ca02c", "hitea": "#9467bd"}


def boot_ci(d: np.ndarray, seed: int = 0) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    boot = np.array([d[rng.integers(0, len(d), size=len(d))].mean() for _ in range(N_BOOT)])
    return np.quantile(boot, [0.025, 0.975])


def load_bsf(dirp: Path, strat: str) -> dict:
    rows = {}
    for p in sorted(dirp.glob("*.json")):
        try:
            r = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if r.get("strategy") != strat or "bo" not in r:
            continue
        bsf = np.asarray(r["bo"].get("best_so_far") or [], dtype=float)
        if len(bsf) < 20:
            continue
        rows.setdefault(r["target_substrate"], []).append(bsf)
    return {t: np.mean(np.vstack(v), axis=0) for t, v in rows.items()}


def save(fig, name: str, title: str) -> None:
    fig.suptitle(title, fontsize=12, y=1.0)
    fig.tight_layout()
    out = FIG / f"{name}.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"  {out.name}")


def forest(df_means: dict, cis: dict, fname: str, title: str, figname: str, seed: int = 0) -> None:
    """df_means: {strategy: mean}; cis: {strategy: (lo,hi)}"""
    fig, ax = plt.subplots(figsize=(8.0, max(2.6, 0.55 * len(df_means) + 1.2)))
    strategies = list(df_means.keys())
    ys = np.arange(len(strategies))[::-1]
    for y, s in zip(ys, strategies):
        m = df_means[s]
        lo, hi = cis.get(s, (m, m))
        ax.errorbar(m, y, xerr=[[m - lo], [hi - m]], fmt="o", color=STRAT_COLOR.get(s, "#333"),
                    markersize=8, capsize=4, lw=2)
        ax.annotate(f"{s}\n{m:+.1f} [{lo:+.1f}, {hi:+.1f}]", (m, y), xytext=(10, -4),
                    textcoords="offset points", fontsize=8.5)
    ax.axvline(0, color="gray", ls="--", lw=1)
    ax.set_yticks([])
    ax.set_xlabel("Δ AUC@20 vs cold（配对 bootstrap 95% CI）")
    ax.grid(axis="x", alpha=0.25)
    save(fig, figname, title)


def main() -> int:
    R = ROOT / "results"

    # ---------- Step1: amination & suzuki effect forest (locked numbers) ----------
    for lib_key, exp_dir, seed in [("amination", "amination_v1_full", 0), ("suzuki", "suzuki_v1_full_rt/suzuki_v1_full", 0)]:
        d = R / exp_dir
        tk = load_bsf(d, "topk_warm"); cold = load_bsf(d, "cold_start")
        tg = sorted(set(tk) & set(cold))
        means, cis = {}, {}
        for s in ["topk_warm", "nearest_topk_warm", "sim_weighted", "safe_gate", "cold_start"]:
            b = load_bsf(d, s)
            t = sorted(set(tk) & set(b))
            if not t:
                continue
            dd = np.array([tk[x].sum() - b[x].sum() for x in t])
            means[s] = float(dd.mean()); cis[s] = boot_ci(dd, seed)
        forest(means, cis, "step1", f"Step1 效应：{lib_key} 各策略 vs 冷启动",
               f"step1_{lib_key}_effects")

        # BSF curves
        fig, ax = plt.subplots(figsize=(6.6, 3.8))
        steps = np.arange(1, 21)
        for s, ls in [("topk_warm", "-"), ("nearest_topk_warm", "--"), ("cold_start", "-."), ("random", ":")]:
            b = load_bsf(d, s)
            if not b:
                continue
            mean = np.mean([b[t] for t in b], axis=0)
            ax.plot(steps, mean, ls, lw=2, color=STRAT_COLOR.get(s, "#333"), label=s)
        ax.set_xlabel("实验步数（1–5 = init）"); ax.set_ylabel("best-so-far（靶级均值）")
        ax.legend(fontsize=8); ax.grid(alpha=0.25)
        save(fig, f"step1_{lib_key}_bsf", f"Step1 效应：{lib_key} best-so-far 曲线")

    # ---------- Step1b Phase A: Morgan substrate (comparison bar) ----------
    fig, ax = plt.subplots(figsize=(8.2, 3.4))
    dels = []
    for lib, d1, d2 in [("amination", "amination_v1_full", "amination_rep_A_morgan_sub_full"),
                        ("suzuki", "suzuki_v1_full_rt/suzuki_v1_full", "suzuki_rep_A_morgan_sub_full")]:
        h = load_bsf(R / d1, "topk_warm"); m = load_bsf(R / d2, "topk_warm")
        c1 = load_bsf(R / d1, "cold_start"); c2 = load_bsf(R / d2, "cold_start")
        t1 = sorted(set(h) & set(c1)); t2 = sorted(set(m) & set(c2))
        dh = np.mean([h[t].sum() - c1[t].sum() for t in t1])
        dm = np.mean([m[t].sum() - c2[t].sum() for t in t2])
        dels.append((lib + " hashed", dh)); dels.append((lib + " Morgan", dm))
    names = [d[0] for d in dels]; vals = [d[1] for d in dels]
    ax.barh(np.arange(len(vals))[::-1], vals, color=["#1f77b4", "#4c9fd8", "#ff7f0e", "#ffb066"], alpha=0.9)
    for i, v in enumerate(vals):
        ax.annotate(f"{v:+.1f}", (v, len(vals) - 1 - i), xytext=(5, -3), textcoords="offset points", fontsize=9)
    ax.set_yticks(range(len(names))[::-1]); ax.set_yticklabels(names, fontsize=9)
    ax.set_xlabel("topk ΔAUC@20 vs cold"); ax.axvline(0, color="gray", ls="--")
    ax.grid(axis="x", alpha=0.25)
    save(fig, "step1b_repA_morgan_substrate", "Step1b-Phase A：底物 Morgan vs hashed（topk 效应不变性）")

    # ---------- Step1b Phase B: DFT pilot vs OHE ----------
    try:
        cmp = pd.read_csv(R / "step1b_rep_B_suzuki_dft_pilot/compare_dft_vs_phaseA_ohe_same_targets.csv")
        fig, ax = plt.subplots(figsize=(7.4, 3.0))
        x = np.arange(len(cmp))
        ax.bar(x - 0.2, cmp["AUC_ohe_A"], 0.4, label="OHE (Phase A)", color="#1f77b4")
        ax.bar(x + 0.2, cmp["AUC_dft"], 0.4, label="DFT (pilot)", color="#d62728")
        ax.set_xticks(x); ax.set_xticklabels(cmp["strategy"], fontsize=9)
        ax.set_ylabel("AUC@20"); ax.legend(fontsize=9); ax.grid(axis="y", alpha=0.25)
        save(fig, "step1b_repB_dft_pilot", "Step1b-Phase B：Suzuki 条件 DFT 试点（不升全量）")
    except Exception as e:
        print("  skip DFT pilot:", e)

    # ---------- Step2 M1: init vs continuation decomposition ----------
    fig, ax = plt.subplots(figsize=(8.2, 3.6))
    labels, carried, post = [], [], []
    for lib, d in [("amination", "step2_m1/effects_amination.csv"), ("suzuki", "step2_m1/effects_suzuki.csv"),
                   ("borylation", "p4_borylation/loso/loso_summary.csv"), ("hitea", "p4_hitea/loso/loso_summary.csv")]:
        src = R / d
        if not src.exists() and (R / "step2_m1").exists():
            # rebuild from raw jobs for suzuki/amination; borylation/hitea from loso_summary
            pass
        # general: use raw jobs
        base = {"amination": "amination_v1_full", "suzuki": "suzuki_v1_full_rt/suzuki_v1_full",
                "borylation": "p4_borylation/loso", "hitea": "p4_hitea/loso"}[lib]
        tk = load_bsf(R / base, "topk_warm"); cold = load_bsf(R / base, "cold_start")
        t = sorted(set(tk) & set(cold))
        if len(t) < 3:
            continue
        car = np.mean([np.sum(tk[x][:5]) + 15 * tk[x][4] - (np.sum(cold[x][:5]) + 15 * cold[x][4]) for x in t])
        postl = np.mean([np.sum(tk[x]) - (np.sum(tk[x][:5]) + 15 * tk[x][4]) -
                         (np.sum(cold[x]) - (np.sum(cold[x][:5]) + 15 * cold[x][4])) for x in t])
        labels.append(lib); carried.append(car); post.append(postl)
    x = np.arange(len(labels))
    ax.bar(x - 0.2, carried, 0.4, label="carried（init 通道）", color="#1f77b4")
    ax.bar(x + 0.2, post, 0.4, label="post_lift（续跑通道）", color="#d62728")
    for i in range(len(labels)):
        ax.annotate(f"{carried[i]:+.0f}", (i - 0.2, carried[i]), ha="center", va="bottom" if carried[i] > 0 else "top", fontsize=8)
        ax.annotate(f"{post[i]:+.0f}", (i + 0.2, post[i]), ha="center", va="bottom" if post[i] > 0 else "top", fontsize=8)
    ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=10)
    ax.set_ylabel("ΔAUC@20 vs cold 分解"); ax.axhline(0, color="gray", lw=1)
    ax.legend(fontsize=9); ax.grid(axis="y", alpha=0.25)
    save(fig, "step2_m1_init_vs_post", "Step2-M1：init 通道 vs 续跑通道分解（价值位置库相关）")

    # ---------- Step2 M2: pooling vs nearest (per library) ----------
    fig, ax = plt.subplots(figsize=(8.2, 3.4))
    pos = 0; names = []
    for lib, d in [("amination", "amination_v1_full"), ("suzuki", "suzuki_v1_full_rt/suzuki_v1_full"),
                   ("borylation", "p4_borylation/loso"), ("hitea", "p4_hitea/loso")]:
        tk = load_bsf(R / d, "topk_warm"); nr = load_bsf(R / d, "nearest_topk_warm"); cold = load_bsf(R / d, "cold_start")
        t = sorted(set(tk) & set(nr) & set(cold))
        if len(t) < 3:
            continue
        dp = np.mean([tk[x].sum() - cold[x].sum() for x in t])
        dn = np.mean([nr[x].sum() - cold[x].sum() for x in t])
        ax.bar(pos - 0.2, dp, 0.4, color=LIB_COLOR[lib], alpha=0.85)
        ax.bar(pos + 0.2, dn, 0.4, color=LIB_COLOR[lib], alpha=0.35, hatch="//")
        names.append(lib); pos += 1
    ax.set_xticks(range(len(names))); ax.set_xticklabels(names, fontsize=10)
    ax.set_ylabel("ΔAUC@20 vs cold")
    import matplotlib.patches as mpatches
    ax.legend(handles=[mpatches.Patch(color="#555", alpha=0.85, label="池化 top-5"),
                       mpatches.Patch(color="#555", alpha=0.35, hatch="//", label="最近邻 top-5")], fontsize=9)
    ax.grid(axis="y", alpha=0.25)
    save(fig, "step2_m2_pool_vs_nearest", "Step2-M2：池化 top-5 vs 最近邻 top-5（Morgan/Tanimoto）")

    # ---------- P0 Suzuki shared-init + amidation matched-init ----------
    fig, axes = plt.subplots(1, 2, figsize=(9.4, 3.3))
    # Suzuki P0
    d = R / "suzuki_p0_shared_init"
    tk = load_bsf(d, "topk_warm"); tr = load_bsf(d, "topk_random_post")
    cr = load_bsf(R / "suzuki_v1_full_rt/suzuki_v1_full", "cold_start")
    t = sorted(set(tk) & set(tr))
    vals = {"C1  topk+EI − topk+random": np.mean([tk[x].sum() - tr[x].sum() for x in t]),
            "C2  cold+EI − cold+random": float(np.nan)}
    axes[0].bar([0], [vals["C1  topk+EI − topk+random"]], color="#1f77b4")
    axes[0].set_xticks([0]); axes[0].set_xticklabels(["C1"], fontsize=10)
    axes[0].set_title("Suzuki P0：给定 top-5 后 EI 的价值", fontsize=10)
    axes[0].set_ylabel("ΔAUC@20"); axes[0].grid(axis="y", alpha=0.25)
    # amidation matched-init
    d = R / "amination_matched_init_audit"
    tk = load_bsf(d, "topk_warm"); tr = load_bsf(d, "topk_random_post")
    ck = load_bsf(d, "cold_start"); crp = load_bsf(d, "cold_random_post")
    t1 = sorted(set(tk) & set(tr))
    t2 = sorted(set(ck) & set(crp))
    c1 = np.mean([tk[x].sum() - tr[x].sum() for x in t1])
    c2 = np.mean([ck[x].sum() - crp[x].sum() for x in t2])
    axes[1].bar([0, 1], [c1, c2], color=["#1f77b4", "#2ca02c"])
    axes[1].set_xticks([0, 1]); axes[1].set_xticklabels(["C1 (topk)", "C2 (cold)"], fontsize=10)
    axes[1].set_title("胺化 matched-init：EI 增值（C1 弱 / C2 强）", fontsize=10)
    axes[1].set_ylabel("ΔAUC@20"); axes[1].grid(axis="y", alpha=0.25)
    save(fig, "p0_matched_init", "Step3-P0：匹配初始化审计（Suzuki C1 / 胺化 C1-C2）")

    # ---------- P1/P2 source robustness curves ----------
    try:
        fig, ax = plt.subplots(figsize=(7.6, 3.4))
        for lib, col in [("amination", "#1f77b4"), ("suzuki", "#ff7f0e")]:
            df = pd.read_csv(R / f"p1p2_source_robustness/{lib}/pooled_curve_by_n_sources.csv")
            ax.plot(df["n_sources"], df["init_best_target_mean"], "o-", color=col, label=lib)
            ax.axhline(df["full_init_best_target_mean"].iloc[0], color=col, ls="--", lw=0.8, alpha=0.6)
        ax.set_xlabel("历史源数 n"); ax.set_ylabel("池化清单 init_best（靶级均值）")
        ax.set_xticks(sorted(df["n_sources"].unique())); ax.legend(fontsize=9); ax.grid(alpha=0.25)
        save(fig, "p1p2_source_robustness", "Step3-P1/P2：源数门槛（虚线 = 全池；≥3 启用、≥5 推荐）")
    except Exception as e:
        print("  skip p1p2:", e)

    # ---------- P4 external holdouts ----------
    for lib_key, d, seed in [("borylation", "p4_borylation/loso", 20260822), ("hitea", "p4_hitea/loso", 20260822)]:
        d = R / d
        tk = load_bsf(d, "topk_warm"); cold = load_bsf(d, "cold_start")
        tg = sorted(set(tk) & set(cold))
        means, cis = {}, {}
        for s in ["topk_warm", "nearest_topk_warm", "cold_start"]:
            b = load_bsf(d, s)
            t = sorted(set(tk) & set(b))
            dd = np.array([tk[x].sum() - b[x].sum() for x in t])
            means[s] = float(dd.mean()); cis[s] = boot_ci(dd, seed)
        forest(means, cis, "p4", f"P4 外部验证：{lib_key} topk vs 对照", f"p4_{lib_key}_effects", seed)

        # per-target forest (positive fraction visual)
        fig, ax = plt.subplots(figsize=(7.4, 4.2))
        dd = {t: tk[t].sum() - cold[t].sum() for t in tg}
        vals = np.array(list(dd.values())); tnames = list(dd.keys())
        colors = ["#2ca02c" if v > 0 else "#d62728" for v in vals]
        ax.barh(np.arange(len(vals))[::-1], vals, color=colors, alpha=0.85)
        ax.axvline(0, color="gray", ls="--")
        ax.set_yticks(range(len(vals))[::-1]); ax.set_yticklabels(tnames, fontsize=8)
        ax.set_xlabel("topk ΔAUC@20 vs cold（每靶）")
        ax.set_title(f"frac>0 = {np.mean(vals>0):.2f}")
        ax.grid(axis="x", alpha=0.25)
        save(fig, f"p4_{lib_key}_per_target", f"P4 外部验证：{lib_key} 靶级 ΔAUC 分布")

    # ---------- rank preservation ----------
    rho = {"amination": 0.577, "borylation": 0.361, "EDBO Suzuki": 0.264, "HiTEA": 0.088, "CHAOS (1-D)": 0.694}
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.4))
    names = list(rho.keys())
    axes[0].barh(np.arange(len(names))[::-1], list(rho.values()), color="#1f77b4", alpha=0.9)
    for i, v in enumerate(rho.values()):
        axes[0].annotate(f"{v:.3f}", (v, len(names) - 1 - i), xytext=(5, -4), textcoords="offset points", fontsize=9)
    axes[0].set_yticks(range(len(names))[::-1]); axes[0].set_yticklabels(names, fontsize=9)
    axes[0].set_xlim(0, 0.8); axes[0].set_xlabel("跨底物排序 Spearman ρ")
    axes[0].set_title("排序保持（五库全正）", fontsize=10); axes[0].grid(axis="x", alpha=0.25)
    # stability: pooled top5 rank in target ordering
    stab = {"amination": (22.7, 260), "borylation": (14.6, 46), "EDBO Suzuki": (87.7, 308), "HiTEA": (38, 48)}
    labs = list(stab.keys()); means = [stab[k][0] / stab[k][1] for k in labs]
    axes[1].barh(np.arange(len(labs))[::-1], means, color="#ff7f0e", alpha=0.9)
    for i, k in enumerate(labs):
        axes[1].annotate(f"{stab[k][0]}/{stab[k][1]}", (means[i], len(labs) - 1 - i), xytext=(5, -4),
                         textcoords="offset points", fontsize=9)
    axes[1].set_yticks(range(len(labs))[::-1]); axes[1].set_yticklabels(labs, fontsize=9)
    axes[1].set_xlabel("池化 top-5 在靶内排序位置（均值/空间大小）")
    axes[1].set_title("顶部排序更稳（越小越好）", fontsize=10); axes[1].grid(axis="x", alpha=0.25)
    save(fig, "rank_preservation", "排序保持假说验证 + 顶部稳定性")

    # ---------- strategy list rules ----------
    try:
        df = pd.read_csv(R / "strategy_list_rules/four_way_compare.csv")
        fig, ax = plt.subplots(figsize=(7.6, 3.4))
        libs = sorted(df["library"].unique())
        x = np.arange(len(libs))
        m = df.groupby("library")["mean"].mean().reindex(libs).to_numpy()
        rk = df.groupby("library")["rank_median"].mean().reindex(libs).to_numpy()
        ax.bar(x - 0.2, m, 0.4, label="mean（默认）", color="#1f77b4")
        ax.bar(x + 0.2, rk, 0.4, label="rank_median", color="#ff7f0e")
        for i in range(len(libs)):
            ax.annotate(f"{m[i]:+.1f}", (i - 0.2, m[i]), ha="center", va="bottom", fontsize=8)
            ax.annotate(f"{rk[i]:+.1f}", (i + 0.2, rk[i]), ha="center", va="bottom", fontsize=8)
        ax.set_xticks(x); ax.set_xticklabels(libs, fontsize=9)
        ax.set_ylabel("init_best（靶级均值）")
        ax.set_title("清单聚合规则：init 层 mean 与 rank_median 对比", fontsize=10.5)
        ax.legend(fontsize=9); ax.grid(axis="y", alpha=0.25)
        save(fig, "strategy_list_rules", "策略研究-规则：清单聚合规则（mean 默认）")
    except Exception as e:
        print("  skip list rules:", e)

    # ---------- strategy continuation (C1 by library) ----------
    fig, ax = plt.subplots(figsize=(7.6, 3.4))
    libs = ["amination", "borylation", "hitea", "suzuki"]
    c1s = []
    for lib in libs:
        base = {"amination": "amination_v1_full", "suzuki": "suzuki_v1_full_rt/suzuki_v1_full",
                "borylation": "p4_borylation/loso", "hitea": "p4_hitea/loso"}[lib]
        tk = load_bsf(R / base, "topk_warm"); tr = load_bsf(R / base, "topk_random_post")
        t = sorted(set(tk) & set(tr))
        c1s.append(np.mean([tk[x].sum() - tr[x].sum() for x in t]) if t else np.nan)
    ax.bar(libs, c1s, color=[LIB_COLOR[k] for k in libs], alpha=0.9)
    for i, v in enumerate(c1s):
        ax.annotate(f"{v:+.1f}", (i, v), ha="center", va="bottom" if v > 0 else "top", fontsize=10)
    ax.set_ylabel("C1 = topk+EI − topk+random（ΔAUC@20）")
    ax.set_title("续跑价值（C1）库级差异：Suzuki 类 EI 必选", fontsize=11)
    ax.axhline(0, color="gray", lw=1); ax.grid(axis="y", alpha=0.25)
    save(fig, "strategy_continuation_c1", "策略研究-续跑：C1 库级差异（分库规则依据）")

    # ---------- strategy probe gate ----------
    try:
        pt = pd.read_csv(R / "strategy_probe_gate/per_target.csv")
        g = pt.groupby("rule")["init_best"].mean().sort_values(ascending=False)
        fig, ax = plt.subplots(figsize=(7.6, 3.2))
        ax.bar(g.index, g.values, color=["#2ca02c" if r.startswith("G2") else "#1f77b4" if not r.startswith("G3") else "#d62728" for r in g.index], alpha=0.85)
        for i, v in enumerate(g.values):
            ax.annotate(f"{v:.1f}", (i, v), ha="center", va="bottom", fontsize=9)
        ax.set_ylabel("init_best（靶级均值）")
        ax.set_title("探针门 G0–G3：init 层（G2 三库正增益；AUC 层待批量协议验证）", fontsize=10.5)
        ax.tick_params(axis="x", labelsize=8)
        ax.grid(axis="y", alpha=0.25)
        save(fig, "strategy_probe_gate", "策略研究-门控：G2 选源池化 init 层信号")
    except Exception as e:
        print("  skip probe gate:", e)

    # ---------- rankmed audit compare ----------
    try:
        df = pd.read_csv(R / "rankmed_audit_compare/per_target.csv")
        fig, ax = plt.subplots(figsize=(7.8, 3.4))
        dh = df.groupby("library").apply(
            lambda g: float(np.mean(g["auc_new"] - g["auc_old"])), include_groups=False).reset_index()
        dh.columns = ["library", "delta"]
        ax.bar(dh["library"], dh["delta"], color="#1f77b4", alpha=0.9)
        for i, v in enumerate(dh["delta"]):
            ax.annotate(f"{v:+.1f}", (i, v), ha="center", va="bottom" if v > 0 else "top", fontsize=10)
        ax.axhline(0, color="gray", lw=1)
        ax.set_ylabel("rank_median − mean（AUC@20）")
        ax.set_title("rank_median 规则复核：pooled 持平、HiTEA 不显著 → 默认 mean", fontsize=10.5)
        ax.grid(axis="y", alpha=0.25)
        save(fig, "rankmed_audit_compare", "策略研究-规则复核：rank_median vs mean（AUC 层）")
    except Exception as e:
        print("  skip rankmed:", e)

    # ---------- continuation arms (four-arm) ----------
    df = pd.read_csv(R / "continuation_arms_compare/per_target.csv")
    fig, ax = plt.subplots(figsize=(7.6, 3.4))
    contrasts = [("B vs A (warm top-5)", "auc_B", "auc_A"), ("C vs A (warm all)", "auc_C", "auc_A"),
                 ("C vs B", "auc_C", "auc_B")]
    vals = [np.mean(df[c] - df[o]) for _, c, o in contrasts]
    ax.bar([c[0] for c in contrasts], vals, color=["#d62728", "#e377c2", "#1f77b4"], alpha=0.9)
    for i, v in enumerate(vals):
        ax.annotate(f"{v:+.1f}", (i, v), ha="center", va="bottom" if v > 0 else "top", fontsize=10)
    ax.axhline(0, color="gray", lw=1); ax.set_ylabel("ΔAUC@20（Suzuki 类 n=23）")
    ax.set_title("四臂 warm 实验：历史进后段 GP 显著变差", fontsize=11)
    ax.grid(axis="y", alpha=0.25)
    save(fig, "continuation_arms", "策略研究-四臂：warm 续跑负结果")

    # ---------- CHAOS ----------
    dfc = pd.read_csv(R / "chaos_validation/per_target.csv")
    if "target" in dfc.columns:
        dfc = dfc.set_index("target")
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.2))
    axes[0].bar(dfc.columns, dfc.mean(), color=["#c7c7c7", "#7f7f7f", "#1f77b4", "#ff7f0e", "#9467bd"], alpha=0.9)
    axes[0].set_title("CHAOS 一维：AUC@20 各策略均值", fontsize=10)
    axes[0].tick_params(axis="x", labelsize=8)
    dtk = dfc["topk_warm"] - dfc["cold_start"]
    axes[1].barh(np.arange(len(dtk))[::-1], dtk, color=["#2ca02c" if v > 0 else "#d62728" for v in dtk], alpha=0.9)
    for i, v in enumerate(dtk):
        axes[1].annotate(f"{v:+.1f}", (v, len(dtk) - 1 - i), xytext=(4, -3), textcoords="offset points", fontsize=8)
    axes[1].set_yticks(range(len(dtk))[::-1]); axes[1].set_yticklabels(dtk.index, fontsize=8)
    axes[1].set_xlabel("topk ΔAUC@20 vs cold（4/4 靶正）")
    axes[1].set_title("CHAOS 一维边界验证", fontsize=10); axes[1].grid(axis="x", alpha=0.25)
    save(fig, "chaos_validation", "CHAOS 一维边界验证（n=4，方向性）")

    print("DONE →", FIG)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
