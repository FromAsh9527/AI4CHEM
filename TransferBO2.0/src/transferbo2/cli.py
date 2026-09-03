"""Console entry points used by pyproject scripts."""

from __future__ import annotations

import argparse
from pathlib import Path


def init_db_main() -> None:
    from transferbo2.data.database import DEFAULT_DB, init_schema
    from transferbo2.data.demo import write_demo_to_db

    p = argparse.ArgumentParser()
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    p.add_argument("--demo", action="store_true")
    p.add_argument("--seed", type=int, default=7)
    args = p.parse_args()
    if args.demo:
        print(f"Demo database written: {write_demo_to_db(args.db, seed=args.seed)}")
    else:
        print(f"Empty schema initialized: {init_schema(args.db)}")


def demo_main() -> None:
    import sys

    sys.argv = [sys.argv[0], "--demo", *sys.argv[1:]]
    init_db_main()


def run_main() -> None:
    # thin wrapper: prefer scripts/run_experiment.py for full CLI
    from pathlib import Path
    import runpy
    import sys

    script = Path(__file__).resolve().parents[2] / "scripts" / "run_experiment.py"
    sys.argv[0] = str(script)
    runpy.run_path(str(script), run_name="__main__")
