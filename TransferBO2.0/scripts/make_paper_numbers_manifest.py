"""Generate the paper Table 1 / Table 3 numbers directly from results JSONs.

Single source of truth: reads per-job JSONs, seed-averages, computes
target-level paired bootstrap CI. To match the LOCKED authoritative summaries
(bootstrap resampling differs slightly across files), the seed is chosen PER
LIBRARY to reproduce the locked CI exactly:

  - amination / suzuki : seed=0        (results/step1_effects/summary.md, FROZEN_CLAIMS)
  - borylation         : seed=20260822 (results/p4_borylation/summary.md)
  - hitea              : seed=20260822 (results/p4_hitea/summary.md, repaired rerun)

NOTE: seed=20260822 reproduces BOTH P4 locked CIs exactly (verified 2026-08-24);
seed=0 reproduces the two FROZEN step1 summaries exactly. The manuscript Table 1
numbers are the locked numbers themselves; this manifest is the audit trail
proving agreement. Regenerate: python scripts/make_paper_numbers_manifest.py
Output: results/paper_numbers/manifest.md + manifest.csv
"""

from __future__ import annotations

import json
import glob
import csv
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "paper_numbers"
N_BOOT = 5000


def load_bsf(dirp: str, strat: str) -> dict:
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


def boot_ci(d: np.ndarray, seed: int) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    boot = np.array([d[rng.integers(0, len(d), size=len(d))].mean() for _ in range(N_BOOT)])
    return np.quantile(boot, [0.025, 0.975])


LIBRARIES = [
    # (key, lib, template, source, json_dir, bootstrap_seed, locked_authority)
    ("amination", "Amidation", "Pd C-N", "Doyle (EDBO)", "results/amination_v1_full", 0,
     "results/step1_effects/summary.md (FROZEN_CLAIMS)"),
    ("borylation", "Borylation", "Ni C-B", "Doyle (ochem-data)", "results/p4_borylation/loso", 20260822,
     "results/p4_borylation/summary.md"),
    ("suzuki", "Suzuki (EDBO)", "Pd C-C", "Doyle (EDBO)", "results/suzuki_v1_full_rt/suzuki_v1_full", 0,
     "results/step1_effects/summary.md (FROZEN_CLAIMS)"),
    ("hitea", "Suzuki (HiTEA)", "Pd C-C", "Pfizer (independent)", "results/p4_hitea/loso", 20260822,
     "results/p4_hitea/summary.md (2026-08-24 repaired rerun)"),
]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for key, lib, tmpl, src, dirp, seed, authority in LIBRARIES:
        tk = load_bsf(dirp, "topk_warm")
        cold = load_bsf(dirp, "cold_start")
        rnd = load_bsf(dirp, "random")
        near = load_bsf(dirp, "nearest_topk_warm")
        tg = sorted(set(tk) & set(cold) & set(rnd))
        a = np.array([tk[t].sum() for t in tg])
        b = np.array([cold[t].sum() for t in tg])
        c = np.array([rnd[t].sum() for t in tg])
        d1 = a - b
        d2 = a - c
        lo1, hi1 = boot_ci(d1, seed)
        lo2, hi2 = boot_ci(d2, seed)
        rec = {
            "library": key, "lib": lib, "template": tmpl, "source": src, "n_tasks": len(tg),
            "bootstrap_seed": seed, "locked_authority": authority,
            "auc_topk": float(a.mean()),
            "d_cold": float(d1.mean()), "ci_cold_lo": float(lo1), "ci_cold_hi": float(hi1),
            "frac_cold": float(np.mean(d1 > 0)),
            "d_random": float(d2.mean()), "ci_random_lo": float(lo2), "ci_random_hi": float(hi2),
            "frac_random": float(np.mean(d2 > 0)),
        }
        if near:
            ntg = sorted(set(tk) & set(cold) & set(near))
            na = np.array([tk[t].sum() for t in ntg])
            nb = np.array([near[t].sum() for t in ntg])
            d3 = na - nb
            lo3, hi3 = boot_ci(d3, seed)
            rec.update({"d_near_vs_pool": float(d3.mean()),
                        "ci_near_lo": float(lo3), "ci_near_hi": float(hi3)})
        rows.append(rec)

    lines = ["# Paper numbers manifest (auto-generated, 2026-08-24)", "",
             "Target-level paired bootstrap, B = 5000, seed per library chosen to reproduce the "
             "LOCKED authoritative summary exactly (audit trail: CI agreement below).",
             "Manuscript Table 1/Table 3 numbers = these locked numbers, not this file's recompute.",
             ""]
    lines.append("| library | n | AUC@20 (topk) | vs cold (95% CI) | frac>0 | vs random (95% CI) | frac>0 | seed | locked source |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        lines.append(f"| {r['lib']} | {r['n_tasks']} | {r['auc_topk']:.1f} | "
                     f"{r['d_cold']:+.1f} [{r['ci_cold_lo']:+.1f}, {r['ci_cold_hi']:+.1f}] | {r['frac_cold']:.2f} | "
                     f"{r['d_random']:+.1f} [{r['ci_random_lo']:+.1f}, {r['ci_random_hi']:+.1f}] | {r['frac_random']:.2f} | "
                     f"{r['bootstrap_seed']} | {r['locked_authority']} |")
    lines.append("")
    lines.append("nearest vs pooled (Δ = nearest − pooled, AUC@20; positive = nearest higher):")
    for r in rows:
        if "d_near_vs_pool" in r:
            lines.append(f"- {r['lib']}: {r['d_near_vs_pool']:+.1f} "
                         f"[{r['ci_near_lo']:+.1f}, {r['ci_near_hi']:+.1f}]")
    (OUT / "manifest.md").write_text("\n".join(lines), encoding="utf-8")
    with open(OUT / "manifest.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
