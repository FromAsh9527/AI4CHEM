"""Analyze amination matched-init audit (C1/C2 decomposition on the main library).

Consumes results/amination_matched_init_audit/*.json plus the frozen
results/amination_v1_full/*.json for the EI arms (cold_start, topk_warm).
The random-post arms share init with the EI arms by construction (same
select_cold_init / select_topk_init with the same seed; seed+100003 streams
only affect the random continuation).

Pre-registered comparisons (same definitions as P0, docs/17 §3.2):
  C1 = topk_warm      - topk_random_post     (given topk start, does EI add value?)
  C2 = cold_start     - cold_random_post     (same random init, does EI beat random cont.?)
  C3 = topk_warm      - cold_start           (init-list premium, same continuation type)
  C4 = topk_random_post vs random first-5    (list vs random init, AUC@5 view)

Inference: seed-average per target, then target bootstrap CI (B=5000).
Also recomputes round-level metrics (AUC@5/10/20, rounds to 50/70/0.9*y_star).

Usage:
    python scripts/analyze_amination_matched_init.py
Output:
    results/amination_matched_init_audit/effects.csv
    results/amination_matched_init_audit/summary.md
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
N_BOOT = 5000


def load(dirpath: Path) -> pd.DataFrame:
    rows = []
    for p in sorted(dirpath.glob("*.json")):
        if p.name in ("loso_records.json", "loso_summary.csv"):
            continue
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if "bo" not in rec:
            continue
        values = np.asarray(rec["bo"].get("values") or [], dtype=float)
        if len(values) == 0:
            continue
        bsf = np.maximum.accumulate(values)
        rows.append(
            {
                "strategy": rec["strategy"],
                "target": rec["target_substrate"],
                "seed": int(rec["seed"]),
                "bsf": bsf,
                "init_best": float(np.max(values[:5])),
                "final_best": float(bsf[-1]),
                "auc": float(np.sum(bsf)),
                "auc5": float(np.sum(bsf[:5])),
                "auc10": float(np.sum(bsf[:10])),
            }
        )
    return pd.DataFrame(rows)


def rounds(bsf: np.ndarray, tau: float) -> tuple[float, int]:
    idx = np.searchsorted(bsf, tau, side="left")
    reached = idx < len(bsf)
    return (math.ceil((idx + 1) / 5) if reached else np.nan), int(reached)


def target_table(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (strat, tgt), g in df.groupby(["strategy", "target"]):
        for tau in (50.0, 70.0):
            r = [rounds(b, tau) for b in g["bsf"]]
            rr = np.array([x[0] for x in r], dtype=float)
            # never-reached -> impute to budget rounds + 1 = 5 (deployment rounds)
            rr = np.where(np.isnan(rr), 5.0, rr)
            rows.append(
                {
                    "strategy": strat, "target": tgt,
                    f"r{tau:g}_mean_rounds": float(rr.mean()),
                    f"r{tau:g}_reached": float(np.mean([x[1] for x in r])),
                }
            )
        rows.append(
            {
                "strategy": strat, "target": tgt,
                "auc": float(g["auc"].mean()),
                "auc5": float(g["auc5"].mean()),
                "auc10": float(g["auc10"].mean()),
                "init_best": float(g["init_best"].mean()),
                "final_best": float(g["final_best"].mean()),
            }
        )
    tab = pd.DataFrame(rows)
    # wide: pivot to strategy columns per metric
    wide = tab.set_index(["strategy", "target"]).stack().reset_index()
    wide.columns = ["strategy", "target", "metric", "value"]
    return wide


def boot_ci(d: np.ndarray) -> tuple[float, float]:
    rng = np.random.default_rng(20260822)
    idx = rng.integers(0, len(d), size=(N_BOOT, len(d)))
    m = d[idx].mean(axis=1)
    return float(np.quantile(m, 0.025)), float(np.quantile(m, 0.975))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-dir", type=Path, default=ROOT / "results" / "amination_matched_init_audit")
    ap.add_argument("--frozen-dir", type=Path, default=ROOT / "results" / "amination_v1_full")
    ap.add_argument("--out-dir", type=Path, default=None)
    args = ap.parse_args()
    AUDIT = args.results_dir
    FROZEN = args.frozen_dir
    OUT = args.out_dir or AUDIT
    B = 20

    audit = load(AUDIT)
    frozen = load(FROZEN)
    frozen = frozen[frozen["strategy"].isin(["cold_start", "topk_warm", "random"])]
    jobs = pd.concat([audit, frozen], ignore_index=True)
    print(f"jobs: audit={len(audit)} frozen={len(frozen)}")
    OUT.mkdir(parents=True, exist_ok=True)

    wide = target_table(jobs)
    piv = wide.pivot_table(index="target", columns=["strategy", "metric"], values="value")

    pairs = {
        "C1_topk_EI_minus_topk_random": ("topk_warm", "topk_random_post"),
        "C2_cold_EI_minus_cold_random": ("cold_start", "cold_random_post"),
        "C3_topk_minus_cold": ("topk_warm", "cold_start"),
        "topk_random_minus_cold": ("topk_random_post", "cold_start"),
    }
    metrics = ["auc", "auc5", "auc10", "init_best", "final_best", "r50_mean_rounds", "r70_mean_rounds",
               "r50_reached", "r70_reached"]
    lines = ["# Amination matched-init audit (C1/C2/C3)", "",
             "Inference: seed-average -> target -> bootstrap CI (B=5000).",
             "r50/r70 = mean deployment rounds (5/round) to >=50/70 yield; never-reached imputed to 5 rounds; reached = frac targets reaching within budget."]
    out_rows = []
    for name, (a, b) in pairs.items():
        lines.append("")
        lines.append(f"## {name}  ({a} - {b})")
        lines.append("")
        lines.append("| metric | mean | 95% CI | frac>0 |")
        lines.append("|---|---|---|---|")
        for m in metrics:
            if (a, m) not in piv.columns or (b, m) not in piv.columns:
                continue
            d = piv[(a, m)] - piv[(b, m)]
            d = d.dropna()
            if len(d) < 3:
                continue
            lo, hi = boot_ci(d.to_numpy())
            lines.append(f"| {m} | {d.mean():+.2f} | [{lo:+.2f}, {hi:+.2f}] | {np.mean(d > 0):.2f} |")
            out_rows.append({"comparison": name, "metric": m, "mean": float(d.mean()),
                             "ci_lo": lo, "ci_hi": hi, "frac_gt0": float(np.mean(d > 0))})
    pd.DataFrame(out_rows).to_csv(OUT / "effects.csv", index=False)
    (OUT / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
