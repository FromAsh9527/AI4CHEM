"""Minimal EDBO+ smoke test: scope generation + initial CVT sampling."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "workspaces" / "_smoke"
CSV_NAME = "my_optimization.csv"


def main() -> int:
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True, exist_ok=True)

    from edbo.plus.optimizer_botorch import EDBOplus

    EDBOplus().generate_reaction_scope(
        components={
            "solvent": ["THF", "Toluene", "DMSO"],
            "T": [-10, 0, 10, 25],
            "concentration": [0.1, 0.2, 1.0],
        },
        directory=str(WORK),
        filename=CSV_NAME,
        check_overwrite=False,
    )

    EDBOplus().run(
        directory=str(WORK),
        filename=CSV_NAME,
        objectives=["yield", "ee", "side_product"],
        objective_mode=["max", "max", "min"],
        batch=3,
        columns_features="all",
        init_sampling_method="cvt",
    )

    import pandas as pd

    df = pd.read_csv(WORK / CSV_NAME)
    n_priority = int((df["priority"] == 1).sum())
    print(f"rows={len(df)} priority=1 count={n_priority}")
    if len(df) != 36:
        print("FAIL: expected 36-row scope", file=sys.stderr)
        return 1
    if n_priority < 1:
        print("FAIL: no priority=1 suggestions", file=sys.stderr)
        return 1
    print("SMOKE OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
