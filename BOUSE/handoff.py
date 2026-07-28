# -*- coding: utf-8 -*-
"""描述符 ↔ EDBO 交接（校验 / 导入）。供 scripts 与两侧 Streamlit 共用。"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd

ID_COL = "molecule_id"
BOUSE_ROOT = Path(__file__).resolve().parent
EDBO_ROOT = BOUSE_ROOT / "edbo"
DESCRIPTORS_OUTPUT = BOUSE_ROOT / "descriptors" / "output"


def check_descriptor_df(df: pd.DataFrame, *, id_col: str = ID_COL) -> list[str]:
    errors: list[str] = []
    if id_col not in df.columns:
        return [f"缺少列 `{id_col}`"]
    if df[id_col].isna().any() or df[id_col].astype(str).str.strip().eq("").any():
        errors.append(f"`{id_col}` 存在空值")
    ids = df[id_col].astype(str).str.strip()
    if ids.duplicated().any():
        errors.append(f"`{id_col}` 有 {int(ids.duplicated().sum())} 个重复值")
    feat = [c for c in df.columns if c != id_col]
    if not feat:
        errors.append("没有数值特征列")
    for c in feat:
        if pd.api.types.is_numeric_dtype(df[c]):
            continue
        coerced = pd.to_numeric(df[c], errors="coerce")
        if coerced.isna().any() and df[c].notna().any():
            errors.append(f"特征列非数值或含非法值: {c}")
    return errors


def check_descriptor_file(path: Path, *, id_col: str = ID_COL) -> list[str]:
    path = Path(path)
    if not path.is_file():
        return [f"文件不存在: {path}"]
    try:
        df = pd.read_csv(path)
    except Exception as e:
        return [f"无法读取 CSV: {e}"]
    return check_descriptor_df(df, id_col=id_col)


def list_edbo_projects(edbo_root: Path | None = None) -> list[str]:
    root = Path(edbo_root or EDBO_ROOT) / "workspaces"
    if not root.is_dir():
        return []
    out = []
    for p in sorted(root.iterdir()):
        if p.is_dir() and (p / "config.json").is_file():
            out.append(p.name)
    return out


def project_workspace(project_id: str, edbo_root: Path | None = None) -> Path:
    return Path(edbo_root or EDBO_ROOT) / "workspaces" / project_id


def chemical_descriptor_factors(ws: Path) -> list[dict]:
    """返回需要 descriptor_*.csv 的化学因子列表。"""
    cfg_path = ws / "config.json"
    if not cfg_path.is_file():
        return []
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    out = []
    for f in cfg.get("factors", []):
        if not isinstance(f, dict):
            continue
        if f.get("kind", "chemical") != "chemical":
            continue
        if f.get("encoding", "descriptor") != "descriptor":
            continue
        key = f.get("key")
        if not key:
            continue
        path = ws / f"descriptor_{key}.csv"
        status = "ready" if path.is_file() else "missing"
        n_rows, n_feat = None, None
        if path.is_file():
            try:
                df = pd.read_csv(path)
                id_col = f.get("id_column", ID_COL)
                n_rows = len(df)
                n_feat = max(0, df.shape[1] - (1 if id_col in df.columns else 0))
            except Exception:
                status = "broken"
        out.append(
            {
                "key": key,
                "id_column": f.get("id_column", ID_COL),
                "path": path,
                "status": status,
                "n_rows": n_rows,
                "n_features": n_feat,
            }
        )
    return out


def list_descriptor_outputs(output_dir: Path | None = None) -> list[Path]:
    d = Path(output_dir or DESCRIPTORS_OUTPUT)
    if not d.is_dir():
        return []
    return sorted(d.glob("descriptor_*.csv")) + sorted(
        p for p in d.glob("*.csv") if not p.name.startswith("descriptor_") and "failed" not in p.name
    )


def import_descriptor(
    src: Path | pd.DataFrame,
    workspace: Path,
    factor: str,
    *,
    force: bool = False,
    skip_validate: bool = False,
) -> Path:
    """写入 workspace/descriptor_<factor>.csv，返回目标路径。"""
    workspace = Path(workspace)
    factor = str(factor).strip()
    if not factor:
        raise ValueError("factor 不能为空")
    workspace.mkdir(parents=True, exist_ok=True)
    dest = workspace / f"descriptor_{factor}.csv"

    if isinstance(src, pd.DataFrame):
        df = src.copy()
        if not skip_validate:
            errs = check_descriptor_df(df)
            if errs:
                raise ValueError("不符合交接契约:\n  - " + "\n  - ".join(errs))
        if dest.exists() and not force:
            raise FileExistsError(f"已存在 {dest.name}（可强制覆盖）")
        cols = [ID_COL] + [c for c in df.columns if c != ID_COL]
        if ID_COL not in df.columns:
            raise ValueError(f"缺少 {ID_COL}")
        df[cols].to_csv(dest, index=False)
        return dest

    src = Path(src)
    if not src.is_file():
        raise FileNotFoundError(src)
    if not skip_validate:
        errs = check_descriptor_file(src)
        if errs:
            raise ValueError("源文件不符合契约:\n  - " + "\n  - ".join(errs))
    if dest.exists() and not force:
        raise FileExistsError(f"已存在 {dest.name}（可强制覆盖）")
    shutil.copy2(src, dest)
    return dest


def check_workspace_descriptors(ws: Path) -> list[str]:
    errors: list[str] = []
    ws = Path(ws)
    if not ws.is_dir():
        return [f"工作区不存在: {ws}"]
    if not (ws / "config.json").is_file():
        errors.append("缺少 config.json")
    for item in chemical_descriptor_factors(ws):
        if item["status"] == "missing":
            errors.append(f"因子 `{item['key']}` 缺少 {item['path'].name}")
        elif item["status"] == "broken":
            errors.append(f"因子 `{item['key']}` 的描述符文件无法读取")
        else:
            sub = check_descriptor_file(item["path"], id_col=item["id_column"])
            errors.extend([f"[{item['path'].name}] {e}" for e in sub])
    return errors
