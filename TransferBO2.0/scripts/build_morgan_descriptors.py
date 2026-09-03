#!/usr/bin/env python
"""Build morgan_r2 substrate descriptors into TransferBO2 DBs (keep hashed_smiles_v1).

Usage:
  python scripts/build_morgan_descriptors.py
  python scripts/build_morgan_descriptors.py --db data/db/transferbo2.db
  python scripts/build_morgan_descriptors.py --db data/db/transferbo2_suzuki.db
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

import numpy as np

from transferbo2.data.database import PACKAGE_ROOT, connect
from transferbo2.descriptors.morgan import component_morgan_or, morgan_bit_vector, require_rdkit

NAME = "morgan_r2"
N_BITS = 2048
RADIUS = 2

DEFAULT_DBS = (
    PACKAGE_ROOT / "data" / "db" / "transferbo2.db",
    PACKAGE_ROOT / "data" / "db" / "transferbo2_suzuki.db",
)


def _substrate_vector(row: sqlite3.Row) -> np.ndarray:
    """Amination: single SMILES. Suzuki: OR of elec+nuc (fallback to pair smiles)."""
    elec = row["smiles_elec"]
    nuc = row["smiles_nuc"]
    smiles = row["smiles"]
    if elec and nuc and str(elec).strip() and str(nuc).strip():
        return component_morgan_or(elec, nuc, n_bits=N_BITS, radius=RADIUS)
    return morgan_bit_vector(str(smiles or ""), n_bits=N_BITS, radius=RADIUS)


def build_db(db_path: Path, *, replace: bool = True) -> int:
    require_rdkit()
    if not db_path.exists():
        raise FileNotFoundError(db_path)

    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT substrate_id, smiles, smiles_elec, smiles_nuc FROM substrates"
        ).fetchall()
        if replace:
            conn.execute(
                "DELETE FROM descriptors WHERE entity_type=? AND name=?",
                ("substrate", NAME),
            )
        n = 0
        for row in rows:
            sid = row["substrate_id"]
            vec = _substrate_vector(row)
            on_bits = int(vec.sum())
            if on_bits <= 0:
                print(f"  [WARN] {sid}: empty Morgan (invalid SMILES?)")
            conn.execute(
                """INSERT OR REPLACE INTO descriptors(
                    descriptor_id, entity_type, entity_id, name, dim, vector_json
                   ) VALUES (?,?,?,?,?,?)""",
                (
                    f"morgan_{sid}",
                    "substrate",
                    sid,
                    NAME,
                    N_BITS,
                    json.dumps(vec.astype(float).tolist()),
                ),
            )
            n += 1
        conn.commit()
    return n


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--db",
        type=Path,
        action="append",
        default=None,
        help="DB path (repeatable). Default: amination + suzuki DBs if present.",
    )
    args = p.parse_args()
    dbs = list(args.db) if args.db else [d for d in DEFAULT_DBS if d.exists()]
    if not dbs:
        raise SystemExit("No DBs found. Pass --db or run ingest first.")

    for db in dbs:
        print(f"Building {NAME} -> {db}")
        n = build_db(db)
        print(f"  wrote {n} substrate vectors (dim={N_BITS}, r={RADIUS})")


if __name__ == "__main__":
    main()
