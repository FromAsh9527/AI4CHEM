"""Summarize W3 seed-0 transfer grid for teaching review."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

rows = []
for p in Path("results/transfer_grid").glob("*.json"):
    d = json.loads(p.read_text(encoding="utf-8"))
    rows.append(
        {
            "strategy": d["strategy"],
            "rep": d["representation"],
            "source": d.get("source_plate"),
            "target": d["target_plate"],
            "seed": d["seed"],
            "best_final": d["best_final"],
            "global_best": d["global_best"],
            "frac": d["best_final"] / d["global_best"],
            "q5": d.get("metrics", {}).get("queries_to_top5"),
            "n_source": d.get("meta", {}).get("n_source_used"),
        }
    )

df = pd.DataFrame(rows)
df0 = df[df["seed"] == 0].copy()

# cold baseline per target/rep
cold = (
    df0[df0["strategy"] == "cold_start"]
    .set_index(["target", "rep"])["frac"]
    .to_dict()
)

xfer = df0[df0["strategy"] != "cold_start"].copy()
xfer["cold_frac"] = xfer.apply(lambda r: cold.get((r["target"], r["rep"])), axis=1)
xfer["delta"] = xfer["frac"] - xfer["cold_frac"]

print("=== seed=0 冷启动基线 (frac=找到值/冠军) ===")
print(
    df0[df0["strategy"] == "cold_start"][["rep", "target", "frac", "best_final"]]
    .sort_values(["rep", "target"])
    .to_string(index=False)
)

print("\n=== seed=0 迁移相对冷启动的增益 delta (正=更好) ===")
show = xfer[["strategy", "rep", "source", "target", "frac", "cold_frac", "delta", "n_source"]]
print(show.sort_values(["rep", "strategy", "target", "source"]).to_string(index=False))

print("\n=== 按策略汇总：平均 delta ===")
print(
    xfer.groupby(["strategy", "rep"])["delta"]
    .agg(["mean", "median", "count"])
    .round(3)
    .to_string()
)

pos = int((xfer["delta"] > 0.02).sum())
neg = int((xfer["delta"] < -0.02).sum())
neu = len(xfer) - pos - neg
print(f"\n粗分: 明显正迁移 {pos} / 中性 {neu} / 明显负迁移 {neg}  (阈值 ±0.02)")

out = Path("results/transfer_grid/seed0_summary.csv")
show.to_csv(out, index=False)
print(f"Wrote {out}")
