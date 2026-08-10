"""Compare random-init cold_start vs diversity-init cold_diversity."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

rows = []
for p in Path("results/baseline/suite").glob("*.json"):
    if p.name.startswith("index"):
        continue
    d = json.loads(p.read_text(encoding="utf-8"))
    strat = d["strategy"]
    rep = d["representation"]
    if strat == "random":
        method = "random"
    elif strat == "cold_diversity":
        method = f"div-{rep}"
    elif strat == "cold_start":
        method = f"randinit-{rep}"
    else:
        method = f"{strat}-{rep}"
    rows.append(
        {
            "method": method,
            "target": d["target_plate"],
            "seed": d["seed"],
            "frac": d["best_final"] / d["global_best"],
            "best_final": d["best_final"],
            "q_top5": d["metrics"].get("queries_to_top5"),
        }
    )

df = pd.DataFrame(rows)
focus = [
    "random",
    "randinit-morgan",
    "div-morgan",
    "randinit-drfp",
    "div-drfp",
]
df = df[df["method"].isin(focus)]

# require full 20 seeds for fair table
counts = df.groupby(["target", "method"])["seed"].nunique().reset_index(name="n")
print("Seed counts:")
print(counts.to_string(index=False))

summary = (
    df.groupby(["target", "method"], as_index=False)
    .agg(
        n=("seed", "nunique"),
        frac_mean=("frac", "mean"),
        frac_std=("frac", "std"),
        q5_median=("q_top5", "median"),
    )
    .sort_values(["target", "frac_mean"], ascending=[True, False])
)
out = Path("results/baseline/suite/init_mode_comparison.csv")
summary.to_csv(out, index=False)
print("\n" + summary.to_string(index=False))
print(f"\nWrote {out}")

print("\n=== diversity vs random-init (same representation) ===")
for t in sorted(df["target"].unique()):
    sub = df[df["target"] == t]
    print(f"\n{t}")
    for rep in ["morgan", "drfp"]:
        a = sub[sub["method"] == f"randinit-{rep}"].set_index("seed")["frac"]
        b = sub[sub["method"] == f"div-{rep}"].set_index("seed")["frac"]
        common = a.index.intersection(b.index)
        if len(common) == 0:
            print(f"  {rep}: incomplete")
            continue
        wins = int((b.loc[common] > a.loc[common]).sum())
        print(
            f"  {rep}: div_mean={b.loc[common].mean():.3f} vs "
            f"randinit_mean={a.loc[common].mean():.3f} | "
            f"div更好 {wins}/{len(common)}"
        )
