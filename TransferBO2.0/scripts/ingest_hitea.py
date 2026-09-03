"""Ingest Pfizer HiTEA Suzuki subset into TransferBO2.0 long-table + SQLite (P4 holdout).

Pre-registered semantics (docs/18_p4_hitea_holdout.md §2, audit results/p4_hitea/audit.md):

- substrate_id  : task_id (hit_01..) derived from canonical Reactant_1 SMILES
                  (aryl halide OR boronate as encoded in the source; r2 partner
                  varies within cell). SMILES kept in substrates.smiles.
- plate_id      : SCREEN_ID from the source = REAL screen/batch metadata.
                  NOTE: this is the FIRST true batch track in TransferBO2.0
                  (multiple tasks share a screen; real batch, not logical plate).
- condition_id  : stable hash of (Catalyst_2_ID_1_SMILES | Solvent_1_Name);
                  Catalyst_2 is the real catalyst/ligand system (Catalyst_1 is
                  Pd(OAc)2 in 99.7% of rows). Raw string kept in conditions.
- yield         : mean Product_Yield_PCT_Area_UV over the cell (partner/T/time/
                  Catalyst_1/replicates). Per-reaction detail preserved in
                  data/processed/hitea_raw_long.csv for noise SI.
- descriptors   : morgan_r2 (RDKit) for substrates; nearest uses Tanimoto.

Usage:
    python scripts/ingest_hitea.py
Output:
    data/processed/hitea_long.csv, data/processed/hitea_raw_long.csv,
    data/db/transferbo2_hitea.db
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
SRC = ROOT / "data" / "raw" / "hitea" / "8_SEPT_APPROVED_full_dataset.csv"
DB = ROOT / "data" / "db" / "transferbo2_hitea.db"
OUT_CSV = ROOT / "data" / "processed" / "hitea_long.csv"
OUT_RAW = ROOT / "data" / "processed" / "hitea_raw_long.csv"
REACTION_ID = "hitea_suzuki"
ROSTER = ROOT / "results" / "p4_hitea" / "audit_task_roster.csv"


def _cond_id(cond_str: str) -> str:
    return "c_" + hashlib.md5(cond_str.encode("utf-8")).hexdigest()[:10]


def _morgan(smiles: str, radius: int = 2, n_bits: int = 1024) -> list[float]:
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return [0.0] * n_bits
    fp = AllChem.GetMorganFingerprintAsBitVect(mol, radius, nBits=n_bits)
    return [float(b) for b in fp]


def main() -> None:
    roster = pd.read_csv(ROSTER)
    task_map = dict(zip(roster["reactant1_smiles"], roster["task_id"]))

    raw = pd.read_csv(SRC, low_memory=False)
    raw = raw[raw["KeyWord_STD"] == "SUZUKI"].copy()
    raw["r1"] = raw["Reactant_1_SMILES"].astype(str).str.strip()
    raw = raw[raw["r1"].isin(task_map)].copy()
    raw["task_id"] = raw["r1"].map(task_map)
    raw["cond_str"] = (
        raw["catalyst_2_ID_1_SMILES"].fillna("").astype(str)
        + "|"
        + raw["Solvent_1_Name"].fillna("").astype(str)
    )
    raw["condition_id"] = raw["cond_str"].map(_cond_id)
    raw["yield"] = pd.to_numeric(raw["Product_Yield_PCT_Area_UV"], errors="coerce")
    raw = raw.dropna(subset=["yield"])
    raw["screen"] = raw["SCREEN_ID"].astype(str)
    raw["plate_id"] = raw["screen"].map(lambda s: f"screen_{s}")

    # per-reaction long table (for noise SI / audit)
    raw_out = pd.DataFrame(
        {
            "reaction_id": raw["REACTION_ID"].astype(str),
            "task_id": raw["task_id"],
            "substrate_smiles": raw["r1"],
            "plate_id": raw["plate_id"],
            "screen_id": raw["screen"],
            "condition_id": raw["condition_id"],
            "cond_str": raw["cond_str"],
            "catalyst": raw["Catalyst_1_Short_Hand"].fillna("").astype(str),
            "catalyst_2": raw["Catalyst_2_Short_Hand"].fillna("").astype(str),
            "solvent": raw["Solvent_1_Name"].fillna("").astype(str),
            "temp_c": raw["Reaction_T"],
            "time_h": raw["Reaction_Time_hrs"],
            "yield": raw["yield"],
            "partner_smiles": raw["reactant_2_SMILES"].fillna("").astype(str),
        }
    )
    raw_out.to_csv(OUT_RAW, index=False)

    # cell-level long table (oracle)
    cells = (
        raw.groupby(["task_id", "condition_id", "plate_id"], as_index=False)
        .agg(yield_mean=("yield", "mean"), n=("yield", "size"))
        .rename(columns={"yield_mean": "yield"})
    )
    long = cells.copy()
    long["experiment_id"] = [f"hit_{i:06d}" for i in range(len(long))]
    long.to_csv(OUT_CSV, index=False)

    # --- SQLite ---
    if DB.exists():
        DB.unlink()
    init_schema(DB)
    cond_strs = raw.drop_duplicates("condition_id").set_index("condition_id")["cond_str"]
    smi_by_task = raw.drop_duplicates("task_id").set_index("task_id")["r1"]

    # Condition-level factor values: Catalyst_2 short hand / Solvent name / T are
    # NOT constant within a (catalyst|solvent) condition in the source (T varies
    # across replicate cells), so store the MODE per condition. OHE of these
    # columns is what gives the GP a non-degenerate condition encoding.
    cond_factors = (
        raw.groupby("condition_id")
        .agg(
            catalyst=("Catalyst_2_Short_Hand", lambda s: s.mode().iloc[0] if len(s.mode()) else ""),
            solvent=("Solvent_1_Name", lambda s: s.mode().iloc[0] if len(s.mode()) else ""),
            temperature_c=("Reaction_T", lambda s: s.mode().iloc[0] if len(s.mode()) else None),
            time_h=("Reaction_Time_hrs", lambda s: s.mode().iloc[0] if len(s.mode()) else None),
        )
        .reset_index()
    )

    with connect(DB) as conn:
        conn.execute(
            "INSERT INTO reactions(reaction_id, name, template, description) VALUES (?,?,?,?)",
            (
                REACTION_ID,
                "Pfizer HiTEA Suzuki subset (P4 external holdout)",
                "Suzuki-Miyaura",
                "Independent-source Suzuki data; task=Reactant_1 identity; "
                "plate_id=SCREEN_ID (REAL batch metadata, first true batch track); "
                "condition=(Catalyst_2|Solvent); yield=cell mean of UV area %%.",
            ),
        )
        for tid, smi in smi_by_task.items():
            conn.execute(
                "INSERT INTO substrates(substrate_id, reaction_id, name, smiles, smiles_elec, notes) "
                "VALUES (?,?,?,?,?,?)",
                (tid, REACTION_ID, tid, smi, smi, "p4_holdout; r1=halide_or_boronate"),
            )
            vec = _morgan(smi)
            conn.execute(
                "INSERT INTO descriptors(descriptor_id, entity_type, entity_id, name, dim, vector_json) "
                "VALUES (?,?,?,?,?,?)",
                (f"mrg_{tid}", "substrate", tid, "morgan_r2", len(vec), json.dumps(vec)),
            )
        for pid in sorted(long["plate_id"].unique()):
            conn.execute(
                "INSERT INTO plates(plate_id, reaction_id, notes, bias_offset, bias_scale) "
                "VALUES (?,?,?,?,?)",
                (pid, REACTION_ID, "REAL screen/batch from HiTEA (first true batch track)", 0.0, 1.0),
            )
        for cid, cstr in cond_strs.items():
            fac = cond_factors.loc[cond_factors["condition_id"] == cid]
            if len(fac):
                cat = fac["catalyst"].iloc[0]
                sol = fac["solvent"].iloc[0]
                temp = fac["temperature_c"].iloc[0]
                th = fac["time_h"].iloc[0]
            else:
                cat = sol = None
                temp = th = None
            conn.execute(
                "INSERT INTO conditions(condition_id, reaction_id, catalyst, ligand, base, solvent, "
                "temperature_c, time_h, condition_json, is_anchor) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    cid,
                    REACTION_ID,
                    cat,
                    None,
                    None,
                    sol,
                    temp,
                    th,
                    json.dumps({"cond_str": cstr}),
                    0,
                ),
            )
        for _, r in long.iterrows():
            conn.execute(
                "INSERT INTO experiments(experiment_id, reaction_id, substrate_id, plate_id, "
                "condition_id, yield, replicate, is_anchor, quality_flag, source) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    r["experiment_id"],
                    REACTION_ID,
                    r["task_id"],
                    r["plate_id"],
                    r["condition_id"],
                    float(r["yield"]),
                    1,
                    0,
                    f"mean_of_{int(r['n'])}",
                    "hitea_suzuki",
                ),
            )
        conn.commit()

    print(f"raw reactions kept: {len(raw_out)}  (source rows: {len(raw)})")
    print(f"cells (task x condition x screen): {len(long)}")
    print(f"tasks: {long['task_id'].nunique()}  conditions: {long['condition_id'].nunique()}  "
          f"screens: {long['plate_id'].nunique()}")
    print(f"wrote {OUT_CSV} / {OUT_RAW} / {DB}")


if __name__ == "__main__":
    main()
