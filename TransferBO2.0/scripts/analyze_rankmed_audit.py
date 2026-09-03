"""Compare AUC-layer results: legacy mean-rule topk_warm vs rank_median-rule topk_warm.

Usage:
    python scripts/analyze_rankmed_audit.py
Output:
    results/rankmed_audit_compare/{per_target.csv, summary.md}
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "rankmed_audit_compare"
N_BOOT = 5000
RNG = np.random.default_rng(20260824)

PAIRS = {
    "amination": ("results/amination_v1_full", "results/amination_rankmed_audit"),
    "suzuki": ("results/suzuki_v1_full_rt/suzuki_v1_full", "results/suzuki_rankmed_audit"),
    "borylation": ("results/p4_borylation/loso", "results/borylation_rankmed_audit"),
    "hitea": ("results/p4_hitea/loso", "results/hitea_rankmed_audit"),
}


def load_metrics(dirpath: Path, strategy: str = "topk_warm") -> pd.DataFrame:
    rows = []
    for p in sorted(Path(dirpath).glob("*.json")):
        if p.name.startswith("loso"):
            continue
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if rec.get("strategy") != strategy or "bo" not in rec:
            continue
        bsf = np.asarray(rec["bo"].get("best_so_far") or [], dtype=float)
        if len(bsf) < 20:
            continue
        rows.append({
            "target": rec["target_substrate"],
            "seed": int(rec["seed"]),
            "auc": float(np.sum(bsf)),
            "auc5": float(np.sum(bsf[:5])),
            "init_best": float(np.max(bsf[:5])),
            "final_best": float(bsf[-1]),
        })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.groupby("target")[["auc", "auc5", "init_best", "final_best"]].mean().reset_index()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    lines = ["# Rank-median rule vs legacy mean rule — AUC layer (20-step budget)", "",
             "Same protocol (LOSO, n_init=5, B=20, EI, seeds 0-4); only the list rule changes.",
             "Target-level paired differences with bootstrap 95% CI.", ""]
    frames = []
    for lib, (old_dir, new_dir) in PAIRS.items():
        old = load_metrics(ROOT / old_dir)
        new = load_metrics(ROOT / new_dir)
        m = old.merge(new, on="target", suffixes=("_old", "_new"))
        m["library"] = lib
        frames.append(m)
        lines.append(f"## {lib}  (n={len(m)} targets)")
        lines.append("")
        lines.append("| metric | mean rule | rank_median rule | Δ | 95% CI | frac new>old |")
        lines.append("|---|---|---|---|---|---|")
        for col in ("auc", "auc5", "init_best", "final_best"):
            a = m[f"{col}_old"].to_numpy()
            b = m[f"{col}_new"].to_numpy()
            d = b - a
            boot = np.array([d[RNG.integers(0, len(d), size=len(d))].mean() for _ in range(N_BOOT)])
            lo, hi = np.quantile(boot, [0.025, 0.975])
            lines.append(f"| {col} | {a.mean():.1f} | {b.mean():.1f} | {d.mean():+.1f} | "
                         f"[{lo:+.1f}, {hi:+.1f}] | {np.mean(d > 0):.2f} |")
        lines.append("")
    all_df = pd.concat(frames, ignore_index=True)
    all_df.to_csv(OUT / "per_target.csv", index=False)
    lines.append("## Pooled (all libraries, n=%d targets)" % len(all_df))
    lines.append("")
    lines.append("| metric | Δ | 95% CI | frac new>old |")
    lines.append("|---|---|---|---|")
    for col in ("auc", "auc5", "init_best", "final_best"):
        d = all_df[f"{col}_new"].to_numpy() - all_df[f"{col}_old"].to_numpy()
        boot = np.array([d[RNG.integers(0, len(d), size=len(d))].mean() for _ in range(N_BOOT)])
        lo, hi = np.quantile(boot, [0.025, 0.975])
        lines.append(f"| {col} | {d.mean():+.1f} | [{lo:+.1f}, {hi:+.1f}] | {np.mean(d > 0):.2f} |")
    lines.append("")
    lines.append("## Verdict")
    lines.append("")
    lines.append("- AUC@20: does the rank_median list rule improve the FULL 20-step budget outcome?")
    lines.append("- AUC@5 / init_best: the init segment (mechanism-relevant part).")
    lines.append("- final_best: endpoint parity.")
    (OUT / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
