"""Cross-family source-count threshold check (docs/18 §4.3) — generic version.

Reproduces the P1+P2 LSO logic on a P4 holdout library:
  for each target, sample source subsets of size n_s in {1,3,5,all}
  (K replicates, subset_seed 0..K-1), rebuild pooled top-5 (mean rule,
  restricted to the target's measured conditions, matching select_topk_init),
  then compare Jaccard and init_best vs the full-history pooled list.

Usage:
    python scripts/analyze_hitea_lso.py --db data/db/transferbo2_hitea.db --tag hitea
    python scripts/analyze_hitea_lso.py --db data/db/transferbo2_borylation.db --tag borylation
Output:
    results/p4_<tag>/lso_source_stability.csv + summary
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
N_S_LIST = (1, 3, 5, "all")
TOP_K = 5


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=ROOT / "data" / "db" / "transferbo2_hitea.db")
    ap.add_argument("--tag", type=str, default="hitea")
    ap.add_argument("--k", type=int, default=20)
    args = ap.parse_args()
    K = args.k
    OUT = ROOT / "results" / f"p4_{args.tag}" / "lso_source_stability.csv"

    conn = sqlite3.connect(str(args.db))
    df = pd.read_sql("SELECT substrate_id, condition_id, yield FROM experiments", conn)
    conn.close()
    df = df.groupby(["substrate_id", "condition_id"], as_index=False)["yield"].mean()

    tasks = sorted(df["substrate_id"].unique())
    rows = []
    for tgt in tasks:
        hist = df[df["substrate_id"] != tgt]
        tgt_conds = set(df[df["substrate_id"] == tgt]["condition_id"])
        full = hist.groupby("condition_id")["yield"].mean()
        full_top = full.loc[full.index.isin(tgt_conds)].sort_values(ascending=False).index[:TOP_K]
        full_best = float(df[df["substrate_id"] == tgt].set_index("condition_id")["yield"].reindex(full_top).max())

        sources = sorted(hist["substrate_id"].unique())
        for ns in N_S_LIST:
            n = len(sources) if ns == "all" else int(ns)
            reps = 1 if ns == "all" else K
            for rep in range(reps):
                if ns == "all":
                    sub = hist
                else:
                    rng = np.random.default_rng(rep)
                    chosen = rng.choice(sources, size=n, replace=False)
                    sub = hist[hist["substrate_id"].isin(chosen)]
                mean = sub.groupby("condition_id")["yield"].mean()
                top = mean.loc[mean.index.isin(tgt_conds)].sort_values(ascending=False).index[:TOP_K]
                jac = len(set(top) & set(full_top)) / len(set(top) | set(full_top))
                ib = float(
                    df[df["substrate_id"] == tgt].set_index("condition_id")["yield"].reindex(top).max()
                )
                rows.append(
                    {
                        "target": tgt, "n_sources": n, "rep": rep,
                        "jaccard_vs_full": jac, "init_best": ib,
                        "d_init_best_vs_full": ib - full_best,
                    }
                )
    res = pd.DataFrame(rows)
    res.to_csv(OUT, index=False)

    full_ib = res[res["n_sources"] == len(tasks) - 1][["target", "init_best"]].rename(
        columns={"init_best": "full_ib"}
    )
    res2 = res.merge(full_ib, on="target")
    print(f"# {args.tag} LSO source-count stability (tasks={len(tasks)}, K={K}, top-{TOP_K})")
    print("")
    print("| n_sources | Jaccard [mean] | Δinit_best [mean] | frac init>=full |")
    print("|---|---|---|---|")
    for ns, g in res.groupby("n_sources"):
        print(
            f"| {ns} | {g['jaccard_vs_full'].mean():.2f} | {g['d_init_best_vs_full'].mean():+.2f} "
            f"| {np.mean(g['d_init_best_vs_full'] >= 0):.2f} |"
        )
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()

