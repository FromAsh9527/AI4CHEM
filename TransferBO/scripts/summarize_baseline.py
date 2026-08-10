"""Summarize baseline suite JSON results for teaching review."""
from pathlib import Path
import json
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
            "frac_of_opt": d["best_final"] / d["global_best"],
        }
    )

df = pd.DataFrame(rows).sort_values(["target", "strategy", "rep"])
print(df.to_string(index=False))
print()
for t in sorted(df["target"].unique()):
    sub = df[df["target"] == t]
    r = sub[sub["strategy"] == "random"].iloc[0]
    m = sub[(sub["strategy"] == "cold_start") & (sub["rep"] == "morgan")].iloc[0]
    o = sub[(sub["strategy"] == "cold_start") & (sub["rep"] == "ohe")].iloc[0]
    print(
        f"{t}: random_best={r.best_final:.0f} | OHE={o.best_final:.0f} | "
        f"Morgan={m.best_final:.0f} | global={r.global_best:.0f}"
    )
