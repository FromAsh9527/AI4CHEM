"""Load processed multi-plate HTE tables."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

REQUIRED_COLS = ("additive_id", "smiles", "plate_id", "response")


def load_plates(
    path: str | Path,
    *,
    plate_col: str = "plate_id",
    smiles_col: str = "smiles",
    response_col: str = "response",
    id_col: str = "additive_id",
) -> pd.DataFrame:
    """Load cleaned four-plate CSV and normalise column names."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"Processed data not found: {path}\n"
            "Run: python scripts/prepare_data.py  (see data/README.md)"
        )
    df = pd.read_csv(path)
    rename = {}
    if id_col != "additive_id" and id_col in df.columns:
        rename[id_col] = "additive_id"
    if smiles_col != "smiles" and smiles_col in df.columns:
        rename[smiles_col] = "smiles"
    if plate_col != "plate_id" and plate_col in df.columns:
        rename[plate_col] = "plate_id"
    if response_col != "response" and response_col in df.columns:
        rename[response_col] = "response"
    if rename:
        df = df.rename(columns=rename)

    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns {missing}. Got: {list(df.columns)}")

    df = df.dropna(subset=["smiles", "plate_id", "response"]).copy()
    df["plate_id"] = df["plate_id"].astype(str)
    df["response"] = pd.to_numeric(df["response"], errors="coerce")
    df = df.dropna(subset=["response"]).reset_index(drop=True)
    return df


def list_plates(df: pd.DataFrame) -> list[str]:
    return sorted(df["plate_id"].unique().tolist())


def get_plate(df: pd.DataFrame, plate_id: str) -> pd.DataFrame:
    sub = df[df["plate_id"].astype(str) == str(plate_id)].reset_index(drop=True)
    if sub.empty:
        raise ValueError(f"No rows for plate_id={plate_id!r}. Available: {list_plates(df)}")
    return sub
