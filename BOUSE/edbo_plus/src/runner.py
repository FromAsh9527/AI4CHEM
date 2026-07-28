# -*- coding: utf-8 -*-
"""调用上游 EDBOplus：生成 scope / 跑一轮推荐。"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from workspace import (
    factor_columns,
    load_config,
    load_reaction,
    observed_mask,
    reaction_path,
    save_config,
    save_reaction,
    suggested_mask,
)


def _edboplus():
    from edbo.plus.optimizer_botorch import EDBOplus

    return EDBOplus()


def generate_scope(ws: Path, components: dict, cfg: dict | None = None) -> tuple[pd.DataFrame, int]:
    cfg = cfg or load_config(ws)
    filename = cfg.get("filename") or "reaction.csv"
    # 上游 generate 在 check_overwrite=True 时会 input()，UI 必须关掉
    # 注意：EDBOplus.generate_reaction_scope 只返回 DataFrame（内部已打印组合数）
    df = _edboplus().generate_reaction_scope(
        components=components,
        directory=str(ws),
        filename=filename,
        check_overwrite=False,
    )
    if df is None:
        raise RuntimeError("生成 scope 失败（上游返回 None）")
    cfg["components"] = components
    save_config(ws, cfg)
    return df, int(len(df))


def import_scope_csv(ws: Path, df: pd.DataFrame, cfg: dict | None = None) -> pd.DataFrame:
    cfg = cfg or load_config(ws)
    objectives = list(cfg.get("objectives") or [])
    # 去掉目标列 / priority，留给 run() 创建 PENDING
    drop = set(objectives) | {"priority"}
    keep = [c for c in df.columns if c not in drop]
    if not keep:
        raise ValueError("上传的 CSV 没有可用因子列")
    clean = df[keep].copy()
    save_reaction(ws, clean, cfg)
    return clean


def run_round(ws: Path, cfg: dict | None = None) -> pd.DataFrame:
    cfg = cfg or load_config(ws)
    path = reaction_path(ws, cfg)
    if not path.exists():
        raise FileNotFoundError("尚未生成搜索域（reaction.csv）")

    objectives = list(cfg["objectives"])
    modes = list(cfg["objective_mode"])
    if len(objectives) != len(modes):
        raise ValueError("objectives 与 objective_mode 长度必须一致")
    if not objectives:
        raise ValueError("至少需要一个目标")

    acq = cfg.get("acquisition_function") or "NoisyEHVI"
    # 单目标时 NoisyEHVI 会自动退化为 EI（上游逻辑）；多目标默认 NoisyEHVI
    if len(objectives) == 1 and acq.lower() == "ehvi":
        acq = "NoisyEHVI"

    thresholds = cfg.get("objective_thresholds")
    if thresholds is not None and len(thresholds) != len(objectives):
        raise ValueError("objective_thresholds 长度必须与 objectives 一致（或设为 null）")

    df = _edboplus().run(
        objectives=objectives,
        objective_mode=modes,
        objective_thresholds=thresholds,
        directory=str(ws),
        filename=cfg.get("filename") or "reaction.csv",
        columns_features=cfg.get("columns_features") or "all",
        batch=int(cfg.get("batch") or 3),
        init_sampling_method=str(cfg.get("init_sampling_method") or "cvt"),
        seed=int(cfg.get("seed") or 0),
        acquisition_function=acq,
        acquisition_function_sampler=cfg.get("acquisition_function_sampler")
        or "SobolQMCNormalSampler",
    )
    return df


def scope_summary(ws: Path, cfg: dict | None = None) -> dict[str, Any]:
    cfg = cfg or load_config(ws)
    df = load_reaction(ws, cfg)
    objectives = list(cfg.get("objectives") or [])
    if df.empty:
        return {"exists": False, "n_rows": 0}
    obs = observed_mask(df, objectives)
    sug = suggested_mask(df)
    return {
        "exists": True,
        "n_rows": int(len(df)),
        "n_factors": len(factor_columns(df, objectives)),
        "factor_cols": factor_columns(df, objectives),
        "n_observed": int(obs.sum()),
        "n_suggested": int(sug.sum()),
        "has_priority": "priority" in df.columns,
        "objectives_in_csv": [o for o in objectives if o in df.columns],
    }
