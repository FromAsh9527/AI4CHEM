#!/usr/bin/env python
"""W8: summarize EDBO amination min S0 (cold vs label_warm).

Example:
  python scripts/summarize_amination_min_s0.py
  python scripts/summarize_amination_min_s0.py --root results/external_edbo_amination_min_s0_pilot
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
STATS = ROOT / "results" / "paper_stats"
PRIMARY = (30, 40, 50)
NEAR0 = 0.02


def load_runs(root: Path) -> pd.DataFrame:
    rows = []
    for p in root.glob("*.json"):
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT / "results" / "external_edbo_amination_min_s0_pilot",
    )
    parser.add_argument("--out-prefix", type=str, default="edbo_amination_min_s0")
    args = parser.parse_args()
    STATS.mkdir(parents=True, exist_ok=True)

    if not args.root.exists():
        note = [
            "# Amination min S0 summary",
            "",
            f"No results directory: `{args.root}`",
            "Submit full grid: `configs/transfer_grid_edbo_amination_min_s0.yaml`",
            "Local pilot: `configs/transfer_grid_edbo_amination_min_s0_pilot.yaml`",
        ]
        (STATS / f"{args.out_prefix}_SUMMARY.md").write_text("\n".join(note), encoding="utf-8")
        print("Missing results:", args.root)
        return 1

    df = load_runs(args.root)
    if df.empty:
        print("No JSON runs in", args.root)
        return 1

    cold = (
        df[df["strategy"] == "cold_start"]
        .groupby(["representation", "target", "seed", "budget"])["frac"]
        .mean()
        .rename("cold_frac")
    )
    lab = df[df["strategy"] == "label_warm"].copy()
    lab = lab.merge(cold.reset_index(), on=["representation", "target", "seed", "budget"], how="left")
    lab["delta_frac"] = lab["frac"] - lab["cold_frac"]

    pair = (
        lab.groupby(["representation", "source", "target", "budget"], as_index=False)["delta_frac"]
        .agg(delta_mean="mean", n_seeds="count")
    )
    primary = (
        pair.groupby(["representation", "source", "target"], as_index=False)["delta_mean"]
        .mean()
        .rename(columns={"delta_mean": "delta_frac_primary"})
    )
    overall = (
        primary.groupby("representation", as_index=False)["delta_frac_primary"]
        .agg(
            mean="mean",
            median="median",
            n_pairs="count",
            n_neg=lambda s: int((s < -NEAR0).sum()),
            n_pos=lambda s: int((s > NEAR0).sum()),
            n_near0=lambda s: int((s.abs() <= NEAR0).sum()),
        )
    )

    pair.to_csv(STATS / f"{args.out_prefix}_pair_by_budget.csv", index=False)
    primary.to_csv(STATS / f"{args.out_prefix}_pair_primary.csv", index=False)
    overall.to_csv(STATS / f"{args.out_prefix}_overall.csv", index=False)

    lines = [
        "# Amination min S0 summary (W8)",
        "",
        f"Root: `{args.root}`",
        f"Primary endpoint: mean Δfrac over B∈{list(PRIMARY)}; near0={NEAR0}",
        "",
        "## Overall (pair-weighted)",
        overall.round(4).to_string(index=False),
        "",
        "## Writing branch",
    ]
    means = overall.set_index("representation")["mean"]
    if len(means) and (means < -NEAR0).all():
        lines.append("Same-direction negative → support cross-family 'not consistently safe default'.")
    elif len(means) and (means.abs() <= NEAR0).all():
        lines.append("Near-zero → still supports 'not a safe default' (no reliable gain).")
    elif len(means) and (means > NEAR0).any():
        lines.append("Positive on some reps → family-dependent; keep Suzuki as important counterexample.")
    else:
        lines.append("Mixed / incomplete — expand seeds before upgrading claim.")
    (STATS / f"{args.out_prefix}_SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")
    print(overall.round(4).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
