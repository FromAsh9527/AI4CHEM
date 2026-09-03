#!/usr/bin/env python
"""Summarize LOSO/smoke JSON or CSV results."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from transferbo2.metrics.evaluate import negative_transfer_rate


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--summary-csv", type=Path, help="loso_summary.csv from run_loso")
    p.add_argument("--run-json", type=Path, help="run.json from run_experiment")
    args = p.parse_args()

    if args.summary_csv and args.summary_csv.exists():
        df = pd.read_csv(args.summary_csv)
        print(df.groupby("strategy")[["auc", "final_best", "hit10_top5pct"]].agg(["mean", "std"]))
        if "cold_start" in set(df["strategy"]):
            cold = df[df["strategy"] == "cold_start"].set_index(["target_substrate", "seed"])["auc"]
            for name, g in df[df["strategy"] != "cold_start"].groupby("strategy"):
                aligned_tr, aligned_cold = [], []
                for _, r in g.iterrows():
                    key = (r["target_substrate"], r["seed"])
                    if key in cold.index:
                        aligned_tr.append(r["auc"])
                        aligned_cold.append(float(cold.loc[key]))
                ntr = negative_transfer_rate(aligned_tr, aligned_cold)
                print(f"NTR[{name}] = {ntr:.3f} (n={len(aligned_tr)})")

    if args.run_json and args.run_json.exists():
        recs = json.loads(args.run_json.read_text(encoding="utf-8"))
        rows = [
            {
                "strategy": r["strategy"],
                "seed": r["seed"],
                "auc": r["stats"]["auc"],
                "final_best": r["stats"]["final_best"],
                "hit10_top5pct": r["stats"]["hit10_top5pct"],
            }
            for r in recs
        ]
        print(pd.DataFrame(rows))


if __name__ == "__main__":
    main()
