"""Aggregate 20-seed baseline results for teaching review."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

rows = []
for p in Path("results/baseline/suite").glob("*.json"):
    if p.name == "index.json":
        continue
    d = json.loads(p.read_text(encoding="utf-8"))
    rows.append(
        {
            "strategy": d["strategy"],
            "rep": d["representation"],
            "target": d["target_plate"],
            "seed": d["seed"],
            "best_final": d["best_final"],
            "global_best": d["global_best"],
            "q_top5": d["metrics"].get("queries_to_top5"),
            "q_top1": d["metrics"].get("queries_to_top1"),
            "frac_of_opt": d["best_final"] / d["global_best"] if d["global_best"] else None,
        }
    )

df = pd.DataFrame(rows)
# method label
df["method"] = df.apply(
    lambda r: "random" if r["strategy"] == "random" else f"BO-{r['rep']}",
    axis=1,
)

summary = (
    df.groupby(["target", "method"], as_index=False)
    .agg(
        n=("seed", "count"),
        best_mean=("best_final", "mean"),
        best_std=("best_final", "std"),
        frac_mean=("frac_of_opt", "mean"),
        q5_median=("q_top5", "median"),
        q5_mean=("q_top5", "mean"),
    )
    .sort_values(["target", "method"])
)

out = Path("results/baseline/suite/baseline_20seeds_summary.csv")
summary.to_csv(out, index=False)
print(summary.to_string(index=False))
print(f"\nWrote {out}")
print(f"Total runs: {len(df)}")

# win rates vs random on best_final
print("\n=== Morgan-BO vs random: 在多少种子上更好 (best_final) ===")
for t in sorted(df["target"].unique()):
    sub = df[df["target"] == t]
    r = sub[sub["method"] == "random"].set_index("seed")["best_final"]
    m = sub[sub["method"] == "BO-morgan"].set_index("seed")["best_final"]
    common = r.index.intersection(m.index)
    wins = int((m.loc[common] > r.loc[common]).sum())
    ties = int((m.loc[common] == r.loc[common]).sum())
    print(
        f"{t}: Morgan 更好 {wins}/{len(common)}  "
        f"(平局 {ties}); "
        f"mean frac Morgan={m.loc[common].mean()/sub['global_best'].iloc[0]:.3f} "
        f"vs random={r.loc[common].mean()/sub['global_best'].iloc[0]:.3f}"
    )
