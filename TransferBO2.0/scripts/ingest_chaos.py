"""Ingest CHAOS four-plate additive screen as a TransferBO2.0 library (1-D validation).

Source: Prieto Kullmer et al. Science 2022 (additive mapping); processed table
in TransferBO 1.0: data/processed/additives_four_plates.csv.

Design decisions (1-D independent validation, see docs/25):
- substrate_id  = plate_id (plate_1..4): each plate is one fixed reaction; the
  "task" is a reaction, not a substrate. 4 tasks total (small n, direction-only).
- condition_id  = additive SMILES hash: 720 additives shared across all 4 plates
  (complete cross product 2880 cells) — ONE-DIMENSIONAL condition space.
- response      = UV210 product area (bigger = better). Plates differ in scale by
  ~10x (median 34k vs 3.8k): raw pooling would let the high-scale plate dominate
  the list. Normalize WITHIN plate to z-score (keeps the ranking, removes the
  level) — this operationalizes "ranking transfers, magnitudes do not".
- plate bias_offset/bias_scale stored so plate-corrected paths can be audited.

Usage:
    python scripts/ingest_chaos.py
Output:
    data/processed/chaos_long.csv, data/db/transferbo2_chaos.db
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from rdkit import Chem
from rdkit.Chem import AllChem

from transferbo2.data.database import connect, init_schema

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT.parent / "TransferBO" / "data" / "processed" / "additives_four_plates.csv"
DB = ROOT / "data" / "db" / "transferbo2_chaos.db"
OUT_CSV = ROOT / "data" / "processed" / "chaos_long.csv"
REACTION_ID = "chaos_additive_screen"


def _cond_id(smiles: str) -> str:
    return "c_" + hashlib.md5(smiles.encode("utf-8")).hexdigest()[:10]


def _morgan(smiles: str, radius: int = 2, n_bits: int = 1024) -> list[float]:
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return [0.0] * n_bits
    fp = AllChem.GetMorganFingerprintAsBitVect(mol, radius, nBits=n_bits)
    return [float(b) for b in fp]


def main() -> int:
    raw = pd.read_csv(SRC)
    raw = raw.rename(columns={"response": "yield_raw"})
    # one reaction per plate: parse from the first reaction_smiles of the plate
    reac_by_plate = raw.groupby("plate_id")["reaction_smiles"].first()
    if not raw["plate_id"].is_unique or len(raw) != 2880:
        print("unexpected shape:", raw.shape)
    raw["condition_id"] = raw["smiles"].map(_cond_id)

    # within-plate z-score of log-ish UV area (scale-free, ranking preserved)
    def _z(g: pd.Series) -> pd.Series:
        s = np.log1p(g)  # UV areas are positive and skewed; log flattens
        return (s - s.mean()) / s.std(ddof=0)

    raw["yield"] = raw.groupby("plate_id")["yield_raw"].transform(_z)
    raw["experiment_id"] = [f"cx_{i:05d}" for i in range(len(raw))]

    if DB.exists():
        DB.unlink()
    init_schema(DB)
    conds = raw.drop_duplicates("condition_id")
    with connect(DB) as conn:
        conn.execute(
            "INSERT INTO reactions(reaction_id, name, template, description) VALUES (?,?,?,?)",
            (
                REACTION_ID,
                "CHAOS additive screen (Prieto Kullmer et al. Science 2022)",
                "additive screening",
                "4 fixed reactions x 720 shared additives (complete cross); "
                "task=plate (reaction identity); condition=additive SMILES (1-D); "
                "yield=within-plate z(log1p(UV area)) — level removed, ranking kept.",
            ),
        )
        for pid, rxn in reac_by_plate.items():
            conn.execute(
                "INSERT INTO substrates(substrate_id, reaction_id, name, smiles, smiles_elec, notes) "
                "VALUES (?,?,?,?,?,?)",
                (pid, REACTION_ID, pid, rxn, rxn, "1-D validation; task=reaction"),
            )
            vec = _morgan(rxn)
            conn.execute(
                "INSERT INTO descriptors(descriptor_id, entity_type, entity_id, name, dim, vector_json) "
                "VALUES (?,?,?,?,?,?)",
                (f"mrg_{pid}", "substrate", pid, "morgan_r2", len(vec), json.dumps(vec)),
            )
        for pid in reac_by_plate.index:
            conn.execute(
                "INSERT INTO plates(plate_id, reaction_id, notes, bias_offset, bias_scale) "
                "VALUES (?,?,?,?,?)",
                (pid, REACTION_ID, "CHAOS physical plate (batch)", 0.0, 1.0),
            )
        for _, r in conds.iterrows():
            conn.execute(
                "INSERT INTO conditions(condition_id, reaction_id, catalyst, ligand, base, solvent, "
                "condition_json, is_anchor) VALUES (?,?,?,?,?,?,?,?)",
                (r["condition_id"], REACTION_ID, r["smiles"], None, None, None,
                 json.dumps({"smiles": r["smiles"]}), 0),
            )
        for _, r in raw.iterrows():
            conn.execute(
                "INSERT INTO experiments(experiment_id, reaction_id, substrate_id, plate_id, "
                "condition_id, yield, replicate, is_anchor, quality_flag, source) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (r["experiment_id"], REACTION_ID, r["plate_id"], r["plate_id"],
                 r["condition_id"], float(r["yield"]), 1, 0,
                 f"uv_raw={r['yield_raw']:.1f}", "chaos_science2022"),
            )
        conn.commit()

    long = raw[["experiment_id", "plate_id", "condition_id", "smiles", "yield_raw", "yield"]]
    long.to_csv(OUT_CSV, index=False)
    print(f"cells: {len(raw)}  plates: {raw['plate_id'].nunique()}  "
          f"conditions: {raw['condition_id'].nunique()}  wrote {DB}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
