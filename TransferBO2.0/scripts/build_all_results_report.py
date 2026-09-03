#!/usr/bin/env python
"""Build consolidated analysis artifacts for all TransferBO2.0 results."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PACK = json.loads((ROOT / "results" / "all_results_pack.json").read_text(encoding="utf-8"))


def row(name: str, strategy: str) -> dict:
    for r in PACK[name]["effects"]:
        if r["strategy"] == strategy:
            return r
    raise KeyError(strategy)


def fmt(v, nd=1):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    return f"{v:+.{nd}f}" if isinstance(v, float) and v != 0 else f"{v:.{nd}f}"


def per_target_deltas(csv: Path, strategies: list[str]) -> dict:
    df = pd.read_csv(csv)
    tm = df.groupby(["strategy", "target_substrate"])["auc"].mean().unstack(0)
    targets = sorted(tm.index)
    out = {"targets": targets}
    out["cold_minus_random"] = [
        float(tm.loc[t, "cold_start"] - tm.loc[t, "random"]) for t in targets
    ]
    for s in strategies:
        if s in tm.columns:
            out[f"{s}_minus_cold"] = [
                float(tm.loc[t, s] - tm.loc[t, "cold_start"]) for t in targets
            ]
    return out


def main() -> None:
    canvas_data = {
        "step1_amin": {
            "meta": PACK["step1_amin_hashed"]["meta"],
            "effects": PACK["step1_amin_hashed"]["effects"],
            "per_target": per_target_deltas(
                ROOT / "results/amination_v1_full/loso_summary.csv",
                ["topk_warm", "nearest_topk_warm", "sim_weighted", "safe_gate", "random"],
            ),
        },
        "step1_suz": {
            "meta": PACK["step1_suz_hashed"]["meta"],
            "effects": PACK["step1_suz_hashed"]["effects"],
            "per_target": per_target_deltas(
                ROOT / "results/suzuki_v1_full/loso_summary.csv",
                ["topk_warm", "nearest_topk_warm", "sim_weighted", "safe_gate", "random"],
            ),
        },
        "repA_amin": {
            "meta": PACK["repA_amin_morgan"]["meta"],
            "effects": PACK["repA_amin_morgan"]["effects"],
        },
        "repA_suz": {
            "meta": PACK["repA_suz_morgan"]["meta"],
            "effects": PACK["repA_suz_morgan"]["effects"],
            "per_target": per_target_deltas(
                ROOT / "results/suzuki_rep_A_morgan_sub_full/loso_summary.csv",
                ["topk_warm", "nearest_topk_warm", "sim_weighted", "safe_gate", "random"],
            ),
        },
        "repB_dft": {
            "meta": PACK["repB_suz_dft_pilot"]["meta"],
            "effects": PACK["repB_suz_dft_pilot"]["effects"],
            "cmp": pd.read_csv(
                ROOT
                / "results/step1b_rep_B_suzuki_dft_pilot/compare_dft_vs_phaseA_ohe_same_targets.csv"
            ).to_dict("records"),
        },
        "ablation": {
            "meta": PACK["topk_ablation"]["meta"],
            "effects": PACK["topk_ablation"]["effects"],
        },
        "pair_amin": PACK["amin_pair_pilot"],
        "pair_suz": PACK["suz_pair_pilot"],
    }

    # hashed vs morgan delta for nearest (amination)
    canvas_data["morgan_shift_amin"] = {
        "nearest_dc_hashed": row("step1_amin_hashed", "nearest_topk_warm")[
            "dAUC_vs_cold_mean"
        ],
        "nearest_dc_morgan": row("repA_amin_morgan", "nearest_topk_warm")[
            "dAUC_vs_cold_mean"
        ],
        "topk_dc": row("step1_amin_hashed", "topk_warm")["dAUC_vs_cold_mean"],
        "sim_dc_hashed": row("step1_amin_hashed", "sim_weighted")["dAUC_vs_cold_mean"],
        "sim_dc_morgan": row("repA_amin_morgan", "sim_weighted")["dAUC_vs_cold_mean"],
    }
    canvas_data["morgan_shift_suz"] = {
        "nearest_dc_hashed": row("step1_suz_hashed", "nearest_topk_warm")[
            "dAUC_vs_cold_mean"
        ],
        "nearest_dc_morgan": row("repA_suz_morgan", "nearest_topk_warm")[
            "dAUC_vs_cold_mean"
        ],
        "topk_dc": row("step1_suz_hashed", "topk_warm")["dAUC_vs_cold_mean"],
    }

    (ROOT / "results" / "canvas_all_results.json").write_text(
        json.dumps(canvas_data, default=float, indent=2), encoding="utf-8"
    )

    # Markdown report
    lines = [
        "# TransferBO2.0 全部结果汇总",
        "",
        "推断单位均为 **target**（seed 平均后跨靶 bootstrap CI）。",
        "主指标：AUC；增益：ΔAUC vs `cold_start` / vs `random`。",
        "",
        "## 0. 实验清单",
        "",
        "| 轨道 | 规模 | 表示 | 路径 |",
        "|---|---|---|---|",
        "| Step1 胺化 LOSO | 450 = 15×6×5 | OHE + hashed | `amination_v1_full` |",
        "| Step1 Suzuki LOSO | 360 = 12×6×5 | OHE + hashed | `suzuki_v1_full` |",
        "| 胺化 topk 消融 | 525 | OHE + hashed | `amination_topk_ablation` |",
        "| 胺化 pair 试点 | 126 | OHE + hashed | `amination_pair_v1_pilot` |",
        "| Suzuki pair 试点 | 126 | OHE + hashed | `suzuki_pair_v1_pilot` |",
        "| Step1b A 胺化 | 450 | OHE + **morgan_r2** | `amination_rep_A_morgan_sub_full` |",
        "| Step1b A Suzuki | 360 | OHE + **morgan_r2** | `suzuki_rep_A_morgan_sub_full` |",
        "| Step1b B Suzuki DFT 试点 | 36 = 3×6×2 | **DFT** + morgan | `suzuki_rep_B_dft_cond_pilot` |",
        "| Step1b B 胺化 both Morgan | 450 | **morgan** + morgan | `amination_rep_B_morgan_both_full` |",
        "| Step1b B Suzuki both Morgan | 360 | **morgan** + morgan | `suzuki_rep_B_morgan_both_full` |",
        "",
        "## 1. Step1 效应（hashed）— 主锁",
        "",
        "### 胺化",
        "",
        "| strategy | AUC | Δcold [CI] | frac>cold | Δrandom |",
        "|---|---:|---:|---:|---:|",
    ]
    order = [
        "topk_warm",
        "nearest_topk_warm",
        "sim_weighted",
        "safe_gate",
        "cold_start",
        "random",
    ]
    for s in order:
        r = row("step1_amin_hashed", s)
        dc = (
            "—"
            if s == "cold_start"
            else f"{r['dAUC_vs_cold_mean']:+.1f} [{r['dAUC_vs_cold_ci95_lo']:+.1f}, {r['dAUC_vs_cold_ci95_hi']:+.1f}]"
        )
        dr = (
            "—"
            if s == "random"
            else f"{r['dAUC_vs_random_mean']:+.1f}"
        )
        fc = "—" if s == "cold_start" else f"{r['frac_targets_gt_cold']:.2f}"
        lines.append(
            f"| {s} | {r['auc_target_mean']:.1f} | {dc} | {fc} | {dr} |"
        )

    lines += [
        "",
        "**结论**：cold ≫ random（15/15）；**topk_warm** 主正增益；nearest 弱于 topk（hashed）；sim/gate ~null vs cold。",
        "",
        "### Suzuki（Q1 失败 = 基线 BO 备注）",
        "",
        "| strategy | AUC | Δcold [CI] | frac>cold | Δrandom |",
        "|---|---:|---:|---:|---:|",
    ]
    for s in order:
        r = row("step1_suz_hashed", s)
        dc = (
            "—"
            if s == "cold_start"
            else f"{r['dAUC_vs_cold_mean']:+.1f} [{r['dAUC_vs_cold_ci95_lo']:+.1f}, {r['dAUC_vs_cold_ci95_hi']:+.1f}]"
        )
        dr = "—" if s == "random" else f"{r['dAUC_vs_random_mean']:+.1f}"
        fc = "—" if s == "cold_start" else f"{r['frac_targets_gt_cold']:.2f}"
        lines.append(
            f"| {s} | {r['auc_target_mean']:.1f} | {dc} | {fc} | {dr} |"
        )

    lines += [
        "",
        "**结论**：cold ≯ random（仅 4/12）→ **Q1 失败**（冷启动 BO 不可靠）。"
        " topk vs cold **+150** 且 CI 不含 0 → **历史 topk 策略仍成立**；"
        " vs random 弱正（CI 贴 0）→ 可行但脆。禁止把胺化整包叙事平移。**不是**「topk 无效」。",
        "",
        "## 2. topk 消融（胺化）",
        "",
        "| strategy | AUC | Δcold |",
        "|---|---:|---:|",
    ]
    for r in sorted(
        PACK["topk_ablation"]["effects"], key=lambda x: -x["auc_target_mean"]
    ):
        dc = (
            "—"
            if r["strategy"] == "cold_start"
            else f"{r['dAUC_vs_cold_mean']:+.1f}"
        )
        lines.append(f"| {r['strategy']} | {r['auc_target_mean']:.1f} | {dc} |")

    lines += [
        "",
        "**结论**：n_init=5 时 k=5 ≡ k=10；k=3≈k=5；`topk_safe_gate` ≡ k=5（门槛未触发弃权）。",
        "",
        "## 3. Pair 试点（单源→靶）",
        "",
        "### 胺化 pair pilot（策略均值 AUC）",
        "",
        "| strategy | mean AUC |",
        "|---|---:|",
    ]
    for r in sorted(
        PACK["amin_pair_pilot"]["by_strategy"], key=lambda x: -x["auc"]
    ):
        lines.append(f"| {r['strategy']} | {r['auc']:.1f} |")

    lines += [
        "",
        "### Suzuki pair pilot",
        "",
        "| strategy | mean AUC |",
        "|---|---:|",
    ]
    for r in sorted(PACK["suz_pair_pilot"]["by_strategy"], key=lambda x: -x["auc"]):
        lines.append(f"| {r['strategy']} | {r['auc']:.1f} |")

    lines += [
        "",
        "**读法**：pair 非 LOSO；胺化单源 topk 弱于池化 LOSO；Suzuki 仍见 cold≺random 倾向。",
        "",
        "## 4. Step1b Phase A — Morgan 底物",
        "",
        "### 胺化：hashed → Morgan",
        "",
        "| strategy | Δcold hashed | Δcold Morgan | 变化 |",
        "|---|---:|---:|---|",
    ]
    for s in ["topk_warm", "nearest_topk_warm", "sim_weighted", "safe_gate"]:
        h = row("step1_amin_hashed", s)["dAUC_vs_cold_mean"]
        m = row("repA_amin_morgan", s)["dAUC_vs_cold_mean"]
        note = "不变（健全）" if s == "topk_warm" else f"{m - h:+.1f}"
        lines.append(f"| {s} | {h:+.1f} | {m:+.1f} | {note} |")

    lines += [
        "",
        "**结论**：topk 与 hashed **完全一致**；**nearest 升至略高于 topk**（+171 vs +160）；sim 仍近 null。",
        "",
        "### Suzuki：hashed → Morgan",
        "",
        "| strategy | Δcold hashed | Δcold Morgan |",
        "|---|---:|---:|",
    ]
    for s in ["topk_warm", "nearest_topk_warm", "sim_weighted", "safe_gate"]:
        h = row("step1_suz_hashed", s)["dAUC_vs_cold_mean"]
        m = row("repA_suz_morgan", s)["dAUC_vs_cold_mean"]
        lines.append(f"| {s} | {h:+.1f} | {m:+.1f} |")

    lines += [
        "",
        "**结论**：nearest 大幅改善（hashed 时近 null → Morgan +166）。"
        " Q1 仍失败（cold 不稳赢 random）；topk vs cold 与 hashed 相同。不升「与胺化同级」叙事。",
        "",
        "## 5. Step1b Phase B — Suzuki DFT 试点",
        "",
        "| strategy | AUC OHE-A | AUC DFT | DFT−OHE |",
        "|---|---:|---:|---:|",
    ]
    cmp = pd.read_csv(
        ROOT
        / "results/step1b_rep_B_suzuki_dft_pilot/compare_dft_vs_phaseA_ohe_same_targets.csv"
    )
    for _, r in cmp.sort_values("d_dft_minus_ohe").iterrows():
        lines.append(
            f"| {r['strategy']} | {r['AUC_ohe_A']:.1f} | {r['AUC_dft']:.1f} | "
            f"{r['d_dft_minus_ohe']:+.1f} |"
        )

    lines += [
        "",
        "**结论**：**不升全量**。topk 相对 OHE −157；cold≈random。",
        "",
        "## 6. Step1b Phase B — 条件+底物 both Morgan",
        "",
        "条件特征从 OHE→morgan_r2 后，所有 GP 策略都会变；random 应不变（健全性）。",
        "明细：`results/step1b_rep_B_morgan_both/`、`results/step1b_rep_B_morgan_both_suzuki/`。",
        "",
        "**胺化**：random 不变；cold 绝对 AUC 下降；topk Δcold 仍强；nearest ≳ topk。不支持条件 Morgan 全面优于 OHE。",
        "",
        "**Suzuki**：cold 仍 ≯ random；topk Δcold CI 跨 0 → 这套条件表示下 topk 不稳，不是 Step1 OHE 上 topk 失败。",
        "",
        "## 7. 总判断（Step1 收口）",
        "",
        "1. **胺化迁移效应成立**（Step1 锁定）：cold 强基线 + 全局 topk 主增益。",
        "2. **产品标准**：历史策略看 vs cold **和** vs random；**Q1 ≠ 否决票**。Suzuki topk 可行、弱于胺化。",
        "3. **底物 Morgan（Phase A）**：健全；近邻变强，胺化 nearest ≳ topk（不回写 hashed 下的 Q3）。",
        "4. **条件表示（Phase B）**：OHE 保持默认；Morgan/DFT 不升。",
        "5. **下一步**：机制（init vs 后续 BO；池化 vs 近邻），见 `docs/12_plan_after_step1.md`。不再堆表示。",
        "",
        "交互图：打开 Cursor Canvas `transferbo2-all-results.canvas.tsx`。",
        "收口戳：`docs/13_step1_closeout.md`。",
        "",
    ]
    md_path = ROOT / "results" / "ALL_RESULTS_ANALYSIS.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {md_path}")
    print(f"Wrote results/canvas_all_results.json")


if __name__ == "__main__":
    main()
