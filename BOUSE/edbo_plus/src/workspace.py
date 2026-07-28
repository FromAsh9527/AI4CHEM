# -*- coding: utf-8 -*-
"""EDBO+ 工作区：一个项目 = 一个目录 + reaction.csv + config.json。"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pandas as pd

DEFAULT_FILENAME = "reaction.csv"

DEFAULT_CONFIG: dict[str, Any] = {
    "filename": DEFAULT_FILENAME,
    "objectives": ["yield", "cost"],
    "objective_mode": ["max", "min"],
    "objective_thresholds": None,
    "batch": 3,
    "seed": 0,
    "init_sampling_method": "cvt",
    "acquisition_function": "NoisyEHVI",
    "acquisition_function_sampler": "SobolQMCNormalSampler",
    "columns_features": "all",
    "components": {
        "solvent": ["THF", "Toluene", "DMSO"],
        "T": [-10, 0, 10, 25],
        "concentration": [0.1, 0.2, 1.0],
    },
}


def workspaces_root(package_root: Path) -> Path:
    return package_root / "workspaces"


def sanitize_project_id(name: str) -> str:
    s = (name or "").strip()
    s = re.sub(r"[^\w\-]+", "_", s, flags=re.UNICODE)
    s = re.sub(r"_+", "_", s).strip("_")
    if not s:
        raise ValueError("项目名不能为空")
    return s[:80]


def project_dir(package_root: Path, project_id: str) -> Path:
    return workspaces_root(package_root) / project_id


def list_projects(package_root: Path) -> list[str]:
    root = workspaces_root(package_root)
    if not root.exists():
        return []
    out = []
    for p in sorted(root.iterdir()):
        if p.is_dir() and not p.name.startswith(("_", ".")):
            if (p / "config.json").exists() or (p / DEFAULT_FILENAME).exists():
                out.append(p.name)
    return out


def reaction_path(ws: Path, cfg: dict | None = None) -> Path:
    name = DEFAULT_FILENAME
    if cfg:
        name = cfg.get("filename") or DEFAULT_FILENAME
    return ws / name


def pred_path(ws: Path, cfg: dict | None = None) -> Path:
    rp = reaction_path(ws, cfg)
    return rp.parent / f"pred_{rp.name}"


def load_config(ws: Path) -> dict:
    path = ws / "config.json"
    if not path.exists():
        cfg = dict(DEFAULT_CONFIG)
        save_config(ws, cfg)
        return cfg
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    # fill defaults for older projects
    for k, v in DEFAULT_CONFIG.items():
        cfg.setdefault(k, v)
    return cfg


def save_config(ws: Path, cfg: dict) -> None:
    ws.mkdir(parents=True, exist_ok=True)
    with open(ws / "config.json", "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def create_project(package_root: Path, name: str, cfg: dict | None = None) -> str:
    pid = sanitize_project_id(name)
    ws = project_dir(package_root, pid)
    if ws.exists() and any(ws.iterdir()):
        raise FileExistsError(f"项目已存在：{pid}")
    ws.mkdir(parents=True, exist_ok=True)
    conf = dict(DEFAULT_CONFIG)
    if cfg:
        conf.update(cfg)
    conf["filename"] = conf.get("filename") or DEFAULT_FILENAME
    save_config(ws, conf)
    return pid


def load_reaction(ws: Path, cfg: dict | None = None) -> pd.DataFrame:
    path = reaction_path(ws, cfg)
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def save_reaction(ws: Path, df: pd.DataFrame, cfg: dict | None = None) -> Path:
    path = reaction_path(ws, cfg)
    ws.mkdir(parents=True, exist_ok=True)
    _write_csv_retry(path, df)
    return path


def _write_csv_retry(path: Path, df: pd.DataFrame, attempts: int = 8) -> None:
    """Baidu Sync / AV 偶发锁文件时重试。"""
    import time

    last: Exception | None = None
    for i in range(attempts):
        try:
            df.to_csv(path, index=False)
            return
        except PermissionError as e:
            last = e
            time.sleep(0.4 * (i + 1))
    assert last is not None
    raise last


def factor_columns(df: pd.DataFrame, objectives: list[str]) -> list[str]:
    skip = set(objectives) | {"priority"}
    skip |= {c for c in df.columns if c.endswith(
        ("_predicted_mean", "_predicted_std_dev", "_expected_improvement")
    )}
    return [c for c in df.columns if c not in skip]


def observed_mask(df: pd.DataFrame, objectives: list[str]) -> pd.Series:
    if df.empty or not objectives:
        return pd.Series([], dtype=bool)
    for obj in objectives:
        if obj not in df.columns:
            return pd.Series([False] * len(df), index=df.index)
    m = pd.Series([True] * len(df), index=df.index)
    for obj in objectives:
        col = df[obj].astype(str)
        m &= ~col.str.contains("PENDING", case=False, na=False)
        m &= df[obj].notna()
    return m


def suggested_mask(df: pd.DataFrame) -> pd.Series:
    if df.empty or "priority" not in df.columns:
        return pd.Series([False] * len(df), index=df.index)
    return pd.to_numeric(df["priority"], errors="coerce").fillna(0) == 1


def parse_level_token(tok: str):
    s = tok.strip()
    if not s:
        return None
    try:
        if re.fullmatch(r"[+-]?\d+", s):
            return int(s)
        return float(s)
    except ValueError:
        return s


def parse_levels_text(text: str) -> list:
    parts: list[str] = []
    for line in (text or "").replace(",", "\n").splitlines():
        t = line.strip()
        if t:
            parts.append(t)
    out = []
    for p in parts:
        v = parse_level_token(p)
        if v is not None:
            out.append(v)
    return out
