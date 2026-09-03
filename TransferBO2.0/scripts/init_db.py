#!/usr/bin/env python
"""Initialize SQLite DB (optionally with synthetic demo library)."""

from __future__ import annotations

import argparse
from pathlib import Path

from transferbo2.data.database import DEFAULT_DB, init_schema
from transferbo2.data.demo import write_demo_to_db


def main() -> None:
    p = argparse.ArgumentParser(description="Initialize TransferBO2.0 database")
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    p.add_argument("--demo", action="store_true", help="Populate synthetic multi-substrate multi-plate demo")
    p.add_argument("--seed", type=int, default=7)
    args = p.parse_args()
    if args.demo:
        path = write_demo_to_db(args.db, seed=args.seed)
        print(f"Demo database written: {path}")
        print(f"Processed CSV: data/processed/demo_long.csv")
    else:
        path = init_schema(args.db)
        print(f"Empty schema initialized: {path}")


if __name__ == "__main__":
    main()
