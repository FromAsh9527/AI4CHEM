#!/usr/bin/env python
"""Download SURF HTE CSVs from Zenodo (DOI 10.5281/zenodo.18185850).

Example:
  python scripts/download_surf.py
  python scripts/download_surf.py --files sm_all.csv bh_all.csv README.md
"""

from __future__ import annotations

import argparse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "data" / "raw" / "surf"
RECORD = "18185850"
FILES = ["sm_all.csv", "bh_all.csv", "sm_positive.csv", "bh_positive.csv", "README.md"]


def url_for(name: str) -> str:
    return f"https://zenodo.org/records/{RECORD}/files/{name}?download=1"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--files", nargs="+", default=["sm_all.csv", "bh_all.csv", "README.md"])
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    for name in args.files:
        dest = args.out / name
        print(f"Downloading {name} -> {dest}")
        urllib.request.urlretrieve(url_for(name), dest)
        print(f"  size={dest.stat().st_size}")
    print("Done. Next: python scripts/audit_external_hte.py --surf-dir", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
