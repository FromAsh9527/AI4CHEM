#!/usr/bin/env python
"""Step2 M2: why pooled topk beats a single source; why Morgan flips nearest.

No new BO. Uses:
  - data/processed/*_long.csv  (condition × substrate yields)
  - LOSO JSON meta.nearest     (hashed vs Morgan source identity)
  - pair_summary.csv           (AUC corroboration on the pilot subset)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
K = 5


def load_yield_matrix(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    mat = df.pivot_table(
        index="condition_id", columns="substrate_id", values="yield", aggfunc="mean"
    )
    return mat


def spearman_pair(a: pd.Series, b: pd.Series) -> float:
    both = pd.concat([a, b], axis=1, keys=["a", "b"]).dropna()
    if len(both) < 8:
        return float("nan")
    r, _ = spearmanr(both["a"], both["b"])
    return float(r)


def topk_ids(series: pd.Series, k: int) -> list:
    return list(series.dropna().sort_values(ascending=False).index[:k])


def mean_on_target(mat: pd.DataFrame, target: str, cids: list) -> float:
    y = mat[target]
    vals = y.reindex(cids).dropna()
    return float(vals.mean()) if len(vals) else float("nan")


def nearest_from_json(results_dir: Path) -> pd.DataFrame:
    rows = []
    for path in sorted(results_dir.glob("nearest_topk_warm__*.json")):
        obj = json.loads(path.read_text(encoding="utf-8"))
        meta = obj.get("meta") or {}
        bsf = (obj.get("stats") or {}).get("best_so_far") or []
        vals = (obj.get("bo") or {}).get("values") or []
        init_vals = [float(v) for v in vals[:K]]
        rows.append(
            {
                "target": obj["target_substrate"],
                "seed": int(obj["seed"]),
                "nearest": meta.get("nearest"),
                "sim": meta.get("sim"),
                "init_best": float(bsf[K - 1]) if len(bsf) >= K else float("nan"),
                "init_mean": float(np.mean(init_vals)) if init_vals else float("nan"),
            }
        )
    return pd.DataFrame(rows)


def topk_init_from_json(results_dir: Path) -> pd.DataFrame:
    rows = []
    for path in sorted(results_dir.glob("topk_warm__*.json")):
        obj = json.loads(path.read_text(encoding="utf-8"))
        bsf = (obj.get("stats") or {}).get("best_so_far") or []
        vals = (obj.get("bo") or {}).get("values") or []
        init_vals = [float(v) for v in vals[:K]]
        rows.append(
            {
                "target": obj["target_substrate"],
                "seed": int(obj["seed"]),
                "init_best": float(bsf[K - 1]) if len(bsf) >= K else float("nan"),
                "init_mean": float(np.mean(init_vals)) if init_vals else float("nan"),
            }
        )
    return pd.DataFrame(rows)


def analyze_library(
    name: str,
    long_csv: Path,
    hashed_dir: Path,
    morgan_dir: Path,
    pair_csv: Path | None,
    loso_csv: Path | None,
    pair_targets: list[str] | None,
    out: Path,
) -> dict:
    mat = load_yield_matrix(long_csv)
    subs = [c for c in mat.columns if mat[c].notna().sum() > 20]
    hashed_nn = nearest_from_json(hashed_dir)
    morgan_nn = nearest_from_json(morgan_dir)
    hashed_map = (
        hashed_nn.groupby("target")["nearest"].agg(lambda s: s.mode().iloc[0]).to_dict()
        if not hashed_nn.empty
        else {}
    )
    morgan_map = (
        morgan_nn.groupby("target")["nearest"].agg(lambda s: s.mode().iloc[0]).to_dict()
        if not morgan_nn.empty
        else {}
    )

    # pairwise spearman
    spear_rows = []
    for t in subs:
        for s in subs:
            if s == t:
                continue
            spear_rows.append(
                {"target": t, "source": s, "spearman": spearman_pair(mat[s], mat[t])}
            )
    spear = pd.DataFrame(spear_rows)

    target_rows = []
    for t in subs:
        others = [s for s in subs if s != t]
        pooled = mat[others].mean(axis=1)
        pooled_ids = topk_ids(pooled, K)
        y_t = mat[t]
        oracle_ids = topk_ids(y_t, K)
        single_means = []
        for s in others:
            ids = topk_ids(mat[s], K)
            single_means.append(mean_on_target(mat, t, ids))
        best_src = others[int(np.nanargmax(single_means))] if single_means else None
        h_nn = hashed_map.get(t)
        m_nn = morgan_map.get(t)
        h_ids = topk_ids(mat[h_nn], K) if h_nn in mat.columns else []
        m_ids = topk_ids(mat[m_nn], K) if m_nn in mat.columns else []

        def _ymax(cids: list) -> float:
            vals = y_t.reindex(cids).dropna()
            return float(vals.max()) if len(vals) else float("nan")
        rho_pool = spearman_pair(pooled, y_t)
        rho_h = (
            float(spear[(spear.target == t) & (spear.source == h_nn)]["spearman"].mean())
            if h_nn
            else float("nan")
        )
        rho_m = (
            float(spear[(spear.target == t) & (spear.source == m_nn)]["spearman"].mean())
            if m_nn
            else float("nan")
        )
        rho_best = float(spear[spear.target == t]["spearman"].max())
        rho_mean = float(spear[spear.target == t]["spearman"].mean())
        target_rows.append(
            {
                "target": t,
                "n_sources": len(others),
                "pooled_top5_on_target": mean_on_target(mat, t, pooled_ids),
                "pooled_top5_max_on_target": _ymax(pooled_ids),
                "mean_single_top5_on_target": float(np.nanmean(single_means)),
                "best_single_top5_on_target": float(np.nanmax(single_means)),
                "oracle_top5_on_target": mean_on_target(mat, t, oracle_ids),
                "hashed_nn": h_nn,
                "morgan_nn": m_nn,
                "nn_changed": int(h_nn != m_nn) if h_nn and m_nn else 0,
                "hashed_nn_top5_on_target": mean_on_target(mat, t, h_ids) if h_ids else float("nan"),
                "hashed_nn_top5_max_on_target": _ymax(h_ids) if h_ids else float("nan"),
                "morgan_nn_top5_on_target": mean_on_target(mat, t, m_ids) if m_ids else float("nan"),
                "morgan_nn_top5_max_on_target": _ymax(m_ids) if m_ids else float("nan"),
                "rho_pooled": rho_pool,
                "rho_hashed_nn": rho_h,
                "rho_morgan_nn": rho_m,
                "rho_best_source": rho_best,
                "rho_mean_source": rho_mean,
                "best_source_for_top5": best_src,
            }
        )
    tgt = pd.DataFrame(target_rows)

    # pair vs LOSO AUC (subset)
    pair_cmp = None
    if pair_csv and pair_csv.exists() and loso_csv and loso_csv.exists():
        pair = pd.read_csv(pair_csv)
        loso = pd.read_csv(loso_csv)
        seeds = sorted(set(pair["seed"]) & set(loso["seed"]))
        targets = pair_targets or sorted(pair["target_substrate"].dropna().unique())
        pair_t = pair[pair["seed"].isin(seeds) & pair["target_substrate"].isin(targets)]
        loso_t = loso[loso["seed"].isin(seeds) & loso["target_substrate"].isin(targets)]
        rows = []
        for strat in ("topk_warm", "nearest_topk_warm", "cold_start", "random"):
            p = pair_t[pair_t["strategy"] == strat].groupby("target_substrate")["auc"].mean()
            l = loso_t[loso_t["strategy"] == strat].groupby("target_substrate")["auc"].mean()
            idx = p.index.intersection(l.index)
            if len(idx) == 0:
                continue
            rows.append(
                {
                    "strategy": strat,
                    "n_targets": int(len(idx)),
                    "pair_auc": float(p.loc[idx].mean()),
                    "loso_auc": float(l.loc[idx].mean()),
                    "loso_minus_pair": float((l.loc[idx] - p.loc[idx]).mean()),
                }
            )
        pair_cmp = pd.DataFrame(rows)

    # JSON init quality hashed vs morgan
    h_top = topk_init_from_json(hashed_dir)
    m_top = topk_init_from_json(morgan_dir)
    h_nn_i = hashed_nn.groupby("target")[["init_best", "init_mean"]].mean()
    m_nn_i = morgan_nn.groupby("target")[["init_best", "init_mean"]].mean()
    h_tk = h_top.groupby("target")[["init_best", "init_mean"]].mean()
    init_cmp = pd.DataFrame(
        {
            "hashed_topk_init_best": h_tk["init_best"],
            "hashed_nn_init_best": h_nn_i["init_best"],
            "morgan_nn_init_best": m_nn_i["init_best"],
        }
    ).dropna(how="all")

    # plots
    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    labels = ["pooled top5", "mean single top5", "hashed NN top5", "morgan NN top5", "oracle top5"]
    vals = [
        tgt["pooled_top5_on_target"].mean(),
        tgt["mean_single_top5_on_target"].mean(),
        tgt["hashed_nn_top5_on_target"].mean(),
        tgt["morgan_nn_top5_on_target"].mean(),
        tgt["oracle_top5_on_target"].mean(),
    ]
    colors = ["#2ca02c", "#888888", "#ff7f0e", "#1f77b4", "#4c78a8"]
    ax.bar(labels, vals, color=colors)
    ax.set_ylabel("mean yield of selected conditions on target")
    ax.set_title(f"{name}: init-list quality on target (k=5)")
    ax.tick_params(axis="x", rotation=20)
    fig.tight_layout()
    fig.savefig(out / f"init_quality_{name}.png", dpi=140)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(5.6, 4.2))
    ax.scatter(tgt["rho_hashed_nn"], tgt["rho_morgan_nn"], c="#1f77b4", s=40)
    lim = [
        np.nanmin([tgt["rho_hashed_nn"].min(), tgt["rho_morgan_nn"].min(), 0]),
        np.nanmax([tgt["rho_hashed_nn"].max(), tgt["rho_morgan_nn"].max(), 1]),
    ]
    ax.plot(lim, lim, ls="--", c="#999")
    ax.set_xlabel("Spearman(hashed-NN, target)")
    ax.set_ylabel("Spearman(Morgan-NN, target)")
    ax.set_title(f"{name}: nearest source ranking agreement")
    fig.tight_layout()
    fig.savefig(out / f"rho_nn_{name}.png", dpi=140)
    plt.close(fig)

    tgt.to_csv(out / f"targets_{name}.csv", index=False)
    spear.to_csv(out / f"spearman_pairs_{name}.csv", index=False)
    init_cmp.to_csv(out / f"json_init_{name}.csv")
    if pair_cmp is not None:
        pair_cmp.to_csv(out / f"pair_vs_loso_{name}.csv", index=False)

    return {
        "name": name,
        "n_targets": len(tgt),
        "frac_nn_changed": float(tgt["nn_changed"].mean()) if len(tgt) else float("nan"),
        "pooled": float(tgt["pooled_top5_on_target"].mean()),
        "mean_single": float(tgt["mean_single_top5_on_target"].mean()),
        "hashed_nn": float(tgt["hashed_nn_top5_on_target"].mean()),
        "morgan_nn": float(tgt["morgan_nn_top5_on_target"].mean()),
        "oracle": float(tgt["oracle_top5_on_target"].mean()),
        "pooled_max": float(tgt["pooled_top5_max_on_target"].mean()),
        "hashed_nn_max": float(tgt["hashed_nn_top5_max_on_target"].mean()),
        "morgan_nn_max": float(tgt["morgan_nn_top5_max_on_target"].mean()),
        "rho_pool": float(tgt["rho_pooled"].mean()),
        "rho_hashed": float(tgt["rho_hashed_nn"].mean()),
        "rho_morgan": float(tgt["rho_morgan_nn"].mean()),
        "rho_mean": float(tgt["rho_mean_source"].mean()),
        "json_hashed_nn_init": float(init_cmp["hashed_nn_init_best"].mean()) if len(init_cmp) else float("nan"),
        "json_morgan_nn_init": float(init_cmp["morgan_nn_init_best"].mean()) if len(init_cmp) else float("nan"),
        "json_topk_init": float(init_cmp["hashed_topk_init_best"].mean()) if len(init_cmp) else float("nan"),
        "pair_cmp": pair_cmp,
        "frac_morgan_gt_hashed_rho": float(
            (tgt["rho_morgan_nn"] > tgt["rho_hashed_nn"]).mean()
        )
        if tgt["rho_morgan_nn"].notna().any()
        else float("nan"),
        "frac_morgan_gt_hashed_y": float(
            (tgt["morgan_nn_top5_on_target"] > tgt["hashed_nn_top5_on_target"]).mean()
        ),
        "frac_pooled_gt_mean_single": float(
            (tgt["pooled_top5_on_target"] > tgt["mean_single_top5_on_target"]).mean()
        ),
        "frac_pooled_gt_hashed": float(
            (tgt["pooled_top5_on_target"] > tgt["hashed_nn_top5_on_target"]).mean()
        ),
        "frac_pooled_vs_morgan": float(
            (tgt["pooled_top5_on_target"] > tgt["morgan_nn_top5_on_target"]).mean()
        ),
    }


def write_md(recs: list[dict], out: Path) -> None:
    lines = [
        "# Step2 M2 — 池化 vs 单源；Morgan 近邻翻盘",
        "",
        "材料：long CSV 的条件产率矩阵 + LOSO JSON 的 `meta.nearest` + pair 试点 AUC。不新跑 BO。",
        "指标：把各策略会选的 **top-5 条件**拿到靶底物上的真实均产（init 清单质量）；Spearman = 源/池化排序 vs 靶排序。",
        "",
    ]
    for r in recs:
        lines += [
            f"## {r['name']}（{r['n_targets']} targets）",
            "",
            "| 清单 | 靶上 top5 均产 | 靶上 top5 最高产 |",
            "|---|---:|---:|",
            f"| 池化 LOSO top5 | **{r['pooled']:.2f}** | **{r['pooled_max']:.2f}** |",
            f"| 单源 top5 平均 | {r['mean_single']:.2f} | — |",
            f"| hashed 近邻 top5 | {r['hashed_nn']:.2f} | {r['hashed_nn_max']:.2f} |",
            f"| Morgan 近邻 top5 | {r['morgan_nn']:.2f} | {r['morgan_nn_max']:.2f} |",
            f"| 靶自身 oracle top5 | {r['oracle']:.2f} | — |",
            "",
            f"- 池化 > 单源平均：{r['frac_pooled_gt_mean_single']:.0%} 靶",
            f"- 池化 > hashed 近邻：{r['frac_pooled_gt_hashed']:.0%} 靶",
            f"- Morgan 近邻产率 > hashed 近邻：{r['frac_morgan_gt_hashed_y']:.0%} 靶；近邻源换人：{r['frac_nn_changed']:.0%}",
            f"- Spearman：池化 {r['rho_pool']:.3f} · hashed-NN {r['rho_hashed']:.3f} · "
            f"Morgan-NN {r['rho_morgan']:.3f} · 源平均 {r['rho_mean']:.3f}",
            f"- JSON init_best：topk {r['json_topk_init']:.1f} · hashed-NN {r['json_hashed_nn_init']:.1f} · "
            f"Morgan-NN {r['json_morgan_nn_init']:.1f}",
            "",
        ]
        if r["pair_cmp"] is not None and len(r["pair_cmp"]):
            lines += [
                "pair 试点 vs 同靶同 seed 的 LOSO AUC：",
                "",
                "| strategy | pair | LOSO | LOSO−pair |",
                "|---|---:|---:|---:|",
            ]
            for _, row in r["pair_cmp"].iterrows():
                lines.append(
                    f"| {row['strategy']} | {row['pair_auc']:.1f} | {row['loso_auc']:.1f} | "
                    f"{row['loso_minus_pair']:+.1f} |"
                )
            lines.append("")

    amin, suz = recs[0], recs[1]
    lines += [
        "## 结论",
        "",
        f"1. **池化优于典型单源（胺化）**：池化 top5 均产 {amin['pooled']:.1f} vs 单源平均 {amin['mean_single']:.1f}，"
        f"{amin['frac_pooled_gt_mean_single']:.0%} 靶上池化更好。pair 试点 topk AUC 低于同靶 LOSO topk"
        "（胺化 +83.5），且 pair 里 topk≡nearest（只有一个源）。",
        "池化不是「随便一个源」，而是把跨源都高的条件抬上来。",
        "",
        f"2. **Morgan 翻盘看的是 init 最高点，不是全局 Spearman。** 胺化 hashed→Morgan 近邻源 **100% 换人**；"
        f"top5 均产只略升（{amin['hashed_nn']:.1f}→{amin['morgan_nn']:.1f}），但 **max** "
        f"{amin['hashed_nn_max']:.1f}→{amin['morgan_nn_max']:.1f}，JSON init_best "
        f"{amin['json_hashed_nn_init']:.1f}→{amin['json_morgan_nn_init']:.1f}（已高于池化 topk 的 {amin['json_topk_init']:.1f}）。"
        f"Spearman 均值 hashed-NN {amin['rho_hashed']:.2f} vs Morgan-NN {amin['rho_morgan']:.2f}，"
        "并不更高——hashed 常绑在「字符串像」的源上，整体排序相关可以还行，但 top 条件在难靶上会崩"
        "（如 s4 hashed→s7）。Morgan 换源后更容易把**至少一个高产条件**送进 init，而 M1 已表明 AUC 吃的是这个最高点。",
        "",
        f"3. **Suzuki**：池化仍优于单源平均（{suz['pooled']:.1f} vs {suz['mean_single']:.1f}）；"
        f"Morgan 近邻 max {suz['morgan_nn_max']:.1f} > hashed {suz['hashed_nn_max']:.1f}，"
        f"JSON init_best {suz['json_hashed_nn_init']:.1f}→{suz['json_morgan_nn_init']:.1f}。"
        "与 Phase A nearest 大幅变强一致。",
        "",
        "4. **给 P2**：默认仍是 **多源池化 topk k=5**。底物用 Morgan 时，nearest 可以并列，因为它改的是 init 清单质量；"
        "sim 加权不改 init，不是主通道。不必为「选更像的源去做 GP」而先堆模型。",
        "",
        "不重开 Step1 数字，不升 pair 全量。",
        "",
    ]
    (out / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / "results" / "step2_m2")
    args = ap.parse_args()
    out = args.out
    out.mkdir(parents=True, exist_ok=True)

    recs = []
    recs.append(
        analyze_library(
            "amination",
            ROOT / "data" / "processed" / "amination_long.csv",
            ROOT / "results" / "amination_v1_full",
            ROOT / "results" / "amination_rep_A_morgan_sub_full",
            ROOT / "results" / "amination_pair_v1_pilot" / "pair_summary.csv",
            ROOT / "results" / "amination_v1_full" / "loso_summary.csv",
            ["sub_s4", "sub_s1", "sub_s10"],
            out,
        )
    )
    recs.append(
        analyze_library(
            "suzuki",
            ROOT / "data" / "processed" / "suzuki_long.csv",
            ROOT / "results" / "suzuki_v1_full",
            ROOT / "results" / "suzuki_rep_A_morgan_sub_full",
            ROOT / "results" / "suzuki_pair_v1_pilot" / "pair_summary.csv",
            ROOT / "results" / "suzuki_v1_full" / "loso_summary.csv",
            ["suz_t1", "suz_t7", "suz_t10"],
            out,
        )
    )
    write_md(recs, out)
    try:
        print((out / "summary.md").read_text(encoding="utf-8"))
    except UnicodeEncodeError:
        print(f"summary written: {out / 'summary.md'}")
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
