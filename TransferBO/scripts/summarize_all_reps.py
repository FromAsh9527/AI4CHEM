"""Compare all baseline representations including fragprint and DRFP."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

rows = []
for p in Path("results/baseline/suite").glob("*.json"):
    if p.name == "index.json":
        continue
    d = json.loads(p.read_text(encoding="utf-8"))
    method = "random" if d["strategy"] == "random" else f"BO-{d['representation']}"
    rows.append(
        {
            "method": method,
            "target": d["target_plate"],
            "seed": d["seed"],
            "best_final": d["best_final"],
            "global_best": d["global_best"],
            "frac": d["best_final"] / d["global_best"],
            "q_top5": d["metrics"].get("queries_to_top5"),
        }
    )

df = pd.DataFrame(rows)
summary = (
    df.groupby(["target", "method"], as_index=False)
    .agg(
        n=("seed", "count"),
        frac_mean=("frac", "mean"),
        frac_std=("frac", "std"),
        best_mean=("best_final", "mean"),
        q5_median=("q_top5", "median"),
    )
    .sort_values(["target", "frac_mean"], ascending=[True, False])
)
out = Path("results/baseline/suite/baseline_all_reps_summary.csv")
summary.to_csv(out, index=False)
print(summary.to_string(index=False))
print(f"\nWrote {out}")

print("\n=== vs random: 平均 frac 更高的次数（按板）===")
for t in sorted(df["target"].unique()):
    sub = df[df["target"] == t]
    r = sub[sub["method"] == "random"].set_index("seed")["frac"]
    print(f"\n{t}  (random mean frac={r.mean():.3f})")
    for m in sorted(sub["method"].unique()):
        if m == "random":
            continue
        s = sub[sub["method"] == m].set_index("seed")["frac"]
        common = r.index.intersection(s.index)
        if len(common) == 0:
            continue
        wins = int((s.loc[common] > r.loc[common]).sum())
        print(
            f"  {m:14s} mean={s.loc[common].mean():.3f}  "
            f"win_vs_random={wins}/{len(common)}"
        )
