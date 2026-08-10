#!/usr/bin/env python
"""Download CHAOS four additive-plate CSVs into data/raw/chaos/additives/."""

from __future__ import annotations

import argparse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://raw.githubusercontent.com/schwallergroup/chaos/main/data/additives"
FILES = [
    "additive_rxn_screening_plate_1.csv",
    "additive_rxn_screening_plate_2.csv",
    "additive_rxn_screening_plate_3.csv",
    "additive_rxn_screening_plate_4.csv",
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "data" / "raw" / "chaos" / "additives",
    )
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        url = f"{BASE}/{name}"
        dest = args.out_dir / name
        print(f"GET {url}")
        urllib.request.urlretrieve(url, dest)
        print(f"  -> {dest} ({dest.stat().st_size} bytes)")
    print("Done. Next: python scripts/prepare_chaos.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
