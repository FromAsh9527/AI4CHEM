#!/usr/bin/env python
"""Export CHAOS additive four-plate tables into TransferBO schema.

Preferred sources (in order):
  1) data/raw/chaos/additives/additive_rxn_screening_plate_{1-4}.csv
  2) third_party/chaos/data/additives/...
  3) --chaos-root pointing at a local CHAOS checkout

Usage:
  python scripts/prepare_chaos.py
  python scripts/prepare_chaos.py --chaos-root path/to/chaos --out data/processed/additives_four_plates.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from transferbo.data.clean import clean_smiles, deduplicate_plate  # noqa: E402
from transferbo.utils.io import ensure_dir  # noqa: E402

PLATE_FILES = {
    "plate_1": "additive_rxn_screening_plate_1.csv",
    "plate_2": "additive_rxn_screening_plate_2.csv",
    "plate_3": "additive_rxn_screening_plate_3.csv",
    "plate_4": "additive_rxn_screening_plate_4.csv",
}


def _find_plate_dir(chaos_root: Path | None) -> Path:
    candidates = [
        ROOT / "data" / "raw" / "chaos" / "additives",
        ROOT / "third_party" / "chaos" / "data" / "additives",
    ]
    if chaos_root is not None:
        candidates.insert(0, Path(chaos_root) / "data" / "additives")
    for c in candidates:
        if all((c / name).exists() for name in PLATE_FILES.values()):
            return c
    tried = "\n  ".join(str(c) for c in candidates)
    raise FileNotFoundError(
        "Could not find CHAOS plate CSVs. Tried:\n  "
        + tried
        + "\n\nDownload with:\n"
        "  python scripts/download_chaos_plates.py\n"
        "or clone https://github.com/schwallergroup/chaos into third_party/chaos"
    )


def _pick_col(df: pd.DataFrame, options: list[str]) -> str | None:
    lower = {c.lower().strip(): c for c in df.columns}
    for opt in options:
        if opt.lower() in lower:
            return lower[opt.lower()]
    return None


def load_one_plate(path: Path, plate_id: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    smiles_col = _pick_col(
        df,
        [
            "additives",  # CHAOS plate files
            "smiles",
            "additive_smiles",
            "Additive_Smiles",
            "canonical_smiles",
            "smi",
        ],
    )
    resp_col = _pick_col(
        df,
        [
            "objective",  # CHAOS plate files (UV210 product area)
            "UV210_Product Area Abs.",
            "uv210",
            "UV210",
            "product_area",
            "Product Area",
            "response",
            "yield",
            "area",
        ],
    )
    id_col = _pick_col(df, ["additive", "additive_id", "Additive", "name", "id"])
    rxn_col = _pick_col(df, ["rxn", "reaction_smiles", "reaction"])

    if smiles_col is None:
        raise ValueError(f"{path.name}: cannot find SMILES column in {list(df.columns)}")
    if resp_col is None:
        raise ValueError(f"{path.name}: cannot find response column in {list(df.columns)}")

    out = pd.DataFrame(
        {
            "additive_id": df[id_col].astype(str) if id_col else [f"{plate_id}_{i}" for i in range(len(df))],
            "smiles": df[smiles_col].astype(str),
            "plate_id": plate_id,
            "response": pd.to_numeric(df[resp_col], errors="coerce"),
        }
    )
    if rxn_col is not None:
        out["reaction_smiles"] = df[rxn_col].astype(str)
    return out.dropna(subset=["response"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare CHAOS four-plate CSV")
    parser.add_argument("--chaos-root", type=Path, default=None)
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "data" / "processed" / "additives_four_plates.csv",
    )
    parser.add_argument("--data-card", type=Path, default=ROOT / "results" / "meta" / "data_card.md")
    args = parser.parse_args(argv)

    plate_dir = _find_plate_dir(args.chaos_root)
    frames = []
    for plate_id, fname in PLATE_FILES.items():
        part = load_one_plate(plate_dir / fname, plate_id)
        print(f"[load] {fname}: {len(part)} rows -> {plate_id}")
        frames.append(part)

    df = pd.concat(frames, ignore_index=True)
    df["smiles"] = df["smiles"].map(clean_smiles)
    before = len(df)
    df = df.dropna(subset=["smiles", "response"])
    df = deduplicate_plate(df)
    print(f"[clean] {before} -> {len(df)} rows after SMILES clean/dedup")

    ensure_dir(args.out.parent)
    df.to_csv(args.out, index=False)
    print(f"Wrote {args.out}")

    # data card
    ensure_dir(args.data_card.parent)
    lines = [
        "# Data card — additives four plates (CHAOS / Prieto Kullmer)",
        "",
        f"- source_dir: `{plate_dir}`",
        f"- processed: `{args.out}`",
        f"- n_rows: {len(df)}",
        f"- plates: {sorted(df['plate_id'].unique())}",
        "",
        "| plate_id | n | min | median | max | top5% thr |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for pid, g in df.groupby("plate_id"):
        y = g["response"]
        thr = y.quantile(0.95)
        lines.append(
            f"| {pid} | {len(g)} | {y.min():.4g} | {y.median():.4g} | {y.max():.4g} | {thr:.4g} |"
        )
    lines.append("")
    args.data_card.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {args.data_card}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
