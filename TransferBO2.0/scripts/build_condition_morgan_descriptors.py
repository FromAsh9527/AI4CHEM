#!/usr/bin/env python
"""Build condition morgan_r2 into TransferBO2 DBs (keep substrate descriptors).

Uses catalyst/ligand/base/solvent SMILES OR-bits. Needed so HPC can run
condition_features=morgan_r2 without RDKit at runtime.

  python scripts/build_condition_morgan_descriptors.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from transferbo2.data.database import PACKAGE_ROOT, connect
from transferbo2.descriptors.morgan import component_morgan_or, require_rdkit

NAME = "morgan_r2"
N_BITS = 2048
RADIUS = 2

DEFAULT_DBS = (
    PACKAGE_ROOT / "data" / "db" / "transferbo2.db",
    PACKAGE_ROOT / "data" / "db" / "transferbo2_suzuki.db",
)


def build_db(db_path: Path) -> int:
    require_rdkit()
    if not db_path.exists():
        raise FileNotFoundError(db_path)

    with connect(db_path) as conn:
        conds = pd.read_sql_query(
            "SELECT condition_id, catalyst, ligand, base, solvent FROM conditions",
            conn,
        )
        conn.execute(
            "DELETE FROM descriptors WHERE entity_type=? AND name=?",
            ("condition", NAME),
        )
        n = 0
        empty = 0
        for _, row in conds.iterrows():
            cid = str(row["condition_id"])
            vec = component_morgan_or(
                row.get("catalyst"),
                row.get("ligand"),
                row.get("base"),
                row.get("solvent"),
                n_bits=N_BITS,
                radius=RADIUS,
            )
            if float(vec.sum()) <= 0:
                empty += 1
            conn.execute(
                """INSERT OR REPLACE INTO descriptors(
                    descriptor_id, entity_type, entity_id, name, dim, vector_json
                   ) VALUES (?,?,?,?,?,?)""",
                (
                    f"cmorgan_{hashlib.md5(cid.encode()).hexdigest()[:16]}",
                    "condition",
                    cid,
                    NAME,
                    N_BITS,
                    json.dumps(vec.astype(float).tolist()),
                ),
            )
            n += 1
        conn.commit()
    if empty:
        print(f"  [WARN] {empty}/{n} conditions had empty Morgan (all NA SMILES?)")
    return n


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", type=Path, action="append", default=None)
    args = p.parse_args()
    dbs = list(args.db) if args.db else [d for d in DEFAULT_DBS if d.exists()]
    if not dbs:
        raise SystemExit("No DBs found")
    for db in dbs:
        print(f"Building condition {NAME} -> {db}")
        n = build_db(db)
        print(f"  wrote {n} condition vectors (dim={N_BITS})")


if __name__ == "__main__":
    main()
