# 四板添加剂 HTE 数据说明（计划书 §4）

## 目标表结构

清洗后统一为：

| 列 | 含义 |
|---|---|
| `additive_id` | 添加剂标识 |
| `smiles` | 规范化 SMILES |
| `plate_id` | 反应板 ID（如 plate_1 … plate_4） |
| `response` | UV210 product area 或归一化响应（越大越好） |

输出路径：`data/processed/additives_four_plates.csv`

## 获取方式（择一）

1. **原文补充材料**  
   Prieto Kullmer et al., *Science* — DOI: https://doi.org/10.1126/science.abn1885

2. **CHAOS 仓库**（推荐，常附带处理脚本）  
   https://github.com/schwallergroup/chaos  
   ```bash
   git clone https://github.com/schwallergroup/chaos.git third_party/chaos
   ```
   将导出的板级 CSV/TSV 放入 `data/raw/`，然后：
   ```bash
   python scripts/prepare_data.py --raw data/raw --out data/processed/additives_four_plates.csv
   ```

3. **流水线冒烟（无外网数据时）**  
   ```bash
   python scripts/prepare_data.py --demo
   ```
   生成合成四板数据，仅用于跑通框架，不可用于论文结论。

## 目录约定

- `data/raw/` — 原始下载（不入库）
- `data/processed/` — 清洗后的统一表（不入库）
- `data/descriptors/` — 描述符特征表（**可入库**，便于 GitHub 复现）

### 导出描述符表

```bash
# 需先有 data/processed/additives_four_plates.csv
# xTB 表可选：python scripts/prepare_chaos_xtb.py
python scripts/export_descriptor_tables.py
```

产出（CHAOS）：

| 文件 | 键 | 说明 |
|---|---|---|
| `chaos_morgan_r2_n2048.csv` | `smiles` | Morgan/ECFP radius=2, 2048 bits |
| `chaos_fragprint_r2_n2048.csv` | `smiles` | Morgan \|\| RDKit FP |
| `chaos_ohe_smiles.csv` / `chaos_ohe_vocab.csv` | `smiles` | 全库 720 维 OHE（存档；运行时 OHE 可能只 fit 子集） |
| `chaos_drfp_n2048.csv` | `reaction_smiles` | 每行一条反应（2880） |
| `chaos_xtb_gfn2.csv` | `smiles` | BOUSE GFN2-xTB（从 processed 复制） |
| `MANIFEST.csv` | — | 文件大小清单 |

## 第二阶段外部验证（可选）

Zenodo SURF：https://doi.org/10.5281/zenodo.18185850
