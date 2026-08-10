#!/usr/bin/env python
"""Prepare Doyle Ahneman BH HTE as shared-candidate multi-plate table.

Source: doyle-lab-ucla/ochem-data deebo/cn-processed.csv
Task = aryl halide substrate; Candidate = (ligand, base, additive) combo.

Output columns aligned with TransferBO plates:
  plate_id, smiles, response, additive_id, reaction_smiles, candidate_key, ...

Example:
  python scripts/prepare_doyle_cn.py
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def cand_id(ligand: str, base: str, additive: str) -> str:
    raw = f"{ligand}||{base}||{additive}"
    return "C_" + hashlib.md5(raw.encode()).hexdigest()[:12]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--raw",
        type=Path,
        default=ROOT / "data/raw/external/cn-processed.csv",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=ROOT / "data/processed/doyle_cn_plates.csv",
    )
    args = ap.parse_args()

    df = pd.read_csv(args.raw)
    rows = []
    for _, r in df.iterrows():
        cid = cand_id(r["ligand_smiles"], r["base_smiles"], r["additive_smiles"])
        # plate = substrate; keep stable plate names
        sid = str(r.get("substrate_id", ""))
        if sid and sid != "nan":
            plate = f"sub_{sid}"
        else:
            plate = "sub_" + hashlib.md5(str(r["substrate_smiles"]).encode()).hexdigest()[:8]
        # Use stable candidate_key as the encoding string (OHE-friendly).
        # Additive SMILES may be the literal "none" and is not RDKit-safe alone.
        add = str(r["additive_smiles"])
        key = f"{r['ligand_smiles']}||{r['base_smiles']}||{add}"
        rxn = ".".join(
            [
                str(r["substrate_smiles"]),
                str(r["ligand_smiles"]),
                str(r["base_smiles"]),
                add if add.lower() != "none" else "",
            ]
        ).strip(".")
        rows.append(
            {
                "plate_id": plate,
                "smiles": key,  # identity string for OHE; not always RDKit-valid
                "response": float(r["yield"]),
                "additive_id": cid,
                "reaction_smiles": rxn,
                "candidate_key": key,
                "ligand_smiles": r["ligand_smiles"],
                "base_smiles": r["base_smiles"],
                "additive_smiles": add,
                "substrate_smiles": r["substrate_smiles"],
                "ligand_name": r.get("ligand_name"),
                "base_name": r.get("base_name"),
                "source_dataset": "doyle_ahneman_cn_processed",
            }
        )
    out = pd.DataFrame(rows)
    # sanity: each plate same candidate set
    plates = out["plate_id"].unique()
    sets = [set(out[out.plate_id == p]["additive_id"]) for p in plates]
    inter = set.intersection(*sets)
    assert len(inter) == out["additive_id"].nunique(), "candidate sets not identical across plates"
    assert out.groupby("plate_id").size().nunique() == 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.out, index=False)
    print(f"Wrote {args.out}")
    print(f"plates={out.plate_id.nunique()} cands={out.additive_id.nunique()} rows={len(out)}")
    print(out.groupby("plate_id").size().describe())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
