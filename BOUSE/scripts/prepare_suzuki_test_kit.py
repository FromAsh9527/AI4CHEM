# -*- coding: utf-8 -*-
"""
从 EDBO 官方 Suzuki 数据整理手动测试物料（支持推荐→查表回填）。

数据::
  edbo/data/suzuki/（复制自上游 edbo-master）

产物::
  BOUSE/manual_test_kit/

用法::

    cd BOUSE
    python scripts/prepare_suzuki_test_kit.py
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pandas as pd

BOUSE = Path(__file__).resolve().parents[1]
EDBO = BOUSE / "edbo"
SRC = EDBO / "data" / "suzuki"
KIT = BOUSE / "manual_test_kit"
MAX_FEATURES = 15

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


def _clean_descriptor(raw: pd.DataFrame, smi_col: str, max_features: int) -> pd.DataFrame:
    keep_feats = []
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
    if len(keep_feats) > max_features:
        var = raw[keep_feats].var(numeric_only=True).sort_values(ascending=False)
        keep_feats = list(var.head(max_features).index)
    out = raw[[smi_col] + keep_feats].copy()
    out = out.rename(columns={smi_col: "molecule_id"})
    out["molecule_id"] = out["molecule_id"].astype(str)
    return out.drop_duplicates(subset=["molecule_id"]).reset_index(drop=True)


def main() -> None:
    if not SRC.is_dir():
        raise SystemExit(f"找不到 Suzuki 数据: {SRC}")

    if KIT.exists():
        shutil.rmtree(KIT)

    d_mol = KIT / "01_molecules"
    d_raw = KIT / "02_raw_dft"
    d_ready = KIT / "03_ready_descriptors"
    d_oracle = KIT / "04_oracle"
    d_ref = KIT / "05_reference_workspace"
    for d in (d_mol, d_raw, d_ready, d_oracle, d_ref):
        d.mkdir(parents=True)

    # molecules
    for key, (fname, smi_col) in FACTOR_DFT.items():
        raw = pd.read_csv(SRC / fname)
        out = pd.DataFrame(
            {
                "molecule_id": raw[smi_col].astype(str).str.strip(),
                "smiles": raw[smi_col].astype(str).str.strip(),
            }
        ).drop_duplicates("molecule_id")
        out.to_csv(d_mol / f"{key}_molecules.csv", index=False)
        print(f"01 {key}: {len(out)}")

    # raw dft
    for key, (fname, _) in FACTOR_DFT.items():
        shutil.copy2(SRC / fname, d_raw / fname)
        print(f"02 {fname}")

    # ready descriptors
    for key, (fname, smi_col) in FACTOR_DFT.items():
        cleaned = _clean_descriptor(pd.read_csv(SRC / fname), smi_col, MAX_FEATURES)
        path = d_ready / f"descriptor_{key}.csv"
        cleaned.to_csv(path, index=False)
        print(f"03 {path.name}: {len(cleaned)} x {cleaned.shape[1]-1}")

    # oracle = full experiment_index with app column names
    oracle = pd.read_csv(SRC / "experiment_index.csv").rename(columns=INDEX_COLS)
    oracle = oracle[list(INDEX_COLS.values())].copy()
    for c in ("electrophile", "nucleophile", "ligand", "base", "solvent"):
        oracle[c] = oracle[c].astype(str)
    oracle.to_csv(d_oracle / "experiment_index.csv", index=False)
    # seed history sample
    seed = oracle.sample(n=10, random_state=0).reset_index(drop=True)
    seed.to_csv(d_oracle / "seed_history_10.csv", index=False)
    print(f"04 oracle: {len(oracle)} rows; seed_history_10: {len(seed)}")

    hint = {
        "reaction": "Suzuki",
        "suggested_project_name": "suzuki_demo",
        "target_column": "yield",
        "chemical_factors": list(FACTOR_DFT.keys()),
        "domain_size": 4 * 3 * 11 * 7 * 4,
        "oracle_coverage": "full (every domain point has yield)",
        "source": "edbo/data/suzuki (复制自上游 edbo-master)",
    }
    (d_ref / "project_hint.json").write_text(
        json.dumps(hint, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    readme = """# 手动测试物料包（Suzuki）

数据来源：`edbo/data/suzuki/`（复制自上游 edbo-master）

**与 Deoxy 物料的关键区别**：这里的 `04_oracle/experiment_index.csv` 覆盖
**全部 3696 个搜索域点**。因此：界面推荐出什么条件，都能查到真实产率回填，
**不要求**推荐结果碰巧等于某几轮论文条件。

---

## 目录

| 文件夹 | 用途 |
|--------|------|
| `01_molecules/` | SMILES → 描述符界面生成 |
| `02_raw_dft/` | 原始 DFT → 清洗 |
| `03_ready_descriptors/` | 已洗好，直接导入 EDBO |
| `04_oracle/` | 全量真值表 + 可选种子历史 |
| `05_reference_workspace/` | 项目提示 |

因子 key：`electrophile` / `nucleophile` / `ligand` / `base` / `solvent`  
域大小：4 × 3 × 11 × 7 × 4 = **3696**

---

## 推荐手动流程（严格闭环模拟）

### 0. 一键准备项目（推荐）

```bash
cd edbo
python scripts/build_suzuki_workspace.py --seed-n 0
# 或带 10 条种子历史再开 BO：
# python scripts/build_suzuki_workspace.py --seed-n 10 --seed 0
```

然后双击 `start_bouse.bat`，EDBO 打开项目 **`suzuki_demo`**。

### 1. 界面操作

1. 步骤2：确认 5 个化学因子描述符已就绪（构建脚本已写好）
2. 步骤3：
   - 无历史 → **无模型选点**
   - 有历史 → **贝叶斯优化**
3. 步骤4（查表回填，不做实验）：在 `edbo` 目录执行

```bash
python scripts/oracle_backfill.py --project suzuki_demo
```

会读取本轮推荐，从 `oracle.csv` 填 `yield`，写入 `history.csv`。

4. 回到步骤3 再推荐 → 再 `oracle_backfill` → 循环

### 2. 纯手动（不用脚本）

1. 新建项目，因子 key 与上表一致  
2. 导入 `03_ready_descriptors/descriptor_*.csv`  
3. 可选：步骤4 先上传 `04_oracle/seed_history_10.csv`  
4. 推荐后，用推荐里的 SMILES 组合在 `04_oracle/experiment_index.csv` 中筛选对应 `yield`，做成回填 CSV 上传

---

## 自动化自检

```bash
cd edbo
python scripts/build_suzuki_workspace.py --seed-n 0
python scripts/run_suzuki_test_flow.py
```
"""
    (KIT / "README.md").write_text(readme, encoding="utf-8")
    print(f"\nDone: {KIT}")


if __name__ == "__main__":
    main()
