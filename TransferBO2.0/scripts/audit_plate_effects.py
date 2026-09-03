#!/usr/bin/env python
"""Audit plate effects on the current database / CSV."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from transferbo2.data.database import DEFAULT_DB, connect, experiments_frame
from transferbo2.plate.effects import (
    anchor_plate_offsets,
    plate_condition_spearman,
    variance_components,
)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    p.add_argument("--out", type=Path, default=Path("results/plate_audit.json"))
    args = p.parse_args()

    with connect(args.db) as conn:
        df = experiments_frame(conn)
    if df.empty:
        raise SystemExit("No experiments in DB. Run: python scripts/init_db.py --demo")

    report = {
        "n_rows": int(len(df)),
        "n_substrates": int(df["substrate_id"].nunique()),
        "n_plates": int(df["plate_id"].nunique()),
        "n_conditions": int(df["condition_id"].nunique()),
        "n_anchors": int((df["is_anchor"] == 1).sum()),
        "variance_components": variance_components(df),
        "anchor_offsets": anchor_plate_offsets(df).to_dict(orient="records"),
        "plate_spearman": plate_condition_spearman(df).to_dict(orient="records"),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
