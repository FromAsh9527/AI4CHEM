#!/usr/bin/env python
"""Prepare four-plate additive HTE data into a unified CSV.

Expected output columns:
  additive_id, smiles, plate_id, response

Data sources (plan §4):
  - Prieto Kullmer et al., Science (DOI: 10.1126/science.abn1885)
  - CHAOS repo helpers: https://github.com/schwallergroup/chaos

Usage:
  python scripts/prepare_data.py --raw data/raw --out data/processed/additives_four_plates.csv
  python scripts/prepare_data.py --demo   # synthetic 4-plate toy data for pipeline smoke tests
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from transferbo.data.clean import clean_smiles, deduplicate_plate  # noqa: E402
from transferbo.utils.io import ensure_dir  # noqa: E402


def _find_candidate_tables(raw_dir: Path) -> list[Path]:
    patterns = ("*.csv", "*.tsv", "*.xlsx")
    files: list[Path] = []
    for pat in patterns:
        files.extend(raw_dir.rglob(pat))
    return sorted(files)


def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    colmap = {c.lower().strip(): c for c in df.columns}
    aliases = {
        "smiles": ["smiles", "additive_smiles", "canonical_smiles", "smi"],
        "response": [
            "response",
            "uv210",
            "product_area",
            "area",
            "yield",
            "norm_response",
            "normalized_response",
        ],
        "plate_id": ["plate_id", "plate", "plate_name", "assay", "reaction_plate"],
        "additive_id": ["additive_id", "additive", "id", "name", "ligand", "additive_name"],
    }
    rename = {}
    for canon, cands in aliases.items():
        for a in cands:
            if a in colmap:
                rename[colmap[a]] = canon
                break
    return df.rename(columns=rename)


def load_raw_tables(raw_dir: Path) -> pd.DataFrame:
    files = _find_candidate_tables(raw_dir)
    if not files:
        raise FileNotFoundError(
            f"No CSV/TSV/XLSX under {raw_dir}. See data/README.md for download steps."
        )

    frames = []
    for path in files:
        if path.suffix.lower() == ".xlsx":
            df = pd.read_excel(path)
        elif path.suffix.lower() == ".tsv":
            df = pd.read_csv(path, sep="\t")
        else:
            df = pd.read_csv(path)
        df = _normalise_columns(df)
        if "plate_id" not in df.columns:
            df["plate_id"] = path.stem
        frames.append(df)

    out = pd.concat(frames, ignore_index=True)
    missing = [c for c in ("smiles", "response") if c not in out.columns]
    if missing:
        raise ValueError(
            f"Could not map columns {missing} from raw files. "
            f"Found columns: {list(out.columns)}"
        )
    if "additive_id" not in out.columns:
        out["additive_id"] = out["smiles"].astype(str)
    return out[["additive_id", "smiles", "plate_id", "response"]]


def make_demo_plates(n_per_plate: int = 120, n_plates: int = 4, seed: int = 0) -> pd.DataFrame:
    """Synthetic multi-plate data so the BO pipeline can be tested without downloads."""
    rng = np.random.default_rng(seed)
    # Generate distinct simple SMILES-like alcohols / aromatics via carbon chain length
    base_templates = [
        "C" * k + "O" for k in range(1, 31)
    ] + [
        "c1ccccc1",
        "c1ccccc1O",
        "c1ccccc1N",
        "c1ccccc1Cl",
        "c1ccccc1F",
        "c1ccccc1Br",
        "c1ccncc1",
        "c1ccncc1O",
        "CCOC(=O)C",
        "CC(=O)O",
        "CC(=O)N",
        "CCN",
        "CCN(CC)CC",
        "CCS",
        "CC#N",
        "C1CCCCC1",
        "C1CCCCC1O",
        "CC(C)O",
        "CC(C)(C)O",
        "c1ccc2ccccc2c1",
    ]
    # Ensure uniqueness after RDKit canonicalisation by appending distinct alkyl patterns
    extras = []
    for i in range(200):
        extras.append("C" * ((i % 12) + 1) + ("N" if i % 2 == 0 else "O"))
    pool = list(dict.fromkeys(base_templates + extras))  # preserve order, unique strings

    rows = []
    for p in range(1, n_plates + 1):
        smiles_list = [pool[i % len(pool)] for i in range(n_per_plate)]
        # Shared latent preference + plate-specific shift → partial transferability
        for i, smi in enumerate(smiles_list):
            latent = (hash(smi) % 1000) / 1000.0
            plate_shift = 0.15 * np.sin(p + i / 5.0)
            noise = rng.normal(0, 0.05)
            y = float(np.clip(0.6 * latent + 0.4 * ((i % 17) / 17.0) + plate_shift + noise, 0, 1))
            rows.append(
                {
                    "additive_id": f"A{i:03d}",
                    "smiles": smi,
                    "plate_id": f"plate_{p}",
                    "response": y,
                }
            )
    return pd.DataFrame(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare TransferBO plate tables")
    parser.add_argument("--raw", type=Path, default=ROOT / "data" / "raw")
    parser.add_argument(
        "--out", type=Path, default=ROOT / "data" / "processed" / "additives_four_plates.csv"
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Write synthetic 4-plate demo data (no external download)",
    )
    args = parser.parse_args(argv)

    if args.demo:
        df = make_demo_plates()
        print(f"[demo] generated {len(df)} rows across {df['plate_id'].nunique()} plates")
    else:
        df = load_raw_tables(args.raw)
        print(f"[raw] loaded {len(df)} rows from {args.raw}")

    df["smiles"] = df["smiles"].map(clean_smiles)
    df = df.dropna(subset=["smiles", "response"]).copy()
    df = deduplicate_plate(df)
    df["plate_id"] = df["plate_id"].astype(str)

    ensure_dir(args.out.parent)
    df.to_csv(args.out, index=False)
    print(f"Wrote {args.out}  ({len(df)} rows, plates={sorted(df['plate_id'].unique())})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
