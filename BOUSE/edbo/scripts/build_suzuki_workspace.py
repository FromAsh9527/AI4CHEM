# -*- coding: utf-8 -*-
"""
用官方 Suzuki 全量数据构建可闭环测试的工作区。

数据来源::
  edbo-master/experiments/data/suzuki/

特点::
  - 搜索域 = 全因子笛卡尔积 = 3696 点
  - experiment_index 覆盖全部 3696 点 → 任意推荐条件都能查到真实 yield

产物::
  workspaces/suzuki_demo/
    config.json
    descriptor_*.csv
    history.csv          # 默认空，或 --seed-n 条随机种子
    oracle.csv           # 全量真值（查表回填用）
    README.txt

用法::

    cd edbo
    python scripts/build_suzuki_workspace.py
    python scripts/build_suzuki_workspace.py --seed-n 10 --seed 0
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
SRC = ROOT / "edbo-master" / "experiments" / "data" / "suzuki"
OUT_NAME = "suzuki_demo"

FACTOR_DFT = {
    "electrophile": ("electrophile_dft.csv", "electrophile_SMILES"),
    "nucleophile": ("nucleophile_dft.csv", "nucleophile_SMILES"),
    "ligand": ("ligand-boltzmann_dft.csv", "ligand_SMILES"),
    "base": ("base_dft.csv", "base_SMILES"),
    "solvent": ("solvent_dft.csv", "solvent_SMILES"),
}

INDEX_COLS = {
    "Electrophile_SMILES": "electrophile",
    "Nucleophile_SMILES": "nucleophile",
    "Ligand_SMILES": "ligand",
    "Base_SMILES": "base",
    "Solvent_SMILES": "solvent",
    "yield": "yield",
}

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
    "stoichiometry",
    "convergence",
]


def _clean_descriptor(raw: pd.DataFrame, smi_col: str, max_features: int | None) -> pd.DataFrame:
    if smi_col not in raw.columns:
        raise ValueError(f"找不到 SMILES 列: {smi_col}")
    keep_feats: list[str] = []
    for c in raw.columns:
        if c == smi_col:
            continue
        if any(k.lower() in c.lower() for k in DROP_KEYWORDS):
            continue
        if not pd.api.types.is_numeric_dtype(raw[c]):
            continue
        if raw[c].nunique(dropna=False) <= 1:
            continue
        keep_feats.append(c)
    if max_features is not None and len(keep_feats) > max_features:
        var = raw[keep_feats].var(numeric_only=True).sort_values(ascending=False)
        keep_feats = list(var.head(max_features).index)
    out = raw[[smi_col] + keep_feats].copy()
    out = out.rename(columns={smi_col: "molecule_id"})
    out["molecule_id"] = out["molecule_id"].astype(str)
    return out.drop_duplicates(subset=["molecule_id"]).reset_index(drop=True)


def load_oracle() -> pd.DataFrame:
    raw = pd.read_csv(SRC / "experiment_index.csv")
    out = raw.rename(columns=INDEX_COLS)[list(INDEX_COLS.values())].copy()
    for c in ("electrophile", "nucleophile", "ligand", "base", "solvent"):
        out[c] = out[c].astype(str)
    out["yield"] = out["yield"].astype(float)
    return out.drop_duplicates(
        subset=["electrophile", "nucleophile", "ligand", "base", "solvent"]
    ).reset_index(drop=True)


def build_config(feat_info: dict) -> dict:
    return {
        "schema_version": 1,
        "template": "suzuki_coupling",
        "source": "edbo-master/experiments/data/suzuki",
        "target_column": "yield",
        "batch_size": 5,
        "acquisition_function": "EI",
        "training_iters": 100,
        "noise_constraint": 0.01,
        "domain_cap": 4000,
        "factors": [
            {"key": k, "kind": "chemical", "encoding": "descriptor", "id_column": "molecule_id"}
            for k in FACTOR_DFT
        ],
        "descriptor_info": feat_info,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="构建 Suzuki 测试工作区")
    parser.add_argument("--name", default=OUT_NAME)
    parser.add_argument("--max-features", type=int, default=15)
    parser.add_argument("--full-descriptors", action="store_true")
    parser.add_argument("--seed-n", type=int, default=0, help="随机写入历史的条数（0=空历史）")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    if not SRC.is_dir():
        raise SystemExit(f"找不到 Suzuki 数据: {SRC}")

    max_feat = None if args.full_descriptors else max(1, int(args.max_features))
    ws = ROOT / "workspaces" / args.name
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True)

    print(f"构建工作区: {ws}")
    feat_info = {}
    for key, (fname, smi_col) in FACTOR_DFT.items():
        cleaned = _clean_descriptor(pd.read_csv(SRC / fname), smi_col, max_feat)
        cleaned.to_csv(ws / f"descriptor_{key}.csv", index=False)
        feat_info[key] = {"n_molecules": len(cleaned), "n_features": cleaned.shape[1] - 1}
        print(f"  {key}: {feat_info[key]}")

    oracle = load_oracle()
    oracle.to_csv(ws / "oracle.csv", index=False)
    print(f"  oracle: {len(oracle)} 条（全空间真值）")

    keys = list(FACTOR_DFT.keys())
    if args.seed_n > 0:
        rng = np.random.default_rng(args.seed)
        n = min(int(args.seed_n), len(oracle))
        idx = rng.choice(len(oracle), size=n, replace=False)
        hist = oracle.iloc[sorted(idx)].reset_index(drop=True)
    else:
        hist = pd.DataFrame(columns=keys + ["yield"])

    hist.to_csv(ws / "history.csv", index=False)
    print(f"  history: {len(hist)} 条")

    cfg = build_config(feat_info)
    with open(ws / "config.json", "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

    readme = f"""Suzuki 闭环测试工作区
====================
来源: edbo-master/experiments/data/suzuki
搜索域: 4×3×11×7×4 = 3696（与 oracle 一一对应）
历史: {len(hist)} 条
描述符: {'full' if max_feat is None else f'top-{max_feat} / chem'}

用法:
  1. streamlit run app.py → 打开项目 {args.name}
  2. 步骤3 推荐（无历史用无模型；有历史用 BO）
  3. 查表回填（不用做实验）:
       python scripts/oracle_backfill.py --project {args.name}
     会根据 last_recommendations.csv 从 oracle.csv 填 yield，并写入历史

或在物料包中手动操作，见 ../../manual_test_kit/README.md
"""
    (ws / "README.txt").write_text(readme, encoding="utf-8")
    print("完成。")
    print(readme)


if __name__ == "__main__":
    main()
