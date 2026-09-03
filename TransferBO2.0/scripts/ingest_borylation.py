"""Ingest Ni-catalyzed borylation dataset into TransferBO2.0 (P4 primary holdout).

Source (two mirrors, identical, cross-checked 1518/1518, yield diff = 0):
  - "Active Learning High Coverage Sets of Complementary Reaction Conditions"
    (Digital Discovery 2025) real_datasets/borylation.csv
  - Doyle lab ochem-data NiB/rxns/inchi_23l.csv (used here: includes InChI structures)
  Original paper: "Advancing Base Metal Catalysis through Data Science: Insight and
  Predictive Models for Ni-Catalyzed Borylation through Supervised Machine Learning"
  (Organometallics 2022, 10.1021/acs.organomet.2c00089).

Semantics (pre-registered, docs/18):
  - substrate_id  : electrophile_id (s1..s33); structure from electrophile_inchi
  - condition_id  : ligand_name | solvent_name  (23 ligands x 2 solvents = 46)
  - yield         : percent yield (0-100, single measurement, 1518 = 33x23x2 full grid)
  - plate_id      : logical_{electrophile_id} (no real batch metadata in source;
                    NOT a batch track)
  - descriptors   : morgan_r2 (1024-bit, radius 2) from electrophile SMILES

Usage:
    python scripts/ingest_borylation.py
Output:
    data/processed/borylation_long.csv, data/db/transferbo2_borylation.db
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from rdkit import Chem
from rdkit.Chem import AllChem

from transferbo2.data.database import connect, init_schema

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "raw" / "cso_datasets" / "inchi_23l.csv"
DB = ROOT / "data" / "db" / "transferbo2_borylation.db"
OUT_CSV = ROOT / "data" / "processed" / "borylation_long.csv"
REACTION_ID = "nib_borylation"


def _morgan(smiles: str, radius: int = 2, n_bits: int = 1024) -> list[float]:
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return [0.0] * n_bits
    fp = AllChem.GetMorganFingerprintAsBitVect(mol, radius, nBits=n_bits)
    return [float(b) for b in fp]


def main() -> None:
    raw = pd.read_csv(SRC)
    raw["electrophile_smiles"] = raw["electrophile_inchi"].map(
        lambda i: Chem.MolToSmiles(Chem.MolFromInchi(i)) if Chem.MolFromInchi(i) else ""
    )
    raw["condition_id"] = (
        raw["ligand_name"].astype(str).str.strip() + "|" + raw["solvent_name"].astype(str).str.strip()
    )
    raw["plate_id"] = raw["electrophile_id"].map(lambda s: f"logical_{s}")
    long = pd.DataFrame(
        {
            "reaction_id": REACTION_ID,
            "experiment_id": [f"nib_{i:05d}" for i in range(len(raw))],
            "substrate_id": raw["electrophile_id"].astype(str),
            "substrate_smiles": raw["electrophile_smiles"],
            "plate_id": raw["plate_id"],
            "condition_id": raw["condition_id"],
            "ligand": raw["ligand_name"].astype(str),
            "solvent": raw["solvent_name"].astype(str),
            "yield": raw["yield"].astype(float),
            "is_anchor": 0,
            "source": "organometallics2022_borylation",
            "quality_flag": "ok",
            "replicate": 1,
        }
    )
    long.to_csv(OUT_CSV, index=False)

    if DB.exists():
        DB.unlink()
    init_schema(DB)
    with connect(DB) as conn:
        conn.execute(
            "INSERT INTO reactions(reaction_id, name, template, description) VALUES (?,?,?,?)",
            (
                REACTION_ID,
                "Ni-catalyzed borylation (Organometallics 2022 / Doyle ochem-data)",
                "Ni-catalyzed C-B borylation",
                "P4 primary holdout; 33 electrophiles x 23 ligands x 2 solvents full grid "
                "(1518, single measurement); plate_id is LOGICAL (no batch metadata).",
            ),
        )
        for sid, g in long.groupby("substrate_id"):
            smi = g["substrate_smiles"].iloc[0]
            conn.execute(
                "INSERT INTO substrates(substrate_id, reaction_id, name, smiles, smiles_elec, notes) "
                "VALUES (?,?,?,?,?,?)",
                (sid, REACTION_ID, sid, smi, smi, "p4_holdout_primary"),
            )
            vec = _morgan(smi)
            conn.execute(
                "INSERT INTO descriptors(descriptor_id, entity_type, entity_id, name, dim, vector_json) "
                "VALUES (?,?,?,?,?,?)",
                (f"mrg_{sid}", "substrate", sid, "morgan_r2", len(vec), json.dumps(vec)),
            )
        for pid in sorted(long["plate_id"].unique()):
            conn.execute(
                "INSERT INTO plates(plate_id, reaction_id, notes, bias_offset, bias_scale) "
                "VALUES (?,?,?,?,?)",
                (pid, REACTION_ID, "LOGICAL plate (=electrophile task); no batch metadata in source",
                 0.0, 1.0),
            )
        for cid, g in long.groupby("condition_id"):
            conn.execute(
                "INSERT INTO conditions(condition_id, reaction_id, catalyst, ligand, base, solvent, "
                "condition_json, is_anchor) VALUES (?,?,?,?,?,?,?,?)",
                (
                    cid, REACTION_ID, None,
                    g["ligand"].iloc[0], None, g["solvent"].iloc[0],
                    json.dumps({"ligand_name": g["ligand"].iloc[0],
                                "solvent_name": g["solvent"].iloc[0]}),
                    0,
                ),
            )
        for _, r in long.iterrows():
            conn.execute(
                "INSERT INTO experiments(experiment_id, reaction_id, substrate_id, plate_id, "
                "condition_id, yield, replicate, is_anchor, quality_flag, source) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (r["experiment_id"], REACTION_ID, r["substrate_id"], r["plate_id"],
                 r["condition_id"], float(r["yield"]), 1, 0, "ok", "organometallics2022_borylation"),
            )
        conn.commit()

    print(f"rows: {len(long)}  tasks: {long['substrate_id'].nunique()}  "
          f"conditions: {long['condition_id'].nunique()}  plates(logical): {long['plate_id'].nunique()}")
    print(f"yield: mean={long['yield'].mean():.1f} med={long['yield'].median():.1f} "
          f"fail(<=1)={ (long['yield']<=1).mean():.3f}")
    print(f"wrote {OUT_CSV} / {DB}")


if __name__ == "__main__":
    main()
