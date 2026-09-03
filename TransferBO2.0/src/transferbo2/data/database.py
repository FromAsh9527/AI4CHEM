"""SQLite helpers and long-table loaders."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd

PACKAGE_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB = PACKAGE_ROOT / "data" / "db" / "transferbo2.db"
SCHEMA_PATH = PACKAGE_ROOT / "data" / "db" / "schema.sql"


def connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else DEFAULT_DB
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(db_path: Path | str | None = None, schema_path: Path | str | None = None) -> Path:
    path = Path(db_path) if db_path else DEFAULT_DB
    sql_path = Path(schema_path) if schema_path else SCHEMA_PATH
    ddl = sql_path.read_text(encoding="utf-8")
    with connect(path) as conn:
        conn.executescript(ddl)
        conn.commit()
    return path


def experiments_frame(
    conn: sqlite3.Connection,
    *,
    reaction_id: Optional[str] = None,
    substrate_ids: Optional[Iterable[str]] = None,
    plate_ids: Optional[Iterable[str]] = None,
) -> pd.DataFrame:
    q = """
    SELECT
      e.experiment_id, e.reaction_id, e.substrate_id, e.plate_id, e.condition_id,
      e.well, e.row, e.col, e.date, e.yield, e.selectivity, e.replicate,
      e.is_anchor, e.quality_flag, e.source,
      c.catalyst, c.ligand, c.base, c.solvent,
      c.temperature_c, c.time_h, c.equiv, c.is_anchor AS condition_is_anchor,
      s.smiles, s.smiles_elec, s.smiles_nuc, s.name AS substrate_name,
      p.date AS plate_date, p.bias_offset, p.bias_scale
    FROM experiments e
    JOIN conditions c ON e.condition_id = c.condition_id
    JOIN substrates s ON e.substrate_id = s.substrate_id
    JOIN plates p ON e.plate_id = p.plate_id
    WHERE 1=1
    """
    params: list = []
    if reaction_id:
        q += " AND e.reaction_id = ?"
        params.append(reaction_id)
    if substrate_ids:
        ids = list(substrate_ids)
        q += f" AND e.substrate_id IN ({','.join('?' for _ in ids)})"
        params.extend(ids)
    if plate_ids:
        ids = list(plate_ids)
        q += f" AND e.plate_id IN ({','.join('?' for _ in ids)})"
        params.extend(ids)
    return pd.read_sql_query(q, conn, params=params)


def load_descriptor_matrix(
    conn: sqlite3.Connection,
    *,
    entity_type: str,
    name: str,
    entity_ids: Optional[Iterable[str]] = None,
) -> pd.DataFrame:
    q = "SELECT entity_id, vector_json FROM descriptors WHERE entity_type=? AND name=?"
    params: list = [entity_type, name]
    if entity_ids:
        ids = list(entity_ids)
        q += f" AND entity_id IN ({','.join('?' for _ in ids)})"
        params.extend(ids)
    rows = conn.execute(q, params).fetchall()
    records = []
    for r in rows:
        vec = json.loads(r["vector_json"])
        rec = {"entity_id": r["entity_id"]}
        for i, v in enumerate(vec):
            rec[f"d{i}"] = float(v)
        records.append(rec)
    if not records:
        return pd.DataFrame(columns=["entity_id"])
    return pd.DataFrame(records)


def export_long_csv(conn: sqlite3.Connection, out_path: Path | str, **kwargs) -> Path:
    df = experiments_frame(conn, **kwargs)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    return out
