# -*- coding: utf-8 -*-
"""项目工作区读写。"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

from factors import FactorSpec, factor_keys

SCHEMA_VERSION = 1
CONFIG_NAME = "config.json"
HISTORY_NAME = "history.csv"
LAST_REC_NAME = "last_recommendations.csv"


def sanitize_project_id(name: str) -> str:
    s = re.sub(r"[^\w一-鿿\-]", "_", name.strip())[:64]
    return s or "project"


def workspaces_root(project_root: Path) -> Path:
    return project_root / "workspaces"


def list_projects(project_root: Path) -> list[str]:
    root = workspaces_root(project_root)
    if not root.is_dir():
        return []
    out = []
    for p in sorted(root.iterdir()):
        if p.is_dir() and (p / CONFIG_NAME).is_file():
            out.append(p.name)
    return out


def project_dir(project_root: Path, project_id: str) -> Path:
    return workspaces_root(project_root) / project_id


def default_config() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "template": "condition_optimization",
        "target_column": "yield",
        "batch_size": 5,
        "acquisition_function": "EI",
        "training_iters": 100,
        "noise_constraint": 0.01,
        "domain_cap": 2500,
        "factors": [],
    }


def load_config(ws: Path) -> dict:
    path = ws / CONFIG_NAME
    if not path.is_file():
        return default_config()
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    base = default_config()
    base.update(cfg)
    base["schema_version"] = SCHEMA_VERSION
    return base


def save_config(ws: Path, cfg: dict) -> None:
    ws.mkdir(parents=True, exist_ok=True)
    cfg = dict(cfg)
    cfg["schema_version"] = SCHEMA_VERSION
    with open(ws / CONFIG_NAME, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def get_factors(cfg: dict) -> list[FactorSpec]:
    return [FactorSpec.from_dict(x) for x in cfg.get("factors", [])]


def descriptor_path(ws: Path, key: str) -> Path:
    return ws / f"descriptor_{key}.csv"


def levels_path(ws: Path, key: str) -> Path:
    return ws / f"levels_{key}.csv"


def load_history(ws: Path, target_col: str, keys: list[str]) -> pd.DataFrame:
    path = ws / HISTORY_NAME
    if not path.is_file():
        return pd.DataFrame(columns=keys + [target_col])
    df = pd.read_csv(path)
    return df


def save_history(ws: Path, df: pd.DataFrame) -> None:
    ws.mkdir(parents=True, exist_ok=True)
    df.to_csv(ws / HISTORY_NAME, index=False)


def save_recommendations(ws: Path, df: pd.DataFrame) -> None:
    ws.mkdir(parents=True, exist_ok=True)
    df.to_csv(ws / LAST_REC_NAME, index=False)


def load_recommendations(ws: Path) -> pd.DataFrame | None:
    path = ws / LAST_REC_NAME
    if not path.is_file():
        return None
    return pd.read_csv(path)


def create_project(project_root: Path, name: str, cfg: dict) -> str:
    pid = sanitize_project_id(name)
    ws = project_dir(project_root, pid)
    if ws.exists() and (ws / CONFIG_NAME).is_file():
        raise FileExistsError(f"项目已存在: {pid}")
    save_config(ws, cfg)
    keys = factor_keys(get_factors(cfg))
    save_history(ws, pd.DataFrame(columns=keys + [cfg.get("target_column", "yield")]))
    return pid
