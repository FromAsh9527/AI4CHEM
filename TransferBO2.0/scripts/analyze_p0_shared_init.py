#!/usr/bin/env python
"""P0 shared-init audit analysis (docs/17_step3_experiment_plan.md §3).

Key comparisons (target-level, seed-mean then bootstrap):
  C1: topk_warm - topk_random_post
  C2: cold_start - cold_random_post
  C3: topk_warm - cold_start
  C4: topk_only init_best vs random init_best (first n_init steps)
  C5: topk_warm - random

Optional: consistency check vs reference Step1 results directory.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from analyze_step1_effects import _bootstrap_mean_ci, load_summary, target_means  # noqa: E402

P0_STRATS = [
    "random",
    "cold_start",
    "topk_warm",
    "cold_random_post",
    "topk_random_post",
    "topk_only",
]

KEY_COMPARISONS = [
    ("C1", "topk_warm", "topk_random_post", "Given topk init, does EI add value?"),
    ("C2", "cold_start", "cold_random_post", "Same init: is cold-EI weaker than random post?"),
    ("C3", "topk_warm", "cold_start", "Init list premium with same post (EI)"),
    ("C5", "topk_warm", "random", "Full protocol vs random (replication check)"),
]


def p0_target_means(jobs: pd.DataFrame) -> pd.DataFrame:
    return (
        jobs.groupby(["strategy", "target_substrate"], as_index=False)[["auc", "final_best", "init_best"]]
        .mean()
        .rename(columns={"target_substrate": "target"})
    )


def p0_effect_tables(tm: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    cold = tm[tm["strategy"] == "cold_start"].set_index("target")
    rnd = tm[tm["strategy"] == "random"].set_index("target")
    rows = []
    target_rows = []
    for strat in P0_STRATS:
        sub = tm[tm["strategy"] == strat].set_index("target")
        if sub.empty:
            continue
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
                "init_best_target_mean": float(sub["init_best"].mean()),
            }
        )
        for t in sub.index:
            target_rows.append(
                {
                    "strategy": strat,
                    "target": t,
                    "auc": float(sub.loc[t, "auc"]),
                    "final_best": float(sub.loc[t, "final_best"]),
                    "init_best": float(sub.loc[t, "init_best"]),
                    "dAUC_vs_cold": float(sub.loc[t, "auc"] - cold.loc[t, "auc"])
                    if strat != "cold_start"
                    else 0.0,
                    "dAUC_vs_random": float(sub.loc[t, "auc"] - rnd.loc[t, "auc"])
                    if strat != "random"
                    else 0.0,
                }
            )
    return pd.DataFrame(rows), pd.DataFrame(target_rows)


def _init_best_from_job(obj: dict, n_init: int) -> float:
    stats = obj.get("stats") or {}
    bsf = stats.get("best_so_far")
    if not bsf:
        values = (obj.get("bo") or {}).get("values") or []
        if not values:
            return float("nan")
        return float(max(values[: min(n_init, len(values))]))
    n = min(n_init, len(bsf))
    return float(bsf[n - 1])


def load_p0_jobs(results_dir: Path, n_init: int = 5) -> pd.DataFrame:
    rows = []
    for path in sorted(results_dir.glob("*.json")):
        if path.name in {"loso_records.json", "pair_records.json"}:
            continue
        obj = json.loads(path.read_text(encoding="utf-8"))
        strat = obj.get("strategy")
        if strat not in P0_STRATS:
            continue
        stats = obj.get("stats") or {}
        rows.append(
            {
                "strategy": strat,
                "target_substrate": obj["target_substrate"],
                "seed": int(obj["seed"]),
                "auc": stats.get("auc"),
                "final_best": stats.get("final_best"),
                "init_best": _init_best_from_job(obj, n_init),
                "init_indices": (obj.get("meta") or {}).get("init_indices"),
            }
        )
    return pd.DataFrame(rows)


def comparison_table(tm: pd.DataFrame, a: str, b: str, metric: str = "auc") -> dict:
    sa = tm[tm["strategy"] == a].set_index("target")[metric]
    sb = tm[tm["strategy"] == b].set_index("target")[metric]
    common = sa.index.intersection(sb.index)
    delta = (sa.loc[common] - sb.loc[common]).to_numpy(dtype=float)
    mean, lo, hi = _bootstrap_mean_ci(delta)
    return {
        "comparison": f"{a} - {b}",
        "metric": metric,
        "mean_delta": mean,
        "ci_lo": lo,
        "ci_hi": hi,
        "frac_targets_gt": float(np.mean(delta > 0)) if len(delta) else float("nan"),
        "n_targets": int(len(common)),
    }


def c4_init_best(tm: pd.DataFrame, n_init: int) -> dict:
    topk = tm[tm["strategy"] == "topk_only"].set_index("target")["init_best"]
    rnd = tm[tm["strategy"] == "random"].set_index("target")["init_best"]
    common = topk.index.intersection(rnd.index)
    delta = (topk.loc[common] - rnd.loc[common]).to_numpy(dtype=float)
    mean, lo, hi = _bootstrap_mean_ci(delta)
    return {
        "comparison": "C4: topk_only.init_best - random.init_best",
        "metric": "init_best",
        "mean_delta": mean,
        "ci_lo": lo,
        "ci_hi": hi,
        "frac_targets_gt": float(np.mean(delta > 0)) if len(delta) else float("nan"),
        "n_targets": int(len(common)),
        "note": f"random init_best uses first {n_init} steps of 20-shot random",
    }


def reference_check(
    p0_tm: pd.DataFrame, ref_dir: Path, strategies: tuple[str, ...] = ("cold_start", "topk_warm", "random")
) -> pd.DataFrame:
    ref_path = ref_dir / "loso_summary.csv"
    if not ref_path.exists():
        return pd.DataFrame()
    ref_tm = target_means(load_summary(ref_path))
    rows = []
    for strat in strategies:
        a = p0_tm[p0_tm["strategy"] == strat].set_index("target")["auc"]
        b = ref_tm[ref_tm["strategy"] == strat].set_index("target")["auc"]
        common = a.index.intersection(b.index)
        if len(common) == 0:
            continue
        diff = (a.loc[common] - b.loc[common]).to_numpy(dtype=float)
        rows.append(
            {
                "strategy": strat,
                "mean_abs_diff": float(np.mean(np.abs(diff))),
                "max_abs_diff": float(np.max(np.abs(diff))),
                "n_targets": int(len(common)),
            }
        )
    return pd.DataFrame(rows)


def write_summary(
    out_dir: Path,
    effects: pd.DataFrame,
    key_df: pd.DataFrame,
    c4: dict,
    ref_df: pd.DataFrame,
    n_jobs: int,
) -> None:
    lines = [
        "# P0 shared-init audit summary",
        "",
        f"Jobs loaded: **{n_jobs}**",
        "",
        "## Key comparisons (ΔAUC, target-level)",
        "",
        "| ID | comparison | mean Δ | 95% CI | frac targets > 0 |",
        "|---|---|---:|---|---:|",
    ]
    for _, row in key_df.iterrows():
        cid = row.get("id", "")
        lines.append(
            f"| {cid} | {row['comparison']} | {row['mean_delta']:+.1f} | "
            f"[{row['ci_lo']:+.1f}, {row['ci_hi']:+.1f}] | {row['frac_targets_gt']:.2f} |"
        )
    lines.extend(
        [
            "",
            "## C4 init_best (topk_only vs random)",
            "",
            f"- mean Δ = **{c4['mean_delta']:+.2f}** [{c4['ci_lo']:+.2f}, {c4['ci_hi']:+.2f}]",
            f"- frac targets topk_only > random: **{c4['frac_targets_gt']:.2f}**",
            "",
        ]
    )
    if not ref_df.empty:
        lines.append("## Step1 replication check (|ΔAUC| vs reference)")
        lines.append("")
        lines.append("| strategy | mean |Δ| | max |Δ| | n_targets |")
        lines.append("|---|---:|---:|---:|")
        for _, r in ref_df.iterrows():
            lines.append(
                f"| {r['strategy']} | {r['mean_abs_diff']:.4f} | {r['max_abs_diff']:.4f} | {int(r['n_targets'])} |"
            )
        lines.append("")
    lines.append("See `docs/17_step3_experiment_plan.md` §3.6 for pre-registered interpretation.")
    (out_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--results-dir", type=Path, required=True)
    p.add_argument("--reference-dir", type=Path, default=None, help="Step1 loso dir for R1/R2/R0 check")
    p.add_argument("--n-init", type=int, default=5)
    p.add_argument("--out-dir", type=Path, default=None)
    args = p.parse_args()

    results_dir = args.results_dir
    out_dir = args.out_dir or results_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    jobs = load_p0_jobs(results_dir, n_init=args.n_init)
    if jobs.empty:
        raise SystemExit(f"No P0 jobs under {results_dir}")

    tm = p0_target_means(jobs)
    effects, target_deltas = p0_effect_tables(tm)
    effects.to_csv(out_dir / "effects.csv", index=False)
    target_deltas.to_csv(out_dir / "target_deltas.csv", index=False)

    key_rows = []
    for cid, a, b, _desc in KEY_COMPARISONS:
        row = comparison_table(tm, a, b)
        row["id"] = cid
        key_rows.append(row)
    key_df = pd.DataFrame(key_rows)
    key_df.to_csv(out_dir / "key_comparisons.csv", index=False)

    c4 = c4_init_best(tm, args.n_init)
    pd.DataFrame([c4]).to_csv(out_dir / "c4_init_best.csv", index=False)

    ref_df = pd.DataFrame()
    if args.reference_dir:
        ref_df = reference_check(tm, args.reference_dir)
        if not ref_df.empty:
            ref_df.to_csv(out_dir / "reference_check.csv", index=False)

    write_summary(out_dir, effects, key_df, c4, ref_df, len(jobs))
    print((out_dir / "summary.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
