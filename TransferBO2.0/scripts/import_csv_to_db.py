#!/usr/bin/env python
"""Import a processed long CSV into the SQLite database."""

from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path

import pandas as pd

from transferbo2.data.database import DEFAULT_DB, connect, init_schema


REQUIRED = ["reaction_id", "substrate_id", "plate_id", "condition_id", "yield"]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--csv", type=Path, required=True)
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    p.add_argument("--replace", action="store_true", help="Wipe experiments before import")
    args = p.parse_args()

    df = pd.read_csv(args.csv)
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise SystemExit(f"CSV missing columns: {missing}")

    init_schema(args.db)
    with connect(args.db) as conn:
        if args.replace:
            conn.execute("DELETE FROM experiments")

        for rid in df["reaction_id"].unique():
            conn.execute(
                "INSERT OR IGNORE INTO reactions(reaction_id, name, template) VALUES (?,?,?)",
                (rid, rid, rid),
            )
        for sid, g in df.groupby("substrate_id"):
            rid = g["reaction_id"].iloc[0]
            conn.execute(
                "INSERT OR IGNORE INTO substrates(substrate_id, reaction_id, name, smiles) VALUES (?,?,?,?)",
                (sid, rid, sid, g["smiles"].iloc[0] if "smiles" in g else None),
            )
        for pid, g in df.groupby("plate_id"):
            rid = g["reaction_id"].iloc[0]
            conn.execute(
                "INSERT OR IGNORE INTO plates(plate_id, reaction_id, date) VALUES (?,?,?)",
                (pid, rid, g["date"].iloc[0] if "date" in g else None),
            )
        for cid, g in df.groupby("condition_id"):
            rid = g["reaction_id"].iloc[0]
            row = g.iloc[0]
            conn.execute(
                """INSERT OR IGNORE INTO conditions(
                    condition_id, reaction_id, catalyst, ligand, base, solvent,
                    temperature_c, time_h, equiv, is_anchor
                ) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    cid,
                    rid,
                    row.get("catalyst"),
                    row.get("ligand"),
                    row.get("base"),
                    row.get("solvent"),
                    row.get("temperature_c"),
                    row.get("time_h"),
                    row.get("equiv"),
                    int(row.get("is_anchor", 0) or 0),
                ),
            )
        for _, r in df.iterrows():
            eid = r["experiment_id"] if "experiment_id" in df.columns and pd.notna(r["experiment_id"]) else f"imp_{uuid.uuid4().hex[:12]}"
            conn.execute(
                """INSERT OR REPLACE INTO experiments(
                    experiment_id, reaction_id, substrate_id, plate_id, condition_id,
                    well, row, col, date, yield, selectivity, replicate, is_anchor,
                    quality_flag, source
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    eid,
                    r["reaction_id"],
                    r["substrate_id"],
                    r["plate_id"],
                    r["condition_id"],
                    r.get("well"),
                    r.get("row"),
                    r.get("col"),
                    r.get("date"),
                    float(r["yield"]),
                    r.get("selectivity"),
                    int(r.get("replicate", 1) or 1),
                    int(r.get("is_anchor", 0) or 0),
                    r.get("quality_flag", "ok"),
                    r.get("source", "import"),
                ),
            )
        conn.commit()
    print(f"Imported {len(df)} rows into {args.db}")


if __name__ == "__main__":
    main()
