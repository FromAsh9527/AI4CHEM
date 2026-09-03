#!/usr/bin/env python
"""Validate locked Step1 + Step2 claims against regenerated analyses.

Writes results/step1_step2_validation/report.md and checks.json.
Exit code 0 iff all checks PASS.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from analyze_step1_effects import analyze_one  # noqa: E402
from analyze_step2_m1_init_vs_bo import load_jobs, share_of_delta, target_means  # noqa: E402
from analyze_step2_m2_pool_vs_nearest import analyze_library  # noqa: E402

OUT = ROOT / "results" / "step1_step2_validation"
TOL = 0.25  # AUC / delta absolute tolerance vs frozen table


def _ok(cond: bool, msg: str, detail: str = "") -> dict:
    return {"pass": bool(cond), "check": msg, "detail": detail}


def count_jobs(d: Path) -> int:
    return len(
        [
            p
            for p in d.glob("*.json")
            if p.name not in {"loso_records.json"}
        ]
    )


def frozen_row(effects: pd.DataFrame, strategy: str) -> pd.Series:
    return effects[effects["strategy"] == strategy].iloc[0]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    checks: list[dict] = []

    # --- V1 job counts ---
    n_amin = count_jobs(ROOT / "results" / "amination_v1_full")
    n_suz = count_jobs(ROOT / "results" / "suzuki_v1_full")
    checks.append(_ok(n_amin == 450, "V1 amination jobs == 450", f"got {n_amin}"))
    checks.append(_ok(n_suz == 360, "V1 suzuki jobs == 360", f"got {n_suz}"))

    # --- V2 regenerate Step1 ---
    amin_csv = ROOT / "results" / "amination_v1_full" / "loso_summary.csv"
    suz_csv = ROOT / "results" / "suzuki_v1_full" / "loso_summary.csv"
    if not amin_csv.exists() or not suz_csv.exists():
        checks.append(_ok(False, "V2 loso_summary present", "missing CSV"))
    else:
        rec_a = analyze_one("validate_amin", amin_csv, OUT)
        rec_s = analyze_one("validate_suz", suz_csv, OUT)
        ea, es = rec_a["effects"], rec_s["effects"]

        frozen = {
            ("amination", "topk_warm", "dAUC_vs_cold_mean"): 160.2,
            ("amination", "topk_warm", "dAUC_vs_random_mean"): 268.0,
            ("amination", "cold_start", "dAUC_vs_random_mean"): 107.8,
            ("amination", "nearest_topk_warm", "dAUC_vs_cold_mean"): 117.0,
            ("suzuki", "topk_warm", "dAUC_vs_cold_mean"): 149.9,
            ("suzuki", "topk_warm", "dAUC_vs_random_mean"): 92.2,
            ("suzuki", "cold_start", "dAUC_vs_random_mean"): -57.7,
        }
        for (lib, strat, col), expect in frozen.items():
            e = ea if lib == "amination" else es
            got = float(frozen_row(e, strat)[col])
            checks.append(
                _ok(
                    abs(got - expect) <= TOL,
                    f"V2 {lib} {strat} {col}",
                    f"expect {expect:+.1f} got {got:+.1f} |d|={abs(got-expect):.3f}",
                )
            )

        # win rates
        topk_a = frozen_row(ea, "topk_warm")
        cold_a = frozen_row(ea, "cold_start")
        topk_s = frozen_row(es, "topk_warm")
        cold_s = frozen_row(es, "cold_start")
        checks.append(
            _ok(
                abs(float(cold_a["frac_targets_gt_random"]) - 1.0) < 1e-9,
                "V2 amination cold>random frac == 1.0",
                f"got {cold_a['frac_targets_gt_random']}",
            )
        )
        checks.append(
            _ok(
                float(cold_s["frac_targets_gt_random"]) < 0.5,
                "V2 suzuki cold>random frac < 0.5 (Q1 fail)",
                f"got {cold_s['frac_targets_gt_random']}",
            )
        )
        checks.append(
            _ok(
                float(topk_s["dAUC_vs_cold_mean"]) > 0
                and float(topk_s["dAUC_vs_cold_ci95_lo"]) > 0,
                "V2 suzuki topk vs cold CI > 0",
                f"Δ={topk_s['dAUC_vs_cold_mean']:+.1f} "
                f"[{topk_s['dAUC_vs_cold_ci95_lo']:+.1f}, {topk_s['dAUC_vs_cold_ci95_hi']:+.1f}]",
            )
        )
        checks.append(
            _ok(
                float(topk_a["dAUC_vs_cold_mean"])
                > float(frozen_row(ea, "nearest_topk_warm")["dAUC_vs_cold_mean"]),
                "V2 hashed: topk Δcold > nearest Δcold",
                f"topk {topk_a['dAUC_vs_cold_mean']:+.1f} vs "
                f"nearest {frozen_row(ea, 'nearest_topk_warm')['dAUC_vs_cold_mean']:+.1f}",
            )
        )

    # --- V3 Phase A sanity ---
    rep_a = ROOT / "results" / "amination_rep_A_morgan_sub_full" / "loso_summary.csv"
    if amin_csv.exists() and rep_a.exists():
        h = pd.read_csv(amin_csv)
        m = pd.read_csv(rep_a)
        for strat in ("topk_warm", "cold_start", "random"):
            dh = h[h["strategy"] == strat].groupby("target_substrate")["auc"].mean()
            dm = m[m["strategy"] == strat].groupby("target_substrate")["auc"].mean()
            idx = dh.index.intersection(dm.index)
            max_abs = float((dm.loc[idx] - dh.loc[idx]).abs().max()) if len(idx) else float("nan")
            checks.append(
                _ok(
                    max_abs < 1e-6,
                    f"V3 Phase A unaffected {strat} max|dAUC|~0",
                    f"max|d|={max_abs:.2e}",
                )
            )
        # nearest should change
        dh = h[h["strategy"] == "nearest_topk_warm"].groupby("target_substrate")["auc"].mean()
        dm = m[m["strategy"] == "nearest_topk_warm"].groupby("target_substrate")["auc"].mean()
        idx = dh.index.intersection(dm.index)
        mean_d = float((dm.loc[idx] - dh.loc[idx]).mean())
        checks.append(
            _ok(
                mean_d > 20,
                "V3 Phase A nearest mean AUC rises vs hashed",
                f"mean dAUC={mean_d:+.1f}",
            )
        )
    else:
        checks.append(_ok(False, "V3 Phase A CSVs present", "missing"))

    # --- V4 M1 ---
    jobs = load_jobs(ROOT / "results" / "amination_v1_full", n_init=5)
    tm = target_means(
        jobs,
        [
            "auc_full",
            "auc_init",
            "auc_post_held",
            "auc_post_lift",
            "init_best",
            "final_best",
            "post_lift",
        ],
    )
    sh = share_of_delta(tm, "topk_warm", "cold_start")
    checks.append(
        _ok(
            sh["share_carried"] >= 1.0 and sh["d_post_lift"] < 0,
            "V4 M1 amination topk vs cold: carried>=1 & post_lift<0",
            f"share_carried={sh['share_carried']:.2f} d_lift={sh['d_post_lift']:+.1f} "
            f"d_full={sh['d_full']:+.1f}",
        )
    )
    jobs_s = load_jobs(ROOT / "results" / "suzuki_v1_full", n_init=5)
    tm_s = target_means(
        jobs_s,
        [
            "auc_full",
            "auc_init",
            "auc_post_held",
            "auc_post_lift",
            "init_best",
            "final_best",
            "post_lift",
        ],
    )
    sh_s = share_of_delta(tm_s, "topk_warm", "cold_start")
    checks.append(
        _ok(
            sh_s["share_carried"] >= 0.7,
            "V4 M1 suzuki topk vs cold: carried share >= 0.7",
            f"share_carried={sh_s['share_carried']:.2f}",
        )
    )

    # --- V5/V6 M2 ---
    m2_out = OUT / "m2_scratch"
    m2_out.mkdir(exist_ok=True)
    amin_m2 = analyze_library(
        "amination",
        ROOT / "data" / "processed" / "amination_long.csv",
        ROOT / "results" / "amination_v1_full",
        ROOT / "results" / "amination_rep_A_morgan_sub_full",
        ROOT / "results" / "amination_pair_v1_pilot" / "pair_summary.csv",
        ROOT / "results" / "amination_v1_full" / "loso_summary.csv",
        ["sub_s4", "sub_s1", "sub_s10"],
        m2_out,
    )
    checks.append(
        _ok(
            amin_m2["frac_pooled_gt_mean_single"] >= 0.8,
            "V5 M2 pooled > mean single on >=80% targets",
            f"frac={amin_m2['frac_pooled_gt_mean_single']:.2f} "
            f"pooled={amin_m2['pooled']:.1f} single={amin_m2['mean_single']:.1f}",
        )
    )
    checks.append(
        _ok(
            amin_m2["frac_nn_changed"] >= 0.9,
            "V6 M2 Morgan nearest source changed on >=90% targets",
            f"frac={amin_m2['frac_nn_changed']:.2f}",
        )
    )
    checks.append(
        _ok(
            amin_m2["morgan_nn_max"] > amin_m2["hashed_nn_max"],
            "V6 M2 Morgan NN init max > hashed NN init max",
            f"morgan_max={amin_m2['morgan_nn_max']:.1f} hashed_max={amin_m2['hashed_nn_max']:.1f}",
        )
    )
    if amin_m2["pair_cmp"] is not None and len(amin_m2["pair_cmp"]):
        row = amin_m2["pair_cmp"][amin_m2["pair_cmp"]["strategy"] == "topk_warm"].iloc[0]
        checks.append(
            _ok(
                float(row["loso_minus_pair"]) > 20,
                "V5 M2 LOSO topk AUC > pair topk (same targets)",
                f"LOSO-pair={row['loso_minus_pair']:+.1f}",
            )
        )

    # --- V7 docs ---
    docs = [
        ROOT / "FROZEN_CLAIMS.md",
        ROOT / "docs" / "15_step1_step2_lock.md",
        ROOT / "docs" / "14_strategy_draft.md",
        ROOT / "results" / "step2_m1" / "summary.md",
        ROOT / "results" / "step2_m2" / "summary.md",
        ROOT / "docs" / "13_step1_closeout.md",
    ]
    missing = [str(p.relative_to(ROOT)) for p in docs if not p.exists()]
    checks.append(
        _ok(not missing, "V7 lock documents present", "missing: " + ", ".join(missing) if missing else "ok")
    )

    n_pass = sum(1 for c in checks if c["pass"])
    n_fail = len(checks) - n_pass
    (OUT / "checks.json").write_text(
        json.dumps({"n_pass": n_pass, "n_fail": n_fail, "checks": checks}, indent=2),
        encoding="utf-8",
    )

    lines = [
        "# Step1 + Step2 校验报告",
        "",
        f"日期：再生校验 · PASS={n_pass} FAIL={n_fail} · total={len(checks)}",
        "",
        "| ID | 结果 | 检查 | 明细 |",
        "|---|---|---|---|",
    ]
    for c in checks:
        mark = "PASS" if c["pass"] else "**FAIL**"
        lines.append(f"| {mark} | {mark} | {c['check']} | {c['detail']} |")
    lines += [
        "",
        "## 结论",
        "",
    ]
    if n_fail == 0:
        lines.append("全部通过。`docs/15_step1_step2_lock.md` 可视为生效。")
    else:
        lines.append(f"**{n_fail} 项失败** — 锁档不生效，先修数据/脚本再重跑本校验。")
    lines.append("")
    report = OUT / "report.md"
    report.write_text("\n".join(lines), encoding="utf-8")
    try:
        print(report.read_text(encoding="utf-8"))
    except UnicodeEncodeError:
        print(f"Wrote {report} PASS={n_pass} FAIL={n_fail}")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
