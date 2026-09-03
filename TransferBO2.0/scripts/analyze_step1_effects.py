#!/usr/bin/env python
"""Step-1 effect analysis: target-level inference (not job-IID).

Primary aggregation (LOCKED for Step 1):
  1) average AUC over seeds within each target
  2) report mean / median / bootstrap CI across targets
  3) target-level win rates vs cold and vs random

Also reports job-level NTR for continuity with earlier tables, but labels it secondary.

Outputs under results/step1_effects/:
  - effects_amination.csv / effects_suzuki.csv
  - target_deltas_*.csv
  - summary.md
  - figures (optional PNG)
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
STRATS = [
    "random",
    "cold_start",
    "topk_warm",
    "nearest_topk_warm",
    "sim_weighted",
    "safe_gate",
]
TRANSFER = [s for s in STRATS if s not in ("random", "cold_start")]


def _bootstrap_mean_ci(x: np.ndarray, n_boot: int = 5000, alpha: float = 0.05, seed: int = 0):
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) == 0:
        return float("nan"), float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    means = []
    for _ in range(n_boot):
        means.append(float(np.mean(rng.choice(x, size=len(x), replace=True))))
    lo, hi = np.quantile(means, [alpha / 2, 1 - alpha / 2])
    return float(np.mean(x)), float(lo), float(hi)


def load_summary(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    need = {"strategy", "target_substrate", "seed", "auc", "final_best", "hit10_top5pct"}
    missing = need - set(df.columns)
    if missing:
        raise ValueError(f"{path} missing {missing}")
    return df


def target_means(df: pd.DataFrame) -> pd.DataFrame:
    """One row per (strategy, target): mean over seeds."""
    return (
        df.groupby(["strategy", "target_substrate"], as_index=False)[
            ["auc", "final_best", "hit10_top5pct"]
        ]
        .mean()
        .rename(columns={"target_substrate": "target"})
    )


def effect_tables(tm: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    cold = tm[tm["strategy"] == "cold_start"].set_index("target")
    rnd = tm[tm["strategy"] == "random"].set_index("target")
    rows = []
    target_rows = []
    for strat in STRATS:
        sub = tm[tm["strategy"] == strat].set_index("target")
        # vs cold
        d_cold = (sub["auc"] - cold["auc"]).dropna()
        d_rand = (sub["auc"] - rnd["auc"]).dropna()
        m_c, lo_c, hi_c = _bootstrap_mean_ci(d_cold.to_numpy())
        m_r, lo_r, hi_r = _bootstrap_mean_ci(d_rand.to_numpy())
        m_auc, lo_auc, hi_auc = _bootstrap_mean_ci(sub["auc"].to_numpy())
        rows.append(
            {
                "strategy": strat,
                "n_targets": int(sub.shape[0]),
                "auc_target_mean": m_auc,
                "auc_ci95_lo": lo_auc,
                "auc_ci95_hi": hi_auc,
                "dAUC_vs_cold_mean": m_c if strat != "cold_start" else 0.0,
                "dAUC_vs_cold_ci95_lo": lo_c if strat != "cold_start" else 0.0,
                "dAUC_vs_cold_ci95_hi": hi_c if strat != "cold_start" else 0.0,
                "frac_targets_gt_cold": float((d_cold > 0).mean())
                if strat != "cold_start"
                else float("nan"),
                "dAUC_vs_random_mean": m_r if strat != "random" else 0.0,
                "dAUC_vs_random_ci95_lo": lo_r if strat != "random" else 0.0,
                "dAUC_vs_random_ci95_hi": hi_r if strat != "random" else 0.0,
                "frac_targets_gt_random": float((d_rand > 0).mean())
                if strat != "random"
                else float("nan"),
                "final_best_target_mean": float(sub["final_best"].mean()),
                "hit10_target_mean": float(sub["hit10_top5pct"].mean()),
            }
        )
        for t in sub.index:
            target_rows.append(
                {
                    "strategy": strat,
                    "target": t,
                    "auc": float(sub.loc[t, "auc"]),
                    "final_best": float(sub.loc[t, "final_best"]),
                    "hit10": float(sub.loc[t, "hit10_top5pct"]),
                    "dAUC_vs_cold": float(sub.loc[t, "auc"] - cold.loc[t, "auc"])
                    if strat != "cold_start"
                    else 0.0,
                    "dAUC_vs_random": float(sub.loc[t, "auc"] - rnd.loc[t, "auc"])
                    if strat != "random"
                    else 0.0,
                }
            )
    return pd.DataFrame(rows), pd.DataFrame(target_rows)


def job_level_ntr(df: pd.DataFrame) -> pd.DataFrame:
    cold = df[df["strategy"] == "cold_start"].set_index(["target_substrate", "seed"])["auc"]
    rows = []
    for strat, g in df[df["strategy"] != "cold_start"].groupby("strategy"):
        d = []
        for _, r in g.iterrows():
            key = (r["target_substrate"], r["seed"])
            if key in cold.index:
                d.append(float(r["auc"]) - float(cold.loc[key]))
        arr = np.asarray(d, dtype=float)
        rows.append(
            {
                "strategy": strat,
                "n_jobs": len(arr),
                "job_mean_dAUC_vs_cold": float(np.mean(arr)) if len(arr) else float("nan"),
                "job_NTR": float(np.mean(arr < 0)) if len(arr) else float("nan"),
            }
        )
    return pd.DataFrame(rows)


def plot_forest(effects: pd.DataFrame, title: str, path: Path, vs: str = "cold") -> None:
    if vs == "cold":
        sub = effects[effects["strategy"] != "cold_start"].copy()
        mean_c, lo_c, hi_c = "dAUC_vs_cold_mean", "dAUC_vs_cold_ci95_lo", "dAUC_vs_cold_ci95_hi"
        xlab = r"Target-mean $\Delta$AUC vs cold (95% bootstrap CI)"
    else:
        sub = effects[effects["strategy"] != "random"].copy()
        mean_c, lo_c, hi_c = "dAUC_vs_random_mean", "dAUC_vs_random_ci95_lo", "dAUC_vs_random_ci95_hi"
        xlab = r"Target-mean $\Delta$AUC vs random (95% bootstrap CI)"
    sub = sub.sort_values(mean_c)
    fig, ax = plt.subplots(figsize=(8.5, 3.8), dpi=140)
    y = np.arange(len(sub))
    ax.axvline(0, color="#333", lw=0.8)
    for i, (_, r) in enumerate(sub.iterrows()):
        ax.plot([r[lo_c], r[hi_c]], [i, i], color="#2e75b6", lw=2)
        ax.plot(r[mean_c], i, "o", color="#1f4e79", ms=6)
    ax.set_yticks(y)
    ax.set_yticklabels(sub["strategy"].tolist())
    ax.set_xlabel(xlab)
    ax.set_title(title)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def analyze_one(name: str, csv: Path, out: Path) -> dict:
    df = load_summary(csv)
    tm = target_means(df)
    effects, targets = effect_tables(tm)
    ntr = job_level_ntr(df)
    effects = effects.merge(ntr, on="strategy", how="left")

    effects.to_csv(out / f"effects_{name}.csv", index=False)
    targets.to_csv(out / f"target_deltas_{name}.csv", index=False)

    plot_forest(
        effects,
        f"{name}: Step-1 effects vs cold (target-level)",
        out / f"forest_{name}_vs_cold.png",
        vs="cold",
    )
    plot_forest(
        effects,
        f"{name}: Step-1 effects vs random (target-level)",
        out / f"forest_{name}_vs_random.png",
        vs="random",
    )
    return {
        "name": name,
        "n_jobs": len(df),
        "n_targets": tm["target"].nunique(),
        "n_seeds": df["seed"].nunique(),
        "effects": effects,
        "targets": targets,
    }


def write_summary_md(results: list[dict], out: Path) -> None:
    lines = [
        "# Step-1 transfer effects — formal summary",
        "",
        "Inference unit: **target/task** (seed-averaged first).",
        "CI: nonparametric bootstrap over targets (5000 resamples).",
        "Job-level NTR kept as secondary continuity metric.",
        "",
    ]
    for rec in results:
        e = rec["effects"]
        lines += [
            f"## {rec['name']}",
            "",
            f"- jobs={rec['n_jobs']}, targets={rec['n_targets']}, seeds={rec['n_seeds']}",
            "",
            "| strategy | AUC (target mean) | Δcold mean [95% CI] | frac targets > cold | Δrandom mean [95% CI] | frac > random | job NTR |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
        for _, r in e.sort_values("auc_target_mean", ascending=False).iterrows():
            if r["strategy"] == "cold_start":
                dc = "—"
                fc = "—"
            else:
                dc = f"{r['dAUC_vs_cold_mean']:+.1f} [{r['dAUC_vs_cold_ci95_lo']:+.1f}, {r['dAUC_vs_cold_ci95_hi']:+.1f}]"
                fc = f"{r['frac_targets_gt_cold']:.2f}"
            if r["strategy"] == "random":
                dr = "—"
                fr = "—"
            else:
                dr = f"{r['dAUC_vs_random_mean']:+.1f} [{r['dAUC_vs_random_ci95_lo']:+.1f}, {r['dAUC_vs_random_ci95_hi']:+.1f}]"
                fr = f"{r['frac_targets_gt_random']:.2f}"
            ntr = "—" if pd.isna(r.get("job_NTR")) else f"{r['job_NTR']:.3f}"
            lines.append(
                f"| {r['strategy']} | {r['auc_target_mean']:.1f} | {dc} | {fc} | {dr} | {fr} | {ntr} |"
            )
        lines.append("")
        # Go criteria checklist
        cold = e[e["strategy"] == "cold_start"].iloc[0]
        rnd = e[e["strategy"] == "random"].iloc[0]
        topk = e[e["strategy"] == "topk_warm"].iloc[0]
        lines += [
            "### Step-1 checklist",
            "",
            f"- cold vs random (target mean Δ): "
            f"**{cold['dAUC_vs_random_mean']:+.1f}** "
            f"[{cold['dAUC_vs_random_ci95_lo']:+.1f}, {cold['dAUC_vs_random_ci95_hi']:+.1f}]; "
            f"frac cold>random targets = {cold['frac_targets_gt_random']:.2f}",
            f"- topk vs cold: **{topk['dAUC_vs_cold_mean']:+.1f}** "
            f"[{topk['dAUC_vs_cold_ci95_lo']:+.1f}, {topk['dAUC_vs_cold_ci95_hi']:+.1f}]; "
            f"frac targets > cold = {topk['frac_targets_gt_cold']:.2f}",
            f"- topk vs random: **{topk['dAUC_vs_random_mean']:+.1f}** "
            f"[{topk['dAUC_vs_random_ci95_lo']:+.1f}, {topk['dAUC_vs_random_ci95_hi']:+.1f}]",
            "",
        ]
    lines += [
        "## What Step 1 does / does not claim",
        "",
        "- Claims: directional transfer **effects** under fixed LOSO protocol.",
        "- Does not claim: chemical mechanism, deployable gate, or 1.0 pair equivalence.",
        "- Product mapping: Q1 ≠ veto of historical topk; see FROZEN_CLAIMS.md appendix.",
        "",
    ]
    (out / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--out",
        type=Path,
        default=ROOT / "results" / "step1_effects",
    )
    args = ap.parse_args()
    out = args.out
    out.mkdir(parents=True, exist_ok=True)

    specs = [
        ("amination", ROOT / "results" / "amination_v1_full" / "loso_summary.csv"),
        ("suzuki", ROOT / "results" / "suzuki_v1_full" / "loso_summary.csv"),
    ]
    results = []
    for name, csv in specs:
        if not csv.exists():
            print(f"[SKIP] missing {csv}")
            continue
        print(f"[..] {name}")
        results.append(analyze_one(name, csv, out))
    write_summary_md(results, out)
    print(f"Wrote {out}")
    print((out / "summary.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
