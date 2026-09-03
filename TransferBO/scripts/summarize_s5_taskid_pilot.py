#!/usr/bin/env python
"""Summarize S5 (init-only) and task-ID pilot grids vs cold."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
STATS = ROOT / "results" / "paper_stats"
PRIMARY = (30, 40, 50)


def load_long(root: Path) -> pd.DataFrame:
    rows = []
    for p in Path(root).glob("*.json"):
        if p.name.startswith(("grid_", "heatmap", "summary")):
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        curve = d.get("bo", {}).get("best_so_far") or []
        gbest = float(d.get("global_best") or 1.0)
        for b in PRIMARY:
            if len(curve) < b:
                continue
            rows.append(
                {
                    "strategy": d["strategy"],
                    "representation": d["representation"],
                    "source": d.get("source_plate"),
                    "target": d["target_plate"],
                    "seed": d["seed"],
                    "budget": b,
                    "frac": float(curve[b - 1]) / gbest if gbest else np.nan,
                }
            )
    return pd.DataFrame(rows)


def summarize(root: Path, tag: str) -> pd.DataFrame:
    df = load_long(root)
    if df.empty:
        return df
    cold = (
        df[df["strategy"] == "cold_start"]
        .groupby(["representation", "target", "seed", "budget"])["frac"]
        .mean()
        .rename("cold_frac")
    )
    warm = df[df["strategy"] != "cold_start"].copy()
    warm = warm.merge(
        cold.reset_index(), on=["representation", "target", "seed", "budget"], how="left"
    )
    warm["delta_frac"] = warm["frac"] - warm["cold_frac"]
    primary = (
        warm.groupby(["strategy", "representation", "source", "target"], as_index=False)[
            "delta_frac"
        ]
        .mean()
        .rename(columns={"delta_frac": "delta_frac_primary"})
    )
    overall = (
        primary.groupby(["strategy", "representation"], as_index=False)["delta_frac_primary"]
        .mean()
        .rename(columns={"delta_frac_primary": "mean_delta_B30_50"})
    )
    STATS.mkdir(parents=True, exist_ok=True)
    primary.to_csv(STATS / f"edbo_suzuki_{tag}_pair_primary.csv", index=False)
    overall.to_csv(STATS / f"edbo_suzuki_{tag}_overall.csv", index=False)
    note = [
        f"# {tag} pilot summary",
        "",
        f"Root: `{root}`",
        "",
        overall.round(4).to_string(index=False),
        "",
    ]
    (STATS / f"edbo_suzuki_{tag}_SUMMARY.md").write_text("\n".join(note), encoding="utf-8")
    return overall


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--s5-root", type=Path, default=ROOT / "results" / "external_edbo_suzuki_s5")
    parser.add_argument(
        "--taskid-root", type=Path, default=ROOT / "results" / "external_edbo_suzuki_taskid"
    )
    args = parser.parse_args()
    if args.s5_root.exists():
        print("S5")
        print(summarize(args.s5_root, "s5").round(4).to_string(index=False))
    if args.taskid_root.exists():
        print("taskid")
        print(summarize(args.taskid_root, "taskid").round(4).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
