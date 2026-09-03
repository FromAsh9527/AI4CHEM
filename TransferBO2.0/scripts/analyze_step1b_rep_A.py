#!/usr/bin/env python
"""Step1b Phase A: transfer-gain under Morgan substrate + Tanimoto.

Reuses Step1 target-level aggregation; writes results/step1b_rep_A/.
Optionally compares to hashed Step1 summary if present (same targets).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from analyze_step1_effects import (  # noqa: E402
    analyze_one,
    target_means,
)

STRATS_AFFECTED = ("nearest_topk_warm", "sim_weighted", "safe_gate", "topk_safe_gate")
STRATS_UNAFFECTED = ("random", "cold_start", "topk_warm")


def compare_to_hashed(
    morgan_csv: Path,
    hashed_csv: Path,
    out: Path,
) -> pd.DataFrame | None:
    if not hashed_csv.exists():
        print(f"[SKIP] no hashed baseline summary: {hashed_csv}")
        return None
    m_raw = pd.read_csv(morgan_csv)
    h_raw = pd.read_csv(hashed_csv)
    shared_seeds = sorted(set(m_raw["seed"]) & set(h_raw["seed"]))
    shared_targets = sorted(set(m_raw["target_substrate"]) & set(h_raw["target_substrate"]))
    m_raw = m_raw[m_raw["seed"].isin(shared_seeds) & m_raw["target_substrate"].isin(shared_targets)]
    h_raw = h_raw[h_raw["seed"].isin(shared_seeds) & h_raw["target_substrate"].isin(shared_targets)]
    m = target_means(m_raw)
    h = target_means(h_raw)
    rows = []
    for strat in sorted(set(m["strategy"]) & set(h["strategy"])):
        mm = m[m["strategy"] == strat].set_index("target")["auc"]
        hh = h[h["strategy"] == strat].set_index("target")["auc"]
        d = (mm - hh).dropna()
        rows.append(
            {
                "strategy": strat,
                "n_targets": int(len(d)),
                "n_shared_seeds": len(shared_seeds),
                "mean_AUC_morgan": float(mm.mean()),
                "mean_AUC_hashed": float(hh.reindex(mm.index).mean()),
                "mean_dAUC_morgan_minus_hashed": float(d.mean()),
                "max_abs_dAUC": float(d.abs().max()) if len(d) else float("nan"),
                "affected_by_substrate_rep": strat in STRATS_AFFECTED,
            }
        )
    cmp = pd.DataFrame(rows).sort_values("strategy")
    cmp.to_csv(out / "compare_morgan_vs_hashed_amination.csv", index=False)
    return cmp


def write_rep_md(rec: dict, cmp: pd.DataFrame | None, out: Path) -> None:
    e = rec["effects"]
    lines = [
        "# Step1b Phase A — Morgan substrate gain (amination)",
        "",
        "Protocol: condition **OHE**, substrate **morgan_r2**, similarity **Tanimoto**.",
        "Inference: target-level (seed-averaged), same as Step1.",
        "Does **not** reopen Step1 OHE+hashed claims; report as conditional robustness.",
        "",
        f"- jobs={rec['n_jobs']}, targets={rec['n_targets']}, seeds={rec['n_seeds']}",
        "",
        "| strategy | AUC | Δcold [95% CI] | frac>cold | Δrandom [95% CI] | frac>random | job NTR |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for _, r in e.sort_values("auc_target_mean", ascending=False).iterrows():
        if r["strategy"] == "cold_start":
            dc, fc = "—", "—"
        else:
            dc = (
                f"{r['dAUC_vs_cold_mean']:+.1f} "
                f"[{r['dAUC_vs_cold_ci95_lo']:+.1f}, {r['dAUC_vs_cold_ci95_hi']:+.1f}]"
            )
            fc = f"{r['frac_targets_gt_cold']:.2f}"
        if r["strategy"] == "random":
            dr, fr = "—", "—"
        else:
            dr = (
                f"{r['dAUC_vs_random_mean']:+.1f} "
                f"[{r['dAUC_vs_random_ci95_lo']:+.1f}, {r['dAUC_vs_random_ci95_hi']:+.1f}]"
            )
            fr = f"{r['frac_targets_gt_random']:.2f}"
        ntr = "—" if pd.isna(r.get("job_NTR")) else f"{r['job_NTR']:.3f}"
        lines.append(
            f"| {r['strategy']} | {r['auc_target_mean']:.1f} | {dc} | {fc} | {dr} | {fr} | {ntr} |"
        )

    topk = e[e["strategy"] == "topk_warm"].iloc[0]
    nearest = e[e["strategy"] == "nearest_topk_warm"].iloc[0]
    sim = e[e["strategy"] == "sim_weighted"].iloc[0]
    lines += [
        "",
        "## Focus (representation-sensitive)",
        "",
        f"- **topk_warm** Δcold = {topk['dAUC_vs_cold_mean']:+.1f} "
        f"[{topk['dAUC_vs_cold_ci95_lo']:+.1f}, {topk['dAUC_vs_cold_ci95_hi']:+.1f}] "
        "(should match Step1; φ(s) unused)",
        f"- **nearest_topk_warm** Δcold = {nearest['dAUC_vs_cold_mean']:+.1f} "
        f"[{nearest['dAUC_vs_cold_ci95_lo']:+.1f}, {nearest['dAUC_vs_cold_ci95_hi']:+.1f}]",
        f"- **sim_weighted** Δcold = {sim['dAUC_vs_cold_mean']:+.1f} "
        f"[{sim['dAUC_vs_cold_ci95_lo']:+.1f}, {sim['dAUC_vs_cold_ci95_hi']:+.1f}]",
        f"- nearest - topk (target-mean AUC): "
        f"**{nearest['auc_target_mean'] - topk['auc_target_mean']:+.1f}**",
        "",
    ]
    if cmp is not None and not cmp.empty:
        lines += [
            "## Sanity: Morgan run vs hashed Step1 (same targets)",
            "",
            "| strategy | mean dAUC (Morgan-hashed) | max |abs| | phi-sensitive? |",
            "|---|---:|---:|---|",
        ]
        for _, r in cmp.iterrows():
            lines.append(
                f"| {r['strategy']} | {r['mean_dAUC_morgan_minus_hashed']:+.2f} | "
                f"{r['max_abs_dAUC']:.2f} | {r['affected_by_substrate_rep']} |"
            )
        una = cmp[cmp["strategy"].isin(STRATS_UNAFFECTED)]
        if not una.empty:
            max_una = float(una["max_abs_dAUC"].max())
            lines += [
                "",
                f"- Unaffected strategies max |d| = **{max_una:.2f}** "
                "(expect ~0; large -> wiring bug).",
                "",
            ]
    else:
        lines += [
            "## Sanity vs hashed Step1",
            "",
            "- Hashed full summary not in workspace; rely on within-run topk vs nearest pattern "
            "and FROZEN_CLAIMS qualitative check.",
            "",
        ]
    lines += [
        "## Closed",
        "",
        "- Representation axis is closed (condition default OHE; no DFT full).",
        "- Product mapping: Q1 is baseline-BO quality, not a veto of topk.",
        "- See docs/13_step1_closeout.md.",
        "",
    ]
    (out / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--summary-csv",
        type=Path,
        default=ROOT / "results" / "amination_rep_A_morgan_sub_full" / "loso_summary.csv",
    )
    ap.add_argument(
        "--hashed-csv",
        type=Path,
        default=ROOT / "results" / "amination_v1_full" / "loso_summary.csv",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=ROOT / "results" / "step1b_rep_A",
    )
    ap.add_argument("--name", default="amination_morgan_A")
    args = ap.parse_args()
    out = args.out
    out.mkdir(parents=True, exist_ok=True)

    if not args.summary_csv.exists():
        raise SystemExit(f"Missing {args.summary_csv}; run LOSO first.")

    print(f"[..] {args.name}")
    rec = analyze_one(args.name, args.summary_csv, out)
    cmp = compare_to_hashed(args.summary_csv, args.hashed_csv, out)
    write_rep_md(rec, cmp, out)
    try:
        print((out / "summary.md").read_text(encoding="utf-8"))
    except UnicodeEncodeError:
        print(f"summary written: {out / 'summary.md'}")
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
