# -*- coding: utf-8 -*-
"""由因子规格构建 meta（可读水平）与 domain_num（GP 数值域）。"""
from __future__ import annotations

import itertools
from pathlib import Path

import numpy as np
import pandas as pd

from factors import FactorSpec
from workspace import descriptor_path, levels_path


def canonical_level(value, *, numeric: bool = False) -> str:
    """统一水平表示，避免 60 vs 60.0 导致历史无法匹配。"""
    if numeric:
        x = float(value)
        if np.isfinite(x) and abs(x - round(x)) < 1e-10:
            return str(int(round(x)))
        return f"{x:.10g}"
    return str(value).strip()


def row_key(row: pd.Series | dict, factors: list[FactorSpec]) -> tuple:
    key = []
    for f in factors:
        v = row[f.key]
        key.append(canonical_level(v, numeric=(f.kind == "numeric")))
    return tuple(key)


def _numeric_feature_cols(df: pd.DataFrame, id_col: str) -> list[str]:
    cols = []
    for c in df.columns:
        if c == id_col:
            continue
        if pd.api.types.is_numeric_dtype(df[c]):
            cols.append(c)
    return cols


def load_chemical_table(ws: Path, factor: FactorSpec) -> pd.DataFrame:
    """返回至少含 molecule_id 的表；descriptor 时另含数值列。"""
    id_col = factor.id_column
    if factor.encoding == "descriptor":
        path = descriptor_path(ws, factor.key)
        if not path.is_file():
            raise FileNotFoundError(f"缺少描述符文件: {path.name}")
        df = pd.read_csv(path)
        if id_col not in df.columns:
            raise ValueError(f"{path.name} 缺少列 {id_col}")
        df = df.copy()
        df[id_col] = df[id_col].astype(str)
        feat = _numeric_feature_cols(df, id_col)
        if not feat:
            raise ValueError(f"{path.name} 无可用数值描述符列")
        return df[[id_col] + feat].drop_duplicates(subset=[id_col])

    # ohe：优先 levels_*.csv，否则用 config.levels
    path = levels_path(ws, factor.key)
    if path.is_file():
        df = pd.read_csv(path)
        if id_col not in df.columns:
            raise ValueError(f"{path.name} 缺少列 {id_col}")
        ids = df[id_col].astype(str).tolist()
    elif factor.levels:
        ids = [str(x) for x in factor.levels]
    else:
        raise FileNotFoundError(
            f"因子 {factor.key}（独热）需要 levels_{factor.key}.csv 或在配置中填写 levels"
        )
    return pd.DataFrame({id_col: ids}).drop_duplicates()


def build_domain(
    ws: Path,
    factors: list[FactorSpec],
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """
    Returns
    -------
    meta : 每行一组实验条件（因子 key → 水平）
    domain_num : 与 meta 同行对齐的数值特征矩阵
    info : 域统计信息
    """
    if not factors:
        raise ValueError("尚未定义任何因子")

    level_maps: list[tuple[FactorSpec, list]] = []
    chem_tables: dict[str, pd.DataFrame] = {}

    for f in factors:
        if f.kind == "numeric":
            levels = f.numeric_levels()
            if not levels:
                raise ValueError(f"数值因子 {f.key} 没有水平")
            canon = []
            for v in levels:
                x = float(v)
                if abs(x - round(x)) < 1e-10:
                    canon.append(int(round(x)))
                else:
                    canon.append(x)
            level_maps.append((f, canon))
        else:
            table = load_chemical_table(ws, f)
            chem_tables[f.key] = table
            ids = table[f.id_column].astype(str).tolist()
            if not ids:
                raise ValueError(f"化学因子 {f.key} 没有水平")
            level_maps.append((f, ids))

    sizes = [len(lv) for _, lv in level_maps]
    domain_size = int(np.prod(sizes))
    if domain_size > 500_000:
        raise ValueError(f"搜索域过大: {domain_size:,}（上限 500,000），请减少水平")

    keys = [f.key for f, _ in level_maps]
    rows = list(itertools.product(*[lv for _, lv in level_maps]))
    meta = pd.DataFrame(rows, columns=keys)

    blocks: list[pd.DataFrame] = []
    for f, _ in level_maps:
        if f.kind == "numeric":
            blocks.append(meta[[f.key]].astype(float).rename(columns={f.key: f"num__{f.key}"}))
            continue

        table = chem_tables[f.key]
        id_col = f.id_column
        joined = meta[[f.key]].merge(
            table.rename(columns={id_col: f.key}),
            on=f.key,
            how="left",
            validate="many_to_one",
        )
        if joined.isna().any().any():
            raise ValueError(f"因子 {f.key}: 存在无法匹配描述符/水平的 molecule_id")

        if f.encoding == "descriptor":
            feat_cols = [c for c in table.columns if c != id_col]
            part = joined[feat_cols].copy()
            part.columns = [f"desc__{f.key}__{c}" for c in feat_cols]
            blocks.append(part)
        else:
            cats = table[id_col].astype(str).tolist()
            ohe = pd.get_dummies(joined[f.key].astype(str), prefix=f"ohe__{f.key}")
            full_cols = [f"ohe__{f.key}_{c}" for c in cats]
            ohe = ohe.reindex(columns=full_cols, fill_value=0)
            blocks.append(ohe.astype(float))

    domain_num = pd.concat(blocks, axis=1)
    domain_num.index = meta.index

    info = {
        "domain_size": domain_size,
        "n_factors": len(factors),
        "n_features": domain_num.shape[1],
        "level_sizes": {f.key: n for (f, _), n in zip(level_maps, sizes)},
    }
    return meta, domain_num, info


def history_to_results(
    history: pd.DataFrame,
    meta: pd.DataFrame,
    domain_num: pd.DataFrame,
    factors: list[FactorSpec],
    target_col: str,
) -> pd.DataFrame:
    """将历史表映射到 domain 行，得到 BO 所需 results（特征 + 目标）。"""
    factor_key_list = [f.key for f in factors]
    if history is None or history.empty:
        return pd.DataFrame(columns=list(domain_num.columns) + [target_col])
    if target_col not in history.columns:
        raise ValueError(f"历史表缺少目标列: {target_col}")

    for k in factor_key_list:
        if k not in history.columns:
            raise ValueError(f"历史表缺少因子列: {k}")

    key_to_idx = {row_key(meta.loc[i], factors): i for i in meta.index}

    rows = []
    for _, r in history.iterrows():
        k = row_key(r, factors)
        idx = key_to_idx.get(k)
        if idx is None:
            raise ValueError(f"历史条件不在搜索域内: {dict(r[factor_key_list])}")
        feat = domain_num.loc[idx].copy()
        feat[target_col] = float(r[target_col])
        rows.append(feat)

    return pd.DataFrame(rows)


def sanitize_for_gp(
    domain_num: pd.DataFrame,
    results: pd.DataFrame,
    target_col: str,
) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    """去掉全域常数列，并对特征做基于 domain 的标准化。"""
    num_cols = list(domain_num.columns)
    keep = []
    for c in num_cols:
        if domain_num[c].nunique(dropna=False) > 1:
            keep.append(c)
    if not keep:
        raise ValueError("清洗后无可用特征列，请检查描述符")

    domain = domain_num[keep].astype(float).copy()
    res = results[keep + [target_col]].astype(float).copy()

    mean = domain.mean()
    std = domain.std(ddof=0).replace(0, 1.0)
    domain = (domain - mean) / std
    res[keep] = (res[keep] - mean) / std
    return domain, res, keep
