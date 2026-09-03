"""Four-arm comparison for the Suzuki-class continuation experiment.

Arms (all: topk-5 list init, n_init=5, B=20, EI, seeds 0-4, rule=mean):
    A = topk_warm            top-5 init + EI, no warm points        (existing results)
    B = topk_warm_warmtop5   A + historical yields of the top-5 list conditions as warm GP points
    C = topk_warm_warmall    A + ALL historical yields as warm GP points (<=120 subsample)
    D = topk_random_post     top-5 init + random post-init (no GP)  (existing results)

Question: does feeding historical yields into the target GP during the
continuation phase add value on top of the top-5 list init?
Primary metric: AUC@20 (sum of best-so-far over 20 steps). Secondary: AUC@5,
init_best, final_best — diagnostics only.

Usage:
    python scripts/analyze_continuation_arms.py
Output:
    results/continuation_arms_compare/{per_target.csv, summary.md}
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "continuation_arms_compare"
N_BOOT = 5000
# Arbitrary fixed seed (kept stable so documented CIs stay reproducible).
RNG = np.random.default_rng(20260901)

# library -> (arm A dir, arm D dir, new arms dir)
LIBRARIES = {
    "suzuki": ("results/suzuki_v1_full_rt/suzuki_v1_full",
               "results/suzuki_p0_shared_init",
               "results/suzuki_continuation_arms"),
    "hitea": ("results/p4_hitea/loso",
              "results/p4_hitea/loso",
              "results/hitea_continuation_arms"),
}
ARMS = {
    "A": "topk_warm",
    "B": "topk_warm_warmtop5",
    "C": "topk_warm_warmall",
    "D": "topk_random_post",
}


def load_metrics(dirpath: Path, strategy: str) -> pd.DataFrame:
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


def boot_ci(d: np.ndarray) -> tuple[float, float]:
    boot = np.array([d[RNG.integers(0, len(d), size=len(d))].mean() for _ in range(N_BOOT)])
    return np.quantile(boot, [0.025, 0.975])


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Continuation arms — Suzuki-class libraries (EDBO Suzuki + HiTEA)",
        "",
        "Same protocol on every arm: LOSO, n_init=5, B=20, EI, seeds 0-4, rule=mean.",
        "",
        "| arm | strategy | description |",
        "|---|---|---|",
        "| A | topk_warm | top-5 list init + EI, no warm points (baseline) |",
        "| B | topk_warm_warmtop5 | A + historical yields of the 5 list conditions as warm GP points |",
        "| C | topk_warm_warmall | A + ALL historical yields as warm GP points (<=120 subsample) |",
        "| D | topk_random_post | top-5 list init + random post-init (no-GP control) |",
        "",
        "Warm points are GP training data only — they do NOT consume target budget.",
        "Primary metric AUC@20; AUC@5 / init_best / final_best are diagnostics.",
        "",
    ]
    frames = []
    for lib, (dir_a, dir_d, dir_new) in LIBRARIES.items():
        new_dir = ROOT / dir_new
        missing = [k for k in ("B", "C") if len(load_metrics(new_dir, ARMS[k])) == 0]
        if missing:
            lines.append(f"## {lib}  — SKIPPED, missing new-arm results: {missing}")
            lines.append("")
            continue
        dfs = {
            k: load_metrics(ROOT / d, s)
            for k, (d, s) in {
                "A": (dir_a, ARMS["A"]),
                "B": (dir_new, ARMS["B"]),
                "C": (dir_new, ARMS["C"]),
                "D": (dir_d, ARMS["D"]),
            }.items()
        }
        merged = dfs["A"].merge(dfs["B"], on="target", suffixes=("_A", "_B"))
        suffix_cols = ("auc", "auc5", "init_best", "final_best")
        merged = merged.merge(
            dfs["C"].rename(columns={k: k + "_C" for k in suffix_cols}), on="target")
        merged = merged.merge(
            dfs["D"].rename(columns={k: k + "_D" for k in suffix_cols}), on="target")
        merged.insert(0, "library", lib)
        frames.append(merged)

        lines.append(f"## {lib}  (n={len(merged)} targets)")
        lines.append("")
        lines.append("| contrast | metric | A/B/C/D mean | Δ vs A | 95% CI vs A | Δ vs D | 95% CI vs D |")
        lines.append("|---|---|---|---|---|---|---|")
        for arm, pre in (("B", "_B"), ("C", "_C")):
            for col in ("auc", "auc5", "init_best", "final_best"):
                a = merged[f"{col}_A"].to_numpy()
                d_arm = merged[f"{col}{pre}"].to_numpy()
                d_d = merged[f"{col}_D"].to_numpy()
                dA = d_arm - a
                dD = d_arm - d_d
                loA, hiA = boot_ci(dA)
                loD, hiD = boot_ci(dD)
                lines.append(f"| {arm} vs A/D | {col} | {a.mean():.1f} / {d_arm.mean():.1f} / "
                             f"{d_d.mean():.1f} | {dA.mean():+.1f} | [{loA:+.1f}, {hiA:+.1f}] | "
                             f"{dD.mean():+.1f} | [{loD:+.1f}, {hiD:+.1f}] |")
        lines.append("")
        lines.append("Warm-top5 is arm B's condition; warm-all is arm C's. Contrast B vs C directly:")
        lines.append("")
        for col in ("auc", "auc5", "init_best", "final_best"):
            b = merged[f"{col}_B"].to_numpy()
            c = merged[f"{col}_C"].to_numpy()
            d = c - b
            lo, hi = boot_ci(d)
            lines.append(f"| C vs B | {col} | B {b.mean():.1f} → C {c.mean():.1f} | Δ {d.mean():+.1f} | [{lo:+.1f}, {hi:+.1f}] |")
        lines.append("")

    if frames:
        all_df = pd.concat(frames, ignore_index=True)
        all_df.to_csv(OUT / "per_target.csv", index=False)
        lines.append(f"## Pooled (both libraries, n={len(all_df)} targets)")
        lines.append("")
        lines.append("| contrast | metric | Δ vs A | 95% CI vs A | Δ vs D | 95% CI vs D |")
        lines.append("|---|---|---|---|---|---|")
        for arm, pre in (("B", "_B"), ("C", "_C")):
            for col in ("auc", "auc5", "init_best", "final_best"):
                a = all_df[f"{col}_A"].to_numpy()
                d_arm = all_df[f"{col}{pre}"].to_numpy()
                d_d = all_df[f"{col}_D"].to_numpy()
                dA = d_arm - a
                dD = d_arm - d_d
                loA, hiA = boot_ci(dA)
                loD, hiD = boot_ci(dD)
                lines.append(f"| {arm} vs A/D | {col} | {dA.mean():+.1f} | [{loA:+.1f}, {hiA:+.1f}] | "
                             f"{dD.mean():+.1f} | [{loD:+.1f}, {hiD:+.1f}] |")
        lines.append("")
        lines.append("## Verdict")
        lines.append("")
        lines.append("- Main contrast B vs A and C vs A: does warm GP data during continuation add value")
        lines.append("  on top of the top-5 list init (AUC@20)?")
        lines.append("- vs D: warm arms must beat the no-GP random control to be meaningful.")
        lines.append("- C vs B: all-history vs list-only warm data.")
        lines.append("- Diagnostics AUC@5 / init_best: init-segment differences (same init for all arms,")
        lines.append("  so only the first warm-informed acquisition differs); final_best: endpoint parity.")
        (OUT / "summary.md").write_text("\n".join(lines), encoding="utf-8")
        print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
