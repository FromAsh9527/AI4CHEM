#!/usr/bin/env python
"""Step2 M1: is topk gain in the init queries or in later BO?

Decompose optimisation AUC (sum of best-so-far) into:
  AUC_init        = sum(bsf[0:n_init])
  AUC_post_held   = n_post * bsf[n_init-1]   # carry-forward of init level
  AUC_post_lift   = sum(bsf[n_init:] - init_best)  # extra from later improvements
  AUC_full        = AUC_init + AUC_post_held + AUC_post_lift

If Δ vs cold is almost all in (AUC_init + AUC_post_held), the product is a
warm-start list, not a smarter GP.

Inference: seed-mean then bootstrap across targets (same as Step1).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from analyze_step1_effects import _bootstrap_mean_ci  # noqa: E402

STRATS = [
    "random",
    "cold_start",
    "topk_warm",
    "nearest_topk_warm",
    "sim_weighted",
    "safe_gate",
]
FOCUS = ("topk_warm", "nearest_topk_warm", "cold_start", "random")


def _bsf_from_job(obj: dict) -> np.ndarray:
    stats = obj.get("stats") or {}
    bsf = stats.get("best_so_far")
    if bsf:
        return np.asarray(bsf, dtype=float)
    values = (obj.get("bo") or {}).get("values") or []
    out, cur = [], -np.inf
    for v in values:
        cur = max(cur, float(v))
        out.append(cur)
    return np.asarray(out, dtype=float)


def load_jobs(results_dir: Path, n_init: int) -> pd.DataFrame:
    rows = []
    for path in sorted(results_dir.glob("*.json")):
        if path.name in {"loso_records.json"}:
            continue
        obj = json.loads(path.read_text(encoding="utf-8"))
        strat = obj.get("strategy")
        if strat not in STRATS:
            continue
        bsf = _bsf_from_job(obj)
        if len(bsf) < n_init + 1:
            continue
        n_post = len(bsf) - n_init
        init_best = float(bsf[n_init - 1])
        final_best = float(bsf[-1])
        auc_init = float(bsf[:n_init].sum())
        auc_post_held = float(n_post * init_best)
        auc_post_lift = float((bsf[n_init:] - init_best).sum())
        auc_full = float(bsf.sum())
        rows.append(
            {
                "strategy": strat,
                "target": obj["target_substrate"],
                "seed": int(obj["seed"]),
                "budget": int(len(bsf)),
                "n_init": int(n_init),
                "n_post": int(n_post),
                "auc_full": auc_full,
                "auc_init": auc_init,
                "auc_post_held": auc_post_held,
                "auc_post_lift": auc_post_lift,
                "init_best": init_best,
                "final_best": final_best,
                "post_lift": final_best - init_best,
                "hit_in_init": int(np.isclose(init_best, final_best)),
            }
        )
        for t, v in enumerate(bsf, start=1):
            rows[-1][f"_bsf_{t}"] = float(v)
    return pd.DataFrame(rows)


def target_means(jobs: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    return jobs.groupby(["strategy", "target"], as_index=False)[cols].mean()


def vs_baseline(tm: pd.DataFrame, col: str, baseline: str) -> pd.DataFrame:
    base = tm[tm["strategy"] == baseline].set_index("target")[col]
    rows = []
    for strat in STRATS:
        sub = tm[tm["strategy"] == strat].set_index("target")[col]
        d = (sub - base).dropna()
        mean, lo, hi = _bootstrap_mean_ci(d.to_numpy())
        if strat == baseline:
            mean = lo = hi = 0.0
            frac = float("nan")
        else:
            frac = float((d > 0).mean()) if len(d) else float("nan")
        rows.append(
            {
                "strategy": strat,
                "metric": col,
                "baseline": baseline,
                "mean": float(tm[tm["strategy"] == strat][col].mean())
                if strat in set(tm["strategy"])
                else float("nan"),
                "delta_mean": mean,
                "delta_ci_lo": lo,
                "delta_ci_hi": hi,
                "frac_gt": frac,
                "n_targets": int(len(d)),
            }
        )
    return pd.DataFrame(rows)


def effects_table(tm: pd.DataFrame, metrics: list[str]) -> pd.DataFrame:
    frames = []
    for col in metrics:
        for base in ("cold_start", "random"):
            frames.append(vs_baseline(tm, col, base))
    return pd.concat(frames, ignore_index=True)


def share_of_delta(tm: pd.DataFrame, strat: str, baseline: str) -> dict:
    a = tm[tm["strategy"] == strat].set_index("target")
    b = tm[tm["strategy"] == baseline].set_index("target")
    idx = a.index.intersection(b.index)
    d_full = (a.loc[idx, "auc_full"] - b.loc[idx, "auc_full"]).astype(float)
    d_init = (a.loc[idx, "auc_init"] - b.loc[idx, "auc_init"]).astype(float)
    d_held = (a.loc[idx, "auc_post_held"] - b.loc[idx, "auc_post_held"]).astype(float)
    d_lift = (a.loc[idx, "auc_post_lift"] - b.loc[idx, "auc_post_lift"]).astype(float)
    d_carried = d_init + d_held
    full_mean = float(d_full.mean())
    out = {
        "strategy": strat,
        "baseline": baseline,
        "d_full": full_mean,
        "d_init": float(d_init.mean()),
        "d_post_held": float(d_held.mean()),
        "d_post_lift": float(d_lift.mean()),
        "d_carried": float(d_carried.mean()),
        "share_carried": float(d_carried.mean() / full_mean) if full_mean else float("nan"),
        "share_lift": float(d_lift.mean() / full_mean) if full_mean else float("nan"),
        "frac_targets_carried_gt_lift": float((d_carried.abs() >= d_lift.abs()).mean()),
    }
    return out


def mean_bsf_curve(jobs: pd.DataFrame) -> pd.DataFrame:
    bsf_cols = sorted(
        [c for c in jobs.columns if c.startswith("_bsf_")],
        key=lambda x: int(x.split("_")[-1]),
    )
    recs = []
    for strat, g in jobs.groupby("strategy"):
        # seed-mean per target then mean over targets
        per_t = g.groupby("target")[bsf_cols].mean()
        mu = per_t.mean(axis=0)
        for col, val in mu.items():
            recs.append(
                {
                    "strategy": strat,
                    "step": int(col.split("_")[-1]),
                    "bsf_target_mean": float(val),
                }
            )
    return pd.DataFrame(recs)


def plot_curves(curve: pd.DataFrame, title: str, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(7.2, 4.0))
    colors = {
        "random": "#888888",
        "cold_start": "#4c78a8",
        "topk_warm": "#2ca02c",
        "nearest_topk_warm": "#ff7f0e",
        "sim_weighted": "#9467bd",
        "safe_gate": "#17becf",
    }
    for strat in STRATS:
        sub = curve[curve["strategy"] == strat]
        if sub.empty:
            continue
        ax.plot(
            sub["step"],
            sub["bsf_target_mean"],
            label=strat,
            color=colors.get(strat, "black"),
            lw=2.0 if strat in FOCUS else 1.2,
            alpha=1.0 if strat in FOCUS else 0.45,
        )
    ax.axvline(5.5, color="#bbbbbb", ls="--", lw=1, label="n_init=5")
    ax.set_xlabel("query step")
    ax.set_ylabel("best-so-far (target-mean yield)")
    ax.set_title(title)
    ax.legend(fontsize=8, loc="lower right")
    fig.tight_layout()
    fig.savefig(out, dpi=140)
    plt.close(fig)


def plot_share(shares: list[dict], title: str, out: Path) -> None:
    labels, carried, lift = [], [], []
    for s in shares:
        labels.append(f"{s['strategy']}\nvs {s['baseline']}")
        carried.append(s["d_carried"])
        lift.append(s["d_post_lift"])
    x = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ax.bar(x, carried, label="init + carry-forward", color="#2ca02c")
    ax.bar(x, lift, bottom=carried, label="later BO lift", color="#4c78a8")
    ax.axhline(0, color="#333", lw=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylabel("ΔAUC (target mean)")
    ax.set_title(title)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out, dpi=140)
    plt.close(fig)


def fmt_ci(mean: float, lo: float, hi: float) -> str:
    return f"{mean:+.1f} [{lo:+.1f}, {hi:+.1f}]"


def write_md(
    name: str,
    jobs: pd.DataFrame,
    tm: pd.DataFrame,
    effects: pd.DataFrame,
    shares: list[dict],
    out: Path,
) -> None:
    n_t = jobs["target"].nunique()
    n_s = jobs["seed"].nunique()
    lines = [
        f"# Step2 M1 — init vs later BO ({name})",
        "",
        f"jobs={len(jobs)}, targets={n_t}, seeds={n_s}; n_init=5, rest = later BO.",
        "AUC = Σ best-so-far（与 Step1 相同）。",
        "",
        "- **AUC_init**：前 5 步 BSF 之和",
        "- **AUC_post_held**：若此后不再提升，后 15 步贡献 = 15 × init_best",
        "- **AUC_post_lift**：后 15 步因 BSF 继续上升多出来的面积",
        "- **carried** = AUC_init + AUC_post_held（init 通道）",
        "",
        "## 水平（靶级均值）",
        "",
        "| strategy | AUC | AUC_init | carried | post_lift | init_best | final_best | frac final=init |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for strat in STRATS:
        sub = tm[tm["strategy"] == strat]
        if sub.empty:
            continue
        frac_hit = float(jobs[jobs["strategy"] == strat]["hit_in_init"].mean())
        lines.append(
            f"| {strat} | {sub['auc_full'].mean():.1f} | {sub['auc_init'].mean():.1f} | "
            f"{(sub['auc_init']+sub['auc_post_held']).mean():.1f} | "
            f"{sub['auc_post_lift'].mean():.1f} | {sub['init_best'].mean():.2f} | "
            f"{sub['final_best'].mean():.2f} | {frac_hit:.2f} |"
        )

    def grab(metric: str, strat: str, base: str) -> pd.Series:
        g = effects[
            (effects["metric"] == metric)
            & (effects["strategy"] == strat)
            & (effects["baseline"] == base)
        ]
        return g.iloc[0]

    lines += [
        "",
        "## topk vs cold / random（分段 ΔAUC）",
        "",
        "| 对比 | Δ full | Δ init | Δ carried | Δ post_lift | carried 占比 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for strat in ("topk_warm", "nearest_topk_warm"):
        for base in ("cold_start", "random"):
            sh = next(s for s in shares if s["strategy"] == strat and s["baseline"] == base)
            g_full = grab("auc_full", strat, base)
            lines.append(
                f"| {strat} − {base} | {fmt_ci(g_full['delta_mean'], g_full['delta_ci_lo'], g_full['delta_ci_hi'])} "
                f"| {sh['d_init']:+.1f} | {sh['d_carried']:+.1f} | {sh['d_post_lift']:+.1f} | "
                f"{sh['share_carried']:.2f} |"
            )

    topk_c = next(s for s in shares if s["strategy"] == "topk_warm" and s["baseline"] == "cold_start")
    topk_r = next(s for s in shares if s["strategy"] == "topk_warm" and s["baseline"] == "random")
    g_ib = grab("init_best", "topk_warm", "cold_start")
    g_lift = grab("post_lift", "topk_warm", "cold_start")

    if topk_c["share_carried"] >= 0.7:
        verdict = (
            "**对 cold：增益主要在 init 通道**（更好的起点被后续 15 步带着走；"
            "cold 的 post_lift 往往更大，因为起点更差、还有空间涨）。"
            "相对 cold，交付物优先是历史高产条件清单，不是更聪明的 GP。"
        )
    elif topk_c["share_lift"] >= 0.5:
        verdict = (
            "**对 cold：后续 BO 仍贡献过半 ΔAUC。**"
            "warm-start 不够，还要解释/改进采集与模型。"
        )
    else:
        verdict = (
            "**对 cold：init 通道与后续 BO 都有贡献。**"
            "清单是主杠杆，但不排除后续轨迹差异。"
        )
    if topk_r["share_lift"] >= 0.5 and topk_r["share_carried"] < 0.5:
        verdict += (
            " **对 random：净增益更多来自后 15 步**"
            "（random 的 5-shot 运气可接近 topk 的 init_best，之后随机续采不如 BO）。"
        )

    lines += [
        "",
        "## 读法",
        "",
        f"- topk vs cold：carried 占比 **{topk_c['share_carried']:.2f}**，"
        f"post_lift Δ = **{topk_c['d_post_lift']:+.1f}**（full Δ = {topk_c['d_full']:+.1f}）",
        f"- topk vs random：carried 占比 **{topk_r['share_carried']:.2f}**，"
        f"post_lift Δ = **{topk_r['d_post_lift']:+.1f}**",
        f"- init_best (topk−cold): {fmt_ci(g_ib['delta_mean'], g_ib['delta_ci_lo'], g_ib['delta_ci_hi'])}",
        f"- post_lift yield (topk−cold): {fmt_ci(g_lift['delta_mean'], g_lift['delta_ci_lo'], g_lift['delta_ci_hi'])}",
        "",
        verdict,
        "",
        "不重开 Step1 数字；本步只解释 AUC 从哪一段来。",
        "",
    ]
    (out / f"summary_{name}.md").write_text("\n".join(lines), encoding="utf-8")


def run_one(name: str, results_dir: Path, out: Path, n_init: int) -> dict:
    jobs = load_jobs(results_dir, n_init=n_init)
    if jobs.empty:
        raise SystemExit(f"No jobs in {results_dir}")
    metric_cols = [
        "auc_full",
        "auc_init",
        "auc_post_held",
        "auc_post_lift",
        "init_best",
        "final_best",
        "post_lift",
    ]
    tm = target_means(jobs, metric_cols)
    effects = effects_table(tm, metric_cols)
    shares = [
        share_of_delta(tm, strat, base)
        for strat in ("topk_warm", "nearest_topk_warm")
        for base in ("cold_start", "random")
    ]
    curve = mean_bsf_curve(jobs)
    jobs_out = jobs.drop(columns=[c for c in jobs.columns if c.startswith("_bsf_")])
    jobs_out.to_csv(out / f"jobs_{name}.csv", index=False)
    tm.to_csv(out / f"target_means_{name}.csv", index=False)
    effects.to_csv(out / f"effects_{name}.csv", index=False)
    pd.DataFrame(shares).to_csv(out / f"share_{name}.csv", index=False)
    curve.to_csv(out / f"bsf_curve_{name}.csv", index=False)
    plot_curves(curve, f"{name}: best-so-far (target mean)", out / f"bsf_curve_{name}.png")
    plot_share(shares, f"{name}: ΔAUC split (init-carried vs later lift)", out / f"share_{name}.png")
    write_md(name, jobs, tm, effects, shares, out)
    return {"name": name, "n_jobs": len(jobs), "shares": shares}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-init", type=int, default=5)
    ap.add_argument("--out", type=Path, default=ROOT / "results" / "step2_m1")
    args = ap.parse_args()
    out = args.out
    out.mkdir(parents=True, exist_ok=True)

    recs = []
    recs.append(
        run_one(
            "amination",
            ROOT / "results" / "amination_v1_full",
            out,
            args.n_init,
        )
    )
    recs.append(
        run_one(
            "suzuki",
            ROOT / "results" / "suzuki_v1_full",
            out,
            args.n_init,
        )
    )

    # combined index
    def _sh(rec, base):
        return next(
            s
            for s in rec["shares"]
            if s["strategy"] == "topk_warm" and s["baseline"] == base
        )

    amin, suz = recs[0], recs[1]
    ac, ar = _sh(amin, "cold_start"), _sh(amin, "random")
    sc, sr = _sh(suz, "cold_start"), _sh(suz, "random")
    lines = [
        "# Step2 M1 — init vs later BO",
        "",
        "材料：Step1 LOSO JSON（OHE+hashed）。不新跑实验。口径：先 seed 平均再跨靶。",
        "",
        "分解：`carried` = 前 5 步面积 + 15×init_best（init 通道）；"
        "`post_lift` = 后 15 步因 BSF 继续上升多出来的面积。",
        "",
        "明细：`summary_amination.md` / `summary_suzuki.md`",
        "",
        "## 胺化",
        "",
        f"- topk vs cold：Δfull **{ac['d_full']:+.1f}** = carried **{ac['d_carried']:+.1f}** "
        f"+ post_lift **{ac['d_post_lift']:+.1f}**（carried 占比 {ac['share_carried']:.0%}）。",
        f"- topk vs random：Δfull **{ar['d_full']:+.1f}**，carried 占比 {ar['share_carried']:.0%}。",
        "- **结论：** 胺化 topk 赢在历史高产条件先做进去；cold 后面涨得更多只是因为起点更差。",
        "",
        "## Suzuki",
        "",
        f"- topk vs cold：Δfull **{sc['d_full']:+.1f}**，carried 占比 **{sc['share_carried']:.0%}** "
        "→ 相对 cold 仍是 init 通道。",
        f"- topk vs random：carried {sr['share_carried']:.0%}，post_lift "
        f"**{sr['d_post_lift']:+.1f}（{sr['share_lift']:.0%}）**。"
        "random 的 5-shot 运气可接近 topk 的 init_best，净增益更多来自后 15 步 BO vs 继续随机。",
        "- **结论：** 对 cold 仍是清单；对 random 不能说「只靠 init」——那是后续 BO vs 随机续采。",
        "",
        "## 给 P2 的一句",
        "",
        "胺化默认交付 = **多源 topk init（k=5）**。先不要为了「让后续 GP 更聪明」去堆模型。"
        "M2 再问：这 5 个点为什么跨底物仍然高产。",
        "",
    ]
    (out / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    print((out / "summary.md").read_text(encoding="utf-8"))
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
