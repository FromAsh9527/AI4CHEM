# -*- coding: utf-8 -*-
"""
用官方 Deoxyfluorination 示例数据构建可在本应用中打开的测试工作区。

数据来源::
  edbo/data/deoxyfluorination_example/（复制自上游 edbo-master）

产物::
  workspaces/deoxy_demo/
    config.json
    descriptor_*.csv   # molecule_id = SMILES
    history.csv        # 默认载入 init + round0..roundN
    README.txt

用法（项目根目录）::

    conda activate edbo
    python scripts/build_deoxy_workspace.py
    python scripts/build_deoxy_workspace.py --rounds 2 --max-features 15
    python scripts/build_deoxy_workspace.py --full-descriptors   # 更重、更接近论文
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "data" / "deoxyfluorination_example"
OUT_NAME = "deoxy_demo"

DROP_KEYWORDS = [
    "file_name",
    "entry",
    "vibration",
    "correlation",
    "Rydberg",
    "correction",
    "atom_number",
    "E-M_angle",
    "MEAN",
    "MAXG",
    "STDEV",
]

# 官方 results 列 → 本应用因子 key
COL_MAP = {
    "sulfonyl_fluoride_SMILES_index": "sulfonyl_fluoride",
    "base_SMILES_index": "base",
    "solvent_SMILES_index": "solvent",
    "substrate_concentration_index": "substrate_concentration",
    "sulfonyl_equiv_index": "sulfonyl_equiv",
    "base_equiv_index": "base_equiv",
    "temperature_index": "temperature",
    "yield": "yield",
}

FACTOR_FILES = {
    "sulfonyl_fluoride": "sulfonyl_fluoride_boltzmann_dft.csv",
    "base": "base_boltzmann_dft.csv",
    "solvent": "solvent_dft.csv",
}


def _clean_descriptor(raw: pd.DataFrame, max_features: int | None) -> pd.DataFrame:
    smi_cols = [c for c in raw.columns if "SMILES" in c]
    if not smi_cols:
        raise ValueError("描述符表中找不到 SMILES 列")
    smi = smi_cols[0]
    keep_feats: list[str] = []
    for c in raw.columns:
        if c == smi:
            continue
        if any(k.lower() in c.lower() for k in DROP_KEYWORDS):
            continue
        if not pd.api.types.is_numeric_dtype(raw[c]):
            continue
        if raw[c].nunique(dropna=False) <= 1:
            continue
        keep_feats.append(c)

    if max_features is not None and len(keep_feats) > max_features:
        # 按方差取前 max_features 列，控制域矩阵体积
        var = raw[keep_feats].var(numeric_only=True).sort_values(ascending=False)
        keep_feats = list(var.head(max_features).index)

    out = raw[[smi] + keep_feats].copy()
    out = out.rename(columns={smi: "molecule_id"})
    out["molecule_id"] = out["molecule_id"].astype(str)
    out = out.drop_duplicates(subset=["molecule_id"])
    return out


def _load_official_history(n_rounds: int) -> pd.DataFrame:
    """n_rounds: 在 init 之后再并入多少个 round*.csv（0 表示仅 init）。"""
    files = ["init"] + [f"round{i}" for i in range(n_rounds)]
    parts = []
    for name in files:
        path = EXAMPLE / "results" / f"{name}.csv"
        if not path.is_file():
            raise FileNotFoundError(path)
        df = pd.read_csv(path, index_col=0)
        parts.append(df)
    hist = pd.concat(parts, axis=0)
    hist = hist.rename(columns=COL_MAP)
    need = list(COL_MAP.values())
    missing = [c for c in need if c not in hist.columns]
    if missing:
        raise ValueError(f"官方结果缺列: {missing}")
    hist = hist[need].copy()
    for c in ("sulfonyl_fluoride", "base", "solvent"):
        hist[c] = hist[c].astype(str)
    return hist.reset_index(drop=True)


def build_config() -> dict:
    return {
        "schema_version": 1,
        "template": "condition_optimization",
        "source": "edbo/data/deoxyfluorination_example (复制自上游 edbo-master)",
        "target_column": "yield",
        "batch_size": 5,
        "acquisition_function": "EI",
        "training_iters": 100,
        "noise_constraint": 0.01,
        "domain_cap": 2500,
        "factors": [
            {
                "key": "sulfonyl_fluoride",
                "kind": "chemical",
                "encoding": "descriptor",
                "id_column": "molecule_id",
            },
            {
                "key": "base",
                "kind": "chemical",
                "encoding": "descriptor",
                "id_column": "molecule_id",
            },
            {
                "key": "solvent",
                "kind": "chemical",
                "encoding": "descriptor",
                "id_column": "molecule_id",
            },
            {
                "key": "substrate_concentration",
                "kind": "numeric",
                "numeric_mode": "list",
                "values": [0.1, 0.2, 0.3, 0.4, 0.5],
            },
            {
                "key": "sulfonyl_equiv",
                "kind": "numeric",
                "numeric_mode": "list",
                "values": [1.1, 1.3, 1.5, 1.7, 1.9],
            },
            {
                "key": "base_equiv",
                "kind": "numeric",
                "numeric_mode": "list",
                "values": [1.1, 1.3, 1.5, 1.7, 1.9],
            },
            {
                "key": "temperature",
                "kind": "numeric",
                "numeric_mode": "list",
                "values": [20, 30, 40, 50, 60],
            },
        ],
    }


def main():
    parser = argparse.ArgumentParser(description="构建 deoxyfluorination 测试工作区")
    parser.add_argument(
        "--rounds",
        type=int,
        default=0,
        help="除 init 外再并入前 N 个 round 作为历史（默认 0=仅 init）",
    )
    parser.add_argument(
        "--max-features",
        type=int,
        default=20,
        help="每个化学因子最多保留的描述符列数（按方差）；默认 20，适合日常测试",
    )
    parser.add_argument(
        "--full-descriptors",
        action="store_true",
        help="不截断描述符（域矩阵很大，内存/时间显著增加）",
    )
    parser.add_argument(
        "--name",
        default=OUT_NAME,
        help=f"工作区目录名（默认 {OUT_NAME}）",
    )
    args = parser.parse_args()

    if not EXAMPLE.is_dir():
        raise SystemExit(f"找不到官方示例: {EXAMPLE}")

    max_feat = None if args.full_descriptors else max(1, int(args.max_features))
    ws = ROOT / "workspaces" / args.name
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True)

    print(f"构建工作区: {ws}")
    print(f"描述符: {'完整' if max_feat is None else f'每因子最多 {max_feat} 列'}")

    feat_info = {}
    for key, filename in FACTOR_FILES.items():
        raw = pd.read_csv(EXAMPLE / "descriptors" / filename)
        cleaned = _clean_descriptor(raw, max_feat)
        out = ws / f"descriptor_{key}.csv"
        cleaned.to_csv(out, index=False)
        feat_info[key] = {"n_molecules": len(cleaned), "n_features": cleaned.shape[1] - 1}
        print(f"  {key}: {feat_info[key]['n_molecules']} 分子, {feat_info[key]['n_features']} 特征 → {out.name}")

    cfg = build_config()
    cfg["descriptor_info"] = feat_info
    with open(ws / "config.json", "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

    hist = _load_official_history(args.rounds)
    hist.to_csv(ws / "history.csv", index=False)
    print(f"  history: {len(hist)} 条（init + {args.rounds} rounds）")

    readme = f"""Deoxyfluorination 测试工作区
===========================
来源: edbo/data/deoxyfluorination_example（复制自上游 edbo-master）
历史条数: {len(hist)}
描述符: {'full' if max_feat is None else f'top-{max_feat} variance / chem'}
搜索域期望大小: 10 * 10 * 5 * 5 * 5 * 5 * 5 = 312500

在界面中打开项目「{args.name}」：
  conda activate edbo
  streamlit run app.py

或跑自动测试流程:
  python scripts/run_test_flow.py
"""
    (ws / "README.txt").write_text(readme, encoding="utf-8")
    print("完成。")
    print(readme)


if __name__ == "__main__":
    main()
