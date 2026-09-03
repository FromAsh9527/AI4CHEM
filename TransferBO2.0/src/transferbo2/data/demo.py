"""Synthetic multi-substrate, multi-plate HTE generator for platform smoke tests."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from transferbo2.data.database import PACKAGE_ROOT, connect, init_schema


CATALYSTS = ["PdA", "PdB", "PdC", "NiA"]
LIGANDS = ["L1", "L2", "L3", "L4", "L5"]
BASES = ["K2CO3", "Cs2CO3", "NaOtBu"]
SOLVENTS = ["Tol", "Diox", "DMF", "MeCN"]
TEMPS = [60.0, 80.0, 100.0]
TIMES = [2.0, 6.0, 12.0]


def _condition_grid(reaction_id: str) -> List[dict]:
    rows = []
    idx = 0
    for cat in CATALYSTS:
        for lig in LIGANDS:
            for base in BASES:
                for sol in SOLVENTS:
                    for t in TEMPS:
                        for th in TIMES:
                            cid = f"cond_{idx:04d}"
                            rows.append(
                                {
                                    "condition_id": cid,
                                    "reaction_id": reaction_id,
                                    "catalyst": cat,
                                    "ligand": lig,
                                    "base": base,
                                    "solvent": sol,
                                    "temperature_c": t,
                                    "time_h": th,
                                    "equiv": 1.0,
                                    "condition_json": json.dumps(
                                        {
                                            "catalyst": cat,
                                            "ligand": lig,
                                            "base": base,
                                            "solvent": sol,
                                            "temperature_c": t,
                                            "time_h": th,
                                        }
                                    ),
                                    "is_anchor": 0,
                                }
                            )
                            idx += 1
    # Mark a few anchors spanning performance regimes (set later after scoring)
    return rows


def _substrate_latent(n: int, dim: int, rng: np.random.Generator) -> np.ndarray:
    """Generate correlated substrate descriptor vectors."""
    base = rng.normal(0, 1, size=(n, dim))
    # encourage two clusters: similar vs OOD
    for i in range(n):
        if i < max(2, n // 2):
            base[i] += np.array([1.5] * (dim // 2) + [0.0] * (dim - dim // 2))
        else:
            base[i] += np.array([-1.2] * (dim // 2) + [0.8] * (dim - dim // 2))
    return base


def _encode_condition(row: dict) -> np.ndarray:
    """Simple numeric encoding for synthetic chemistry response."""
    cat = CATALYSTS.index(row["catalyst"]) / max(1, len(CATALYSTS) - 1)
    lig = LIGANDS.index(row["ligand"]) / max(1, len(LIGANDS) - 1)
    base = BASES.index(row["base"]) / max(1, len(BASES) - 1)
    sol = SOLVENTS.index(row["solvent"]) / max(1, len(SOLVENTS) - 1)
    temp = (row["temperature_c"] - 60.0) / 40.0
    time = (row["time_h"] - 2.0) / 10.0
    return np.array([cat, lig, base, sol, temp, time], dtype=float)


def _true_yield(phi_s: np.ndarray, x: np.ndarray, rng: np.random.Generator, noise: float) -> float:
    # Shared structure + substrate-specific preference
    shared = 55 + 25 * math.sin(2.2 * x[0] + 1.1 * x[1]) + 10 * (1 - abs(x[2] - 0.5))
    pref = 18 * float(np.dot(phi_s[:3], x[:3])) + 8 * float(phi_s[3] * x[3])
    temp_term = 6 * math.exp(-((x[4] - (0.4 + 0.3 * phi_s[4])) ** 2) / 0.15)
    y = shared + pref + temp_term + rng.normal(0, noise)
    return float(np.clip(y, 0.0, 100.0))


def generate_demo_dataset(
    *,
    seed: int = 7,
    n_substrates: int = 6,
    n_plates: int = 3,
    desc_dim: int = 8,
    noise: float = 2.5,
    subsample_per_substrate: int | None = 180,
) -> Tuple[pd.DataFrame, Dict[str, np.ndarray], dict]:
    """Return long experiment table + substrate descriptor dict.

    Grid is large (~2880); by default subsample per substrate for tractable demos,
    but keep shared anchor conditions on every plate.
    """
    rng = np.random.default_rng(seed)
    reaction_id = "demo_cn_coupling"
    conditions = _condition_grid(reaction_id)
    X = np.vstack([_encode_condition(c) for c in conditions])
    phi = _substrate_latent(n_substrates, desc_dim, rng)

    # Choose anchors: mid indices with diverse encodings
    anchor_idx = [0, len(conditions) // 4, len(conditions) // 2, (3 * len(conditions)) // 4]
    for i in anchor_idx:
        conditions[i]["is_anchor"] = 1

    # Plate effects: global offset + mild condition interaction
    plate_offsets = rng.normal(0, 6.0, size=n_plates)
    plate_scales = 1.0 + rng.normal(0, 0.05, size=n_plates)
    plate_cond_bias = rng.normal(0, 1.5, size=(n_plates, X.shape[1]))

    substrates = [f"sub_{i:02d}" for i in range(n_substrates)]
    plates = [f"plate_{j+1}" for j in range(n_plates)]

    # Assign substrates to plates with overlap (history vs target realism)
    # Each substrate appears primarily on one plate, with anchors replicated.
    primary = {substrates[i]: plates[i % n_plates] for i in range(n_substrates)}

    records = []
    eid = 0
    for si, sid in enumerate(substrates):
        # candidate condition indices: anchors + random subsample
        keep = set(anchor_idx)
        if subsample_per_substrate is not None:
            extra = rng.choice(
                len(conditions),
                size=min(subsample_per_substrate, len(conditions)),
                replace=False,
            )
            keep.update(int(i) for i in extra)
        else:
            keep.update(range(len(conditions)))
        keep = sorted(keep)

        for pi, pid in enumerate(plates):
            # full non-anchor data only on primary plate; anchors on all plates
            for ci in keep:
                is_anchor = conditions[ci]["is_anchor"] == 1
                if pid != primary[sid] and not is_anchor:
                    continue
                y0 = _true_yield(phi[si], X[ci], rng, noise=noise)
                # plate effect
                y = plate_scales[pi] * y0 + plate_offsets[pi] + float(plate_cond_bias[pi] @ X[ci])
                y = float(np.clip(y, 0.0, 100.0))
                row = conditions[ci]
                well_r = int(ci % 8)
                well_c = int((ci // 8) % 12)
                records.append(
                    {
                        "experiment_id": f"exp_{eid:06d}",
                        "reaction_id": reaction_id,
                        "substrate_id": sid,
                        "plate_id": pid,
                        "condition_id": row["condition_id"],
                        "well": f"{chr(65 + well_r)}{well_c+1:02d}",
                        "row": well_r,
                        "col": well_c,
                        "date": f"2026-0{(pi % 9) + 1}-15",
                        "yield": y,
                        "selectivity": None,
                        "replicate": 1,
                        "is_anchor": int(is_anchor),
                        "reagent_lot": f"lot_{pid}",
                        "instrument_id": "lc_01",
                        "operator": "demo",
                        "quality_flag": "ok",
                        "source": "demo",
                        "catalyst": row["catalyst"],
                        "ligand": row["ligand"],
                        "base": row["base"],
                        "solvent": row["solvent"],
                        "temperature_c": row["temperature_c"],
                        "time_h": row["time_h"],
                        "equiv": row["equiv"],
                    }
                )
                eid += 1

    df = pd.DataFrame(records)
    desc = {substrates[i]: phi[i] for i in range(n_substrates)}
    meta = {
        "reaction_id": reaction_id,
        "conditions": conditions,
        "substrates": substrates,
        "plates": plates,
        "plate_offsets": plate_offsets,
        "plate_scales": plate_scales,
        "primary": primary,
        "desc_dim": desc_dim,
    }
    return df, desc, meta


def write_demo_to_db(
    db_path: Path | str | None = None,
    *,
    seed: int = 7,
    processed_csv: Path | str | None = None,
    write_csv: bool = True,
) -> Path:
    from transferbo2.data.database import DEFAULT_DB

    path = Path(db_path) if db_path else DEFAULT_DB
    init_schema(path)
    df, desc, meta = generate_demo_dataset(seed=seed)
    reaction_id = meta["reaction_id"]

    if write_csv:
        out_csv = Path(processed_csv) if processed_csv else (PACKAGE_ROOT / "data" / "processed" / "demo_long.csv")
        out_csv.parent.mkdir(parents=True, exist_ok=True)
        try:
            df.to_csv(out_csv, index=False)
        except OSError as exc:
            # Baidu Sync / OneDrive locks are common on Windows shared folders
            print(f"[warn] could not write {out_csv}: {exc}")

    with connect(path) as conn:
        conn.execute("DELETE FROM experiments")
        conn.execute("DELETE FROM anchors")
        conn.execute("DELETE FROM descriptors")
        conn.execute("DELETE FROM conditions")
        conn.execute("DELETE FROM plates")
        conn.execute("DELETE FROM substrates")
        conn.execute("DELETE FROM reactions")
        conn.execute("DELETE FROM literature")

        conn.execute(
            "INSERT INTO reactions(reaction_id, name, template, description) VALUES (?,?,?,?)",
            (
                reaction_id,
                "Demo C-N coupling",
                "Buchwald-Hartwig-like",
                "Synthetic multi-substrate multi-plate library for TransferBO2.0 smoke tests",
            ),
        )

        for i, sid in enumerate(meta["substrates"]):
            conn.execute(
                """INSERT INTO substrates(substrate_id, reaction_id, name, smiles, notes)
                   VALUES (?,?,?,?,?)""",
                (sid, reaction_id, sid, f"C{i}DEMO", f"primary_plate={meta['primary'][sid]}"),
            )

        for j, pid in enumerate(meta["plates"]):
            conn.execute(
                """INSERT INTO plates(plate_id, reaction_id, date, instrument_id, operator, reagent_lot,
                   notes, bias_offset, bias_scale) VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    pid,
                    reaction_id,
                    f"2026-0{(j % 9) + 1}-15",
                    "lc_01",
                    "demo",
                    f"lot_{pid}",
                    "synthetic plate effect",
                    float(meta["plate_offsets"][j]),
                    float(meta["plate_scales"][j]),
                ),
            )

        for c in meta["conditions"]:
            conn.execute(
                """INSERT INTO conditions(condition_id, reaction_id, catalyst, ligand, base, solvent,
                   temperature_c, time_h, equiv, condition_json, is_anchor)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    c["condition_id"],
                    reaction_id,
                    c["catalyst"],
                    c["ligand"],
                    c["base"],
                    c["solvent"],
                    c["temperature_c"],
                    c["time_h"],
                    c["equiv"],
                    c["condition_json"],
                    c["is_anchor"],
                ),
            )
            if c["is_anchor"]:
                conn.execute(
                    "INSERT INTO anchors(anchor_id, reaction_id, condition_id, role, notes) VALUES (?,?,?,?,?)",
                    (f"anchor_{c['condition_id']}", reaction_id, c["condition_id"], "bridge", "demo anchor"),
                )

        for _, r in df.iterrows():
            conn.execute(
                """INSERT INTO experiments(
                    experiment_id, reaction_id, substrate_id, plate_id, condition_id,
                    well, row, col, date, yield, selectivity, replicate, is_anchor,
                    reagent_lot, instrument_id, operator, quality_flag, source
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    r["experiment_id"],
                    r["reaction_id"],
                    r["substrate_id"],
                    r["plate_id"],
                    r["condition_id"],
                    r["well"],
                    int(r["row"]),
                    int(r["col"]),
                    r["date"],
                    float(r["yield"]),
                    None,
                    int(r["replicate"]),
                    int(r["is_anchor"]),
                    r["reagent_lot"],
                    r["instrument_id"],
                    r["operator"],
                    r["quality_flag"],
                    r["source"],
                ),
            )

        for sid, vec in desc.items():
            conn.execute(
                """INSERT INTO descriptors(descriptor_id, entity_type, entity_id, name, dim, vector_json)
                   VALUES (?,?,?,?,?,?)""",
                (f"desc_{sid}", "substrate", sid, "physchem_v1", len(vec), json.dumps(vec.tolist())),
            )

        # seed literature registry
        lit = [
            ("Shields2021", "Bayesian reaction optimization as a tool for chemical synthesis", 2021, "10.1038/s41586-021-03213-y", "bo,reaction", "reading_notes/Shields2021.md", 3),
            ("Swersky2013MTBO", "Multi-Task Bayesian Optimization", 2013, "", "mtbo,transfer", "", 3),
            ("Bonilla2008MultioutputGP", "Multi-task Gaussian Process Prediction", 2008, "", "mtgp,icm", "", 3),
            ("Ahneman2018BH", "Predicting reaction performance in C-N cross-coupling", 2018, "10.1126/science.aar5169", "data,bh", "", 3),
            ("Johnson2007ComBat", "Adjusting batch effects in microarray expression data", 2007, "10.1093/biostatistics/kxj037", "batch", "", 2),
        ]
        for row in lit:
            conn.execute(
                "INSERT INTO literature(cite_key, title, year, doi, tags, path_note, priority) VALUES (?,?,?,?,?,?,?)",
                row,
            )
        conn.commit()

    return path
