#!/usr/bin/env python
"""P1+P2 offline: source-count robustness and top-k list stability.

Protocol: docs/17_step3_experiment_plan.md §4

  python scripts/analyze_p1p2_list_stability.py --library amination
  python scripts/analyze_p1p2_list_stability.py --library suzuki
  python scripts/analyze_p1p2_list_stability.py --library both
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from analyze_step1_effects import _bootstrap_mean_ci  # noqa: E402

from transferbo2.benchmarks.source_subset import (  # noqa: E402
    init_metrics,
    jaccard,
    load_yield_matrix,
    nearest_source_topk_ids,
    pooled_topk_ids,
    random_source_topk_ids,
    sample_source_subset,
    source_support,
)
from transferbo2.data.database import connect, load_descriptor_matrix

K = 5

LIBRARY_META = {
    "amination": {
        "long_csv": ROOT / "data" / "processed" / "amination_long.csv",
        "db": ROOT / "data" / "db" / "transferbo2.db",
        "out": ROOT / "results" / "p1p2_source_robustness" / "amination",
        "subset_replicates": 20,
        "source_counts": [1, 2, 3, 5, "all"],
        "desc_name": "morgan_r2",
    },
    "suzuki": {
        "long_csv": ROOT / "data" / "processed" / "suzuki_long.csv",
        "db": ROOT / "data" / "db" / "transferbo2_suzuki.db",
        "out": ROOT / "results" / "p1p2_source_robustness" / "suzuki",
        "subset_replicates": 10,
        "source_counts": [1, 2, 3, 5, "all"],
        "desc_name": "morgan_r2",
    },
}


def _load_desc(db_path: Path, name: str = "morgan_r2") -> dict[str, np.ndarray]:
    with connect(db_path) as conn:
        df = load_descriptor_matrix(conn, entity_type="substrate", name=name)
    if df.empty:
        return {}
    cols = [c for c in df.columns if c != "entity_id"]
    return {str(r["entity_id"]): r[cols].to_numpy(dtype=float) for _, r in df.iterrows()}


def analyze_library(name: str, subset_seed_base: int = 0) -> pd.DataFrame:
    meta = LIBRARY_META[name]
    out = Path(meta["out"])
    out.mkdir(parents=True, exist_ok=True)

    long_df = pd.read_csv(meta["long_csv"])
    mat = load_yield_matrix(meta["long_csv"])
    desc = _load_desc(meta["db"], meta["desc_name"])
    targets = sorted(mat.columns)
    source_counts = meta["source_counts"]
    K_rep = int(meta["subset_replicates"])

    rows = []
    for target in targets:
        all_sources = [c for c in mat.columns if c != target]
        full_ids = pooled_topk_ids(long_df, target, all_sources, k=K, mat=mat)
        full_m = init_metrics(mat, target, full_ids)
        full_sup = source_support(long_df, all_sources, full_ids)

        for n_s in source_counts:
            for rep in range(K_rep):
                seed = subset_seed_base + rep
                subset = sample_source_subset(all_sources, n_s, subset_seed=seed, target=target)
                pool_ids = pooled_topk_ids(long_df, target, subset, k=K, mat=mat)
                pool_m = init_metrics(mat, target, pool_ids)
                rand_ids, rand_src = random_source_topk_ids(
                    long_df, target, subset, k=K, subset_seed=seed, mat=mat
                )
                rand_m = init_metrics(mat, target, rand_ids)
                nn_ids, nn_src, nn_sim = ([], "", float("nan"))
                if desc:
                    nn_ids, nn_src, nn_sim = nearest_source_topk_ids(
                        long_df, target, subset, desc, k=K, mat=mat
                    )
                nn_m = init_metrics(mat, target, nn_ids)
                sup = source_support(long_df, subset, pool_ids)

                rows.append(
                    {
                        "library": name,
                        "target": target,
                        "n_sources": str(n_s),
                        "n_sources_int": len(subset) if n_s != "all" else len(all_sources),
                        "subset_replicate": rep,
                        "subset_seed": seed,
                        "n_hist_sources": len(all_sources),
                        "list_type": "pooled",
                        "top5_ids": "|".join(pool_ids),
                        "jaccard_vs_full": jaccard(pool_ids, full_ids),
                        "init_best": pool_m["init_best"],
                        "init_mean": pool_m["init_mean"],
                        "delta_init_best_vs_full": pool_m["init_best"] - full_m["init_best"],
                        "mean_source_support": float(np.mean(list(sup.values()))) if sup else float("nan"),
                        "min_source_support": float(min(sup.values())) if sup else float("nan"),
                        "full_init_best": full_m["init_best"],
                    }
                )
                rows.append(
                    {
                        "library": name,
                        "target": target,
                        "n_sources": str(n_s),
                        "n_sources_int": len(subset),
                        "subset_replicate": rep,
                        "subset_seed": seed,
                        "n_hist_sources": len(all_sources),
                        "list_type": "random_source",
                        "chosen_source": rand_src,
                        "top5_ids": "|".join(rand_ids),
                        "jaccard_vs_full": jaccard(rand_ids, full_ids),
                        "init_best": rand_m["init_best"],
                        "init_mean": rand_m["init_mean"],
                        "delta_init_best_vs_full": rand_m["init_best"] - full_m["init_best"],
                        "mean_source_support": float("nan"),
                        "min_source_support": float("nan"),
                        "full_init_best": full_m["init_best"],
                    }
                )
                if nn_ids:
                    rows.append(
                        {
                            "library": name,
                            "target": target,
                            "n_sources": str(n_s),
                            "n_sources_int": len(subset),
                            "subset_replicate": rep,
                            "subset_seed": seed,
                            "n_hist_sources": len(all_sources),
                            "list_type": "nearest_morgan",
                            "chosen_source": nn_src,
                            "nearest_sim": nn_sim,
                            "top5_ids": "|".join(nn_ids),
                            "jaccard_vs_full": jaccard(nn_ids, full_ids),
                            "init_best": nn_m["init_best"],
                            "init_mean": nn_m["init_mean"],
                            "delta_init_best_vs_full": nn_m["init_best"] - full_m["init_best"],
                            "mean_source_support": float("nan"),
                            "min_source_support": float("nan"),
                            "full_init_best": full_m["init_best"],
                        }
                    )

    detail = pd.DataFrame(rows)
    detail.to_csv(out / "list_stability_detail.csv", index=False)

    # aggregate by (list_type, n_sources) across targets and replicates
    agg_rows = []
    for (lt, ns), g in detail.groupby(["list_type", "n_sources"]):
        j = g["jaccard_vs_full"].to_numpy(dtype=float)
        d = g["delta_init_best_vs_full"].to_numpy(dtype=float)
        ib = g["init_best"].to_numpy(dtype=float)
        fb = g["full_init_best"].to_numpy(dtype=float)
        mj, jlo, jhi = _bootstrap_mean_ci(j)
        md, dlo, dhi = _bootstrap_mean_ci(d)
        mib, _, _ = _bootstrap_mean_ci(ib)
        mfb, _, _ = _bootstrap_mean_ci(fb)
        agg_rows.append(
            {
                "library": name,
                "list_type": lt,
                "n_sources": ns,
                "n_targets": g["target"].nunique(),
                "n_rows": len(g),
                "jaccard_mean": mj,
                "jaccard_ci_lo": jlo,
                "jaccard_ci_hi": jhi,
                "delta_init_best_mean": md,
                "delta_init_best_ci_lo": dlo,
                "delta_init_best_ci_hi": dhi,
                "init_best_mean": mib,
                "full_init_best_mean": mfb,
                "frac_init_ge_full": float(np.mean(ib >= fb - 1e-9)),
            }
        )
    summary = pd.DataFrame(agg_rows)
    summary.to_csv(out / "list_stability_summary.csv", index=False)

    # curves: pooled only, target-level mean per n_s
    pooled = detail[detail["list_type"] == "pooled"]
    curve_rows = []
    for ns, g in pooled.groupby("n_sources"):
        per_target = g.groupby("target").agg(
            jaccard=("jaccard_vs_full", "mean"),
            init_best=("init_best", "mean"),
            full_init_best=("full_init_best", "first"),
            delta_init=("delta_init_best_vs_full", "mean"),
        )
        curve_rows.append(
            {
                "n_sources": ns,
                "n_sources_int": int(g["n_sources_int"].iloc[0]),
                "jaccard_target_mean": float(per_target["jaccard"].mean()),
                "init_best_target_mean": float(per_target["init_best"].mean()),
                "full_init_best_target_mean": float(per_target["full_init_best"].mean()),
                "delta_init_target_mean": float(per_target["delta_init"].mean()),
                "frac_target_init_ge_full": float((per_target["init_best"] >= per_target["full_init_best"] - 1e-9).mean()),
            }
        )
    curve = pd.DataFrame(curve_rows).sort_values("n_sources_int")
    curve.to_csv(out / "pooled_curve_by_n_sources.csv", index=False)

    _plot_curves(name, curve, out)
    _write_summary_md(name, summary, curve, out)
    return detail


def _plot_curves(name: str, curve: pd.DataFrame, out: Path) -> None:
    if curve.empty:
        return
    x = curve["n_sources_int"].to_numpy()
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    axes[0].plot(x, curve["jaccard_target_mean"], "o-", label="Jaccard vs full")
    axes[0].set_xlabel("n historical sources in subset")
    axes[0].set_ylabel("Jaccard (top-5)")
    axes[0].set_title(f"{name}: list stability")
    axes[0].grid(True, alpha=0.3)

    axes[1].plot(x, curve["init_best_target_mean"], "o-", label="subset pooled")
    axes[1].plot(x, curve["full_init_best_target_mean"], "s--", label="full pool", color="gray")
    axes[1].set_xlabel("n historical sources in subset")
    axes[1].set_ylabel("init_best on target")
    axes[1].set_title(f"{name}: init quality vs n_sources")
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(out / "pooled_curve.png", dpi=150)
    plt.close(fig)


def _write_summary_md(name: str, summary: pd.DataFrame, curve: pd.DataFrame, out: Path) -> None:
    pooled = summary[summary["list_type"] == "pooled"].sort_values("n_sources")
    lines = [
        f"# P1+P2 list stability — {name}",
        "",
        "## Pooled top-5 vs full history",
        "",
        "| n_sources | Jaccard [CI] | Δinit_best [CI] | frac init ≥ full |",
        "|---|---:|---|---:|",
    ]
    for _, r in pooled.iterrows():
        lines.append(
            f"| {r['n_sources']} | {r['jaccard_mean']:.2f} [{r['jaccard_ci_lo']:.2f}, {r['jaccard_ci_hi']:.2f}] | "
            f"{r['delta_init_best_mean']:+.2f} [{r['delta_init_best_ci_lo']:+.2f}, {r['delta_init_best_ci_hi']:+.2f}] | "
            f"{r['frac_init_ge_full']:.2f} |"
        )
    lines.extend(
        [
            "",
            "## List types at n_sources=all (reference)",
            "",
        ]
    )
    all_row = summary[summary["n_sources"] == "all"]
    for _, r in all_row.iterrows():
        lines.append(
            f"- **{r['list_type']}**: Jaccard={r['jaccard_mean']:.2f}, init_best={r['init_best_mean']:.1f}, "
            f"Δinit={r['delta_init_best_mean']:+.2f}"
        )
    lines.append("")
    lines.append(f"Detail: `list_stability_detail.csv` · Figure: `pooled_curve.png`")
    (out / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--library", choices=["amination", "suzuki", "both"], default="both")
    p.add_argument("--subset-seed-base", type=int, default=0)
    args = p.parse_args()
    libs = ["amination", "suzuki"] if args.library == "both" else [args.library]
    for lib in libs:
        print(f"=== {lib} ===", flush=True)
        analyze_library(lib, subset_seed_base=args.subset_seed_base)
        print(f"  -> {LIBRARY_META[lib]['out']}", flush=True)


if __name__ == "__main__":
    main()
