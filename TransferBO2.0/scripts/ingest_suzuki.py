"""Ingest EDBO Suzuki plates into TransferBO2.0 (separate DB from amination).

Semantic contract (same as amination track):

- substrate_id  : task id from source plate_id (suz_t1…suz_t12) = one coupling pair
- plate_id      : logical_{substrate_id} — NOT independent physical batch
- condition_id  : candidate_key = ligand × base × solvent (shared across tasks)
- yield         : response (%)
- descriptors   : hashed_smiles_v1 on electrophile||nucleophile

Default source:
  ../TransferBO/data/processed/edbo_suzuki_plates.csv
Default DB (does NOT overwrite amination DB):
  data/db/transferbo2_suzuki.db
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from transferbo2.data.database import PACKAGE_ROOT, connect, init_schema

DEFAULT_SRC = (
    PACKAGE_ROOT.parent / "TransferBO" / "data" / "processed" / "edbo_suzuki_plates.csv"
)
DEFAULT_DB = PACKAGE_ROOT / "data" / "db" / "transferbo2_suzuki.db"
REACTION_ID = "edbo_suzuki"


def _smiles_fingerprint(smiles: str, dim: int = 32) -> list[float]:
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


def load_suzuki_long(src: Path) -> pd.DataFrame:
    df = pd.read_csv(src)
    required = [
        "plate_id",
        "ligand_smiles",
        "base_smiles",
        "solvent_smiles",
        "electrophile_smiles",
        "nucleophile_smiles",
        "response",
        "candidate_key",
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"{src} missing columns: {missing}")

    out = pd.DataFrame(
        {
            "reaction_id": REACTION_ID,
            "substrate_id": df["plate_id"].astype(str),
            "substrate_smiles_elec": df["electrophile_smiles"].astype(str),
            "substrate_smiles_nuc": df["nucleophile_smiles"].astype(str),
            "plate_id": df["plate_id"].astype(str).map(lambda s: f"logical_{s}"),
            "condition_id": df["candidate_key"].astype(str),
            "ligand": df["ligand_smiles"].astype(str),
            "base": df["base_smiles"].astype(str),
            "solvent": df["solvent_smiles"].astype(str),
            "yield": df["response"].astype(float),
            "source": df["source_dataset"].astype(str)
            if "source_dataset" in df.columns
            else "edbo_suzuki",
            "reaction_smiles": df["reaction_smiles"].astype(str)
            if "reaction_smiles" in df.columns
            else "",
        }
    )
    out["substrate_smiles"] = (
        out["substrate_smiles_elec"] + "||" + out["substrate_smiles_nuc"]
    )
    out = out.drop_duplicates(subset=["substrate_id", "condition_id"], keep="first")
    out["experiment_id"] = [f"suz_{i:05d}" for i in range(len(out))]
    return out.reset_index(drop=True)


def main() -> None:
    p = argparse.ArgumentParser(description="Ingest EDBO Suzuki into TransferBO2.0")
    p.add_argument("--src", type=Path, default=DEFAULT_SRC)
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    p.add_argument(
        "--out-csv",
        type=Path,
        default=PACKAGE_ROOT / "data" / "processed" / "suzuki_long.csv",
    )
    args = p.parse_args()

    if not args.src.exists():
        raise SystemExit(f"Source not found: {args.src}")

    df = load_suzuki_long(args.src)
    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out_csv, index=False)

    if args.db.exists():
        args.db.unlink()
    init_schema(args.db)

    with connect(args.db) as conn:
        conn.execute(
            """INSERT INTO reactions(reaction_id, name, template, description)
               VALUES (?,?,?,?)""",
            (
                REACTION_ID,
                "EDBO Suzuki–Miyaura (Shields et al. style task table)",
                "Suzuki-Miyaura",
                "Hard-negative / cross-chemistry track. "
                "Same OHE + hashed SMILES + LOSO strategies as amination_v1. "
                "plate_id=logical_{suz_t*} (one-pair-one-logical-plate; NOT physical batch).",
            ),
        )
        for sid, g in df.groupby("substrate_id"):
            elec = g["substrate_smiles_elec"].iloc[0]
            nuc = g["substrate_smiles_nuc"].iloc[0]
            pair = g["substrate_smiles"].iloc[0]
            conn.execute(
                """INSERT INTO substrates(
                    substrate_id, reaction_id, name, smiles, smiles_elec, smiles_nuc, notes
                   ) VALUES (?,?,?,?,?,?,?)""",
                (
                    sid,
                    REACTION_ID,
                    sid,
                    pair,
                    elec,
                    nuc,
                    "pair=electrophile||nucleophile; logical_plate_aligned=1",
                ),
            )
            vec = _smiles_fingerprint(pair, 32)
            conn.execute(
                """INSERT INTO descriptors(
                    descriptor_id, entity_type, entity_id, name, dim, vector_json
                   ) VALUES (?,?,?,?,?,?)""",
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
            conn.execute(
                """INSERT INTO conditions(
                    condition_id, reaction_id, catalyst, ligand, base, solvent,
                    condition_json, is_anchor
                   ) VALUES (?,?,?,?,?,?,?,?)""",
                (
                    cid,
                    REACTION_ID,
                    None,  # Pd fixed / not varying in this table
                    row["ligand"],
                    row["base"],
                    row["solvent"],
                    json.dumps(
                        {
                            "ligand_smiles": row["ligand"],
                            "base_smiles": row["base"],
                            "solvent_smiles": row["solvent"],
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
        conn.execute(
            "INSERT OR REPLACE INTO literature(cite_key, title, year, doi, tags, path_note, priority) VALUES (?,?,?,?,?,?,?)",
            (
                "Shields2021",
                "Bayesian reaction optimization as a tool for chemical synthesis",
                2021,
                "10.1038/s41586-021-03213-y",
                "bo,suzuki,edbo",
                "",
                3,
            ),
        )
        conn.commit()

    print(f"Wrote long CSV: {args.out_csv} ({len(df)} rows)")
    print(f"Ingested DB: {args.db}")
    print(
        f"  substrates={df['substrate_id'].nunique()}  "
        f"unique_conditions={df['condition_id'].nunique()}  reaction_id={REACTION_ID}"
    )
    print("  SEMANTICS: plate_id is LOGICAL (aligned with substrate pair), not physical batch.")
    print("  NOTE: amination DB untouched (separate path).")


if __name__ == "__main__":
    main()
