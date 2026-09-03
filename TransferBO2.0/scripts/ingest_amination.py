"""Ingest Doyle/EDBO aryl amination plates into TransferBO2.0 long-table + SQLite.

Semantic contract (IMPORTANT — do not conflate with CHAOS true plates):

- substrate_id  : chemical aryl halide identity (from substrate_smiles)
- plate_id      : logical campaign / task id from the source table
                  For this library, plate_id == one-substrate-one-logical-plate
                  (perfectly aligned with substrate). It is NOT an independent
                  batch-effect factor. Real batch effects belong on the SURF track.
- condition_id  : ligand × base × additive combination (candidate_key)
- yield         : response (percent-scale)

Default source:
  ../TransferBO/data/processed/edbo_amination_plates.csv
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from transferbo2.data.database import DEFAULT_DB, PACKAGE_ROOT, connect, init_schema

DEFAULT_SRC = (
    PACKAGE_ROOT.parent / "TransferBO" / "data" / "processed" / "edbo_amination_plates.csv"
)
REACTION_ID = "edbo_aryl_amination"


def _stable_id(prefix: str, text: str) -> str:
    h = hashlib.md5(text.encode("utf-8")).hexdigest()[:10]
    return f"{prefix}_{h}"


def _smiles_fingerprint(smiles: str, dim: int = 32) -> list[float]:
    """Cheap deterministic descriptor without requiring RDKit.

    Uses hashed character n-grams. Good enough for similarity gating demos;
    replace with Morgan/DFT later via descriptors table overwrite.
    """
    s = (smiles or "").strip()
    vec = np.zeros(dim, dtype=float)
    if not s:
        return vec.tolist()
    for n in (2, 3):
        for i in range(max(0, len(s) - n + 1)):
            gram = s[i : i + n]
            idx = int(hashlib.md5(gram.encode()).hexdigest(), 16) % dim
            vec[idx] += 1.0
    nrm = np.linalg.norm(vec)
    if nrm > 0:
        vec = vec / nrm
    return vec.tolist()


def load_amination_long(src: Path) -> pd.DataFrame:
    df = pd.read_csv(src)
    required = [
        "plate_id",
        "substrate_smiles",
        "ligand_smiles",
        "base_smiles",
        "additive_smiles",
        "response",
        "candidate_key",
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"{src} missing columns: {missing}")

    out = pd.DataFrame(
        {
            "reaction_id": REACTION_ID,
            # Keep human-readable task ids (sub_s1…) as substrate_id for continuity
            # with TransferBO frozen analyses (e.g. s4).
            "substrate_id": df["plate_id"].astype(str),
            "substrate_smiles": df["substrate_smiles"].astype(str),
            # Logical plate == substrate task in this library (documented confound).
            "plate_id": df["plate_id"].astype(str).map(lambda s: f"logical_{s}"),
            "condition_id": df["candidate_key"].astype(str),
            "catalyst": None,
            "ligand": df["ligand_smiles"].astype(str),
            "base": df["base_smiles"].astype(str),
            "solvent": None,
            "temperature_c": None,
            "time_h": None,
            "equiv": None,
            "yield": df["response"].astype(float),
            "is_anchor": 0,
            "source": df["source_dataset"].astype(str)
            if "source_dataset" in df.columns
            else "edbo_amination",
            "quality_flag": "ok",
            "replicate": 1,
            "reaction_smiles": df["reaction_smiles"].astype(str)
            if "reaction_smiles" in df.columns
            else "",
        }
    )
    # Drop exact duplicate condition rows within a substrate if any
    out = out.drop_duplicates(subset=["substrate_id", "condition_id", "replicate"], keep="first")
    out["experiment_id"] = [
        f"amin_{i:05d}" for i in range(len(out))
    ]
    return out.reset_index(drop=True)


def write_csv(df: pd.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return path


def ingest_to_db(df: pd.DataFrame, db_path: Path, *, replace_reaction: bool = True) -> Path:
    init_schema(db_path)
    with connect(db_path) as conn:
        if replace_reaction:
            # Remove only this reaction's rows so demo/other libs can coexist if needed
            for table in ("experiments", "anchors", "conditions", "plates", "substrates"):
                try:
                    conn.execute(
                        f"DELETE FROM {table} WHERE reaction_id = ?",
                        (REACTION_ID,),
                    )
                except Exception:
                    pass
            conn.execute("DELETE FROM reactions WHERE reaction_id = ?", (REACTION_ID,))
            conn.execute(
                "DELETE FROM descriptors WHERE entity_id LIKE 'sub_s%' OR entity_id IN "
                "(SELECT substrate_id FROM substrates WHERE reaction_id = ?)",
                (REACTION_ID,),
            )

        conn.execute(
            """INSERT OR REPLACE INTO reactions(reaction_id, name, template, description)
               VALUES (?,?,?,?)""",
            (
                REACTION_ID,
                "EDBO aryl amination (Doyle/Ahneman-style)",
                "Buchwald-Hartwig",
                "Primary TransferBO2.0 library. plate_id is logical one-substrate-one-plate "
                "(NOT independent batch). Use SURF track for real date/batch effects.",
            ),
        )

        for sid, g in df.groupby("substrate_id"):
            smiles = g["substrate_smiles"].iloc[0]
            conn.execute(
                """INSERT OR REPLACE INTO substrates(
                    substrate_id, reaction_id, name, smiles, smiles_elec, notes
                   ) VALUES (?,?,?,?,?,?)""",
                (
                    sid,
                    REACTION_ID,
                    sid,
                    smiles,
                    smiles,
                    "logical_plate_aligned=1; primary_track=substrate_transfer",
                ),
            )

        for pid, g in df.groupby("plate_id"):
            conn.execute(
                """INSERT OR REPLACE INTO plates(
                    plate_id, reaction_id, notes, bias_offset, bias_scale
                   ) VALUES (?,?,?,?,?)""",
                (
                    pid,
                    REACTION_ID,
                    "LOGICAL plate (=substrate task). Not a physical batch plate.",
                    0.0,
                    1.0,
                ),
            )

        for cid, g in df.groupby("condition_id"):
            row = g.iloc[0]
            payload = {
                "ligand": row["ligand"],
                "base": row["base"],
                "additive_as_ligand_slot": False,
            }
            # additive is stored in source as separate col; encode into condition_json
            # Recover additive from original uniqueness: ligand||base may collide; keep cid
            conn.execute(
                """INSERT OR REPLACE INTO conditions(
                    condition_id, reaction_id, catalyst, ligand, base, solvent,
                    temperature_c, time_h, equiv, condition_json, is_anchor
                   ) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    cid,
                    REACTION_ID,
                    None,
                    row["ligand"],
                    row["base"],
                    None,
                    None,
                    None,
                    None,
                    json.dumps({"condition_id": cid, **payload}),
                    0,
                ),
            )

        # Prefer storing additive into condition_json by joining unique rows
        # Re-read additive from long df via a side map if present in CSV export —
        # long table currently folds additive into condition_id only. Enrich from src columns
        # by re-loading ligand/base from df — additive not in long df. Fix: add additive col.
        for _, r in df.iterrows():
            conn.execute(
                """INSERT OR REPLACE INTO experiments(
                    experiment_id, reaction_id, substrate_id, plate_id, condition_id,
                    yield, replicate, is_anchor, quality_flag, source
                   ) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    r["experiment_id"],
                    REACTION_ID,
                    r["substrate_id"],
                    r["plate_id"],
                    r["condition_id"],
                    float(r["yield"]),
                    int(r["replicate"]),
                    0,
                    "ok",
                    str(r["source"]),
                ),
            )

        # Substrate descriptors
        for sid, g in df.groupby("substrate_id"):
            smiles = g["substrate_smiles"].iloc[0]
            vec = _smiles_fingerprint(smiles, dim=32)
            conn.execute(
                """INSERT OR REPLACE INTO descriptors(
                    descriptor_id, entity_type, entity_id, name, dim, vector_json
                   ) VALUES (?,?,?,?,?,?)""",
                (f"fp_{sid}", "substrate", sid, "hashed_smiles_v1", len(vec), json.dumps(vec)),
            )

        conn.commit()
    return db_path


def main() -> None:
    p = argparse.ArgumentParser(description="Ingest EDBO aryl amination into TransferBO2.0")
    p.add_argument("--src", type=Path, default=DEFAULT_SRC)
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    p.add_argument(
        "--out-csv",
        type=Path,
        default=PACKAGE_ROOT / "data" / "processed" / "amination_long.csv",
    )
    p.add_argument("--keep-demo", action="store_true", help="Do not wipe demo reaction rows")
    args = p.parse_args()

    if not args.src.exists():
        raise SystemExit(f"Source not found: {args.src}")

    df = load_amination_long(args.src)
    # Attach additive for condition enrichment
    raw = pd.read_csv(args.src)
    add_map = raw.drop_duplicates("candidate_key").set_index("candidate_key")["additive_smiles"]
    df["additive"] = df["condition_id"].map(add_map)

    csv_path = write_csv(df, args.out_csv)

    if not args.keep_demo:
        # Fresh DB focused on primary library
        if args.db.exists():
            args.db.unlink()
        init_schema(args.db)

    # Patch ingest to store additive in condition_json
    init_schema(args.db)
    with connect(args.db) as conn:
        conn.execute("DELETE FROM experiments")
        conn.execute("DELETE FROM anchors")
        conn.execute("DELETE FROM descriptors")
        conn.execute("DELETE FROM conditions")
        conn.execute("DELETE FROM plates")
        conn.execute("DELETE FROM substrates")
        conn.execute("DELETE FROM reactions")
        conn.execute(
            """INSERT INTO reactions(reaction_id, name, template, description)
               VALUES (?,?,?,?)""",
            (
                REACTION_ID,
                "EDBO aryl amination (Doyle/Ahneman-style)",
                "Buchwald-Hartwig",
                "PRIMARY library for TransferBO2.0. "
                "plate_id=logical_{substrate_id} (one-substrate-one-logical-plate; "
                "NOT independent batch). Real batch → SURF track later.",
            ),
        )
        for sid, g in df.groupby("substrate_id"):
            smiles = g["substrate_smiles"].iloc[0]
            conn.execute(
                """INSERT INTO substrates(substrate_id, reaction_id, name, smiles, smiles_elec, notes)
                   VALUES (?,?,?,?,?,?)""",
                (sid, REACTION_ID, sid, smiles, smiles, "primary_track; logical_plate_aligned=1"),
            )
            vec = _smiles_fingerprint(smiles, 32)
            conn.execute(
                """INSERT INTO descriptors(descriptor_id, entity_type, entity_id, name, dim, vector_json)
                   VALUES (?,?,?,?,?,?)""",
                (f"fp_{sid}", "substrate", sid, "hashed_smiles_v1", 32, json.dumps(vec)),
            )
        for pid in sorted(df["plate_id"].unique()):
            conn.execute(
                """INSERT INTO plates(plate_id, reaction_id, notes, bias_offset, bias_scale)
                   VALUES (?,?,?,?,?)""",
                (pid, REACTION_ID, "LOGICAL plate (=substrate task), not physical batch", 0.0, 1.0),
            )
        for cid, g in df.groupby("condition_id"):
            row = g.iloc[0]
            additive = row.get("additive")
            conn.execute(
                """INSERT INTO conditions(
                    condition_id, reaction_id, catalyst, ligand, base, solvent,
                    condition_json, is_anchor
                   ) VALUES (?,?,?,?,?,?,?,?)""",
                (
                    cid,
                    REACTION_ID,
                    # SCHEMA NOTE: catalyst column stores additive_smiles for this library
                    # (Pd precursor fixed in Ahneman/EDBO design). See docs/05_data_roles.md.
                    None if pd.isna(additive) else str(additive),
                    row["ligand"],
                    row["base"],
                    None,
                    json.dumps(
                        {
                            "ligand_smiles": row["ligand"],
                            "base_smiles": row["base"],
                            "additive_smiles": None if pd.isna(additive) else str(additive),
                            "catalyst_column_semantics": "additive_smiles",
                        }
                    ),
                    0,
                ),
            )
        for _, r in df.iterrows():
            conn.execute(
                """INSERT INTO experiments(
                    experiment_id, reaction_id, substrate_id, plate_id, condition_id,
                    yield, replicate, is_anchor, quality_flag, source
                   ) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    r["experiment_id"],
                    REACTION_ID,
                    r["substrate_id"],
                    r["plate_id"],
                    r["condition_id"],
                    float(r["yield"]),
                    1,
                    0,
                    "ok",
                    str(r["source"]),
                ),
            )
        # literature pointers
        for row in [
            ("Ahneman2018BH", "Predicting reaction performance in C-N cross-coupling", 2018, "10.1126/science.aar5169", "data,bh,primary", "", 3),
            ("Shields2021", "Bayesian reaction optimization as a tool for chemical synthesis", 2021, "10.1038/s41586-021-03213-y", "bo", "reading_notes/Shields2021.md", 3),
        ]:
            conn.execute(
                "INSERT OR REPLACE INTO literature(cite_key, title, year, doi, tags, path_note, priority) VALUES (?,?,?,?,?,?,?)",
                row,
            )
        conn.commit()

    n_sub = df["substrate_id"].nunique()
    n_cond = df["condition_id"].nunique()
    print(f"Wrote long CSV: {csv_path} ({len(df)} rows)")
    print(f"Ingested DB: {args.db}")
    print(f"  substrates={n_sub}  unique_conditions={n_cond}  reaction_id={REACTION_ID}")
    print("  SEMANTICS: plate_id is LOGICAL (aligned with substrate), not physical batch.")


if __name__ == "__main__":
    main()
