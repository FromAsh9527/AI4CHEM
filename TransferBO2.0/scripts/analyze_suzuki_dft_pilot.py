#!/usr/bin/env python
"""Summarize Suzuki Phase B DFT pilot vs Phase A OHE (same targets/seeds)."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from analyze_step1_effects import analyze_one, target_means  # noqa: E402


def main() -> int:
    dft_csv = ROOT / "results" / "suzuki_rep_B_dft_cond_pilot" / "loso_summary.csv"
    a_csv = ROOT / "results" / "suzuki_rep_A_morgan_sub_full" / "loso_summary.csv"
    out = ROOT / "results" / "step1b_rep_B_suzuki_dft_pilot"
    out.mkdir(parents=True, exist_ok=True)

    dft = pd.read_csv(dft_csv)
    a = pd.read_csv(a_csv)
    a = a[
        a["target_substrate"].isin(dft["target_substrate"].unique())
        & a["seed"].isin(dft["seed"].unique())
    ].copy()

    rec = analyze_one("suzuki_dft_B_pilot", dft_csv, out)
    e = rec["effects"]
    print(e[
        [
            "strategy",
            "auc_target_mean",
            "dAUC_vs_cold_mean",
            "dAUC_vs_cold_ci95_lo",
            "dAUC_vs_cold_ci95_hi",
            "dAUC_vs_random_mean",
            "dAUC_vs_random_ci95_lo",
            "dAUC_vs_random_ci95_hi",
            "frac_targets_gt_cold",
            "frac_targets_gt_random",
        ]
    ].to_string(index=False))

    tm_d = target_means(dft)
    tm_a = target_means(a)
    rows = []
    for strat in sorted(set(tm_d["strategy"]) & set(tm_a["strategy"])):
        dd = tm_d[tm_d["strategy"] == strat].set_index("target")["auc"]
        aa = tm_a[tm_a["strategy"] == strat].set_index("target")["auc"]
        delta = (dd - aa).dropna()
        rows.append(
            {
                "strategy": strat,
                "AUC_dft": float(dd.mean()),
                "AUC_ohe_A": float(aa.reindex(dd.index).mean()),
                "d_dft_minus_ohe": float(delta.mean()),
            }
        )
    cmp = pd.DataFrame(rows)
    cmp.to_csv(out / "compare_dft_vs_phaseA_ohe_same_targets.csv", index=False)
    print("--- DFT vs PhaseA OHE (same 3 targets, seeds 0-1) ---")
    print(cmp.to_string(index=False))

    lines = [
        "# Suzuki Phase B DFT pilot",
        "",
        "condition=DFT (860d), substrate=morgan_r2, Tanimoto.",
        "3 targets x 6 strategies x 2 seeds = 36. Pilot-scale only.",
        "",
        "| strategy | AUC DFT | dCold | dRandom |",
        "|---|---:|---:|---:|",
    ]
    for _, r in e.sort_values("auc_target_mean", ascending=False).iterrows():
        dc = "—" if r["strategy"] == "cold_start" else f"{r['dAUC_vs_cold_mean']:+.1f}"
        dr = "—" if r["strategy"] == "random" else f"{r['dAUC_vs_random_mean']:+.1f}"
        lines.append(f"| {r['strategy']} | {r['auc_target_mean']:.1f} | {dc} | {dr} |")
    lines += [
        "",
        "## vs Phase A OHE (same subset)",
        "",
        "| strategy | AUC DFT | AUC OHE-A | DFT-OHE |",
        "|---|---:|---:|---:|",
    ]
    for _, r in cmp.iterrows():
        lines.append(
            f"| {r['strategy']} | {r['AUC_dft']:.1f} | {r['AUC_ohe_A']:.1f} | "
            f"{r['d_dft_minus_ohe']:+.1f} |"
        )
    cold = e[e["strategy"] == "cold_start"].iloc[0]
    rnd = e[e["strategy"] == "random"].iloc[0]
    lines += [
        "",
        "## Read",
        "",
        f"- cold vs random (target mean): {cold['dAUC_vs_random_mean']:+.1f} "
        f"[{cold['dAUC_vs_random_ci95_lo']:+.1f}, {cold['dAUC_vs_random_ci95_hi']:+.1f}]",
        f"- random mean AUC={rnd['auc_target_mean']:.1f}; cold={cold['auc_target_mean']:.1f}",
        "- If DFT cold still loses to random on this pilot, do not escalate to full Suzuki DFT.",
        "",
    ]
    (out / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
