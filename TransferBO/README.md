# TransferBO

跨反应板 **Transfer / Warm-start Bayesian Optimisation**（纯计算回顾性模拟）。

对应计划书：[`方向三-TransferBO纯计算方案.md`](./方向三-TransferBO纯计算方案.md)

> 在公开多反应板 HTE 数据上，系统检验：反应板 A 的结果能否帮助板 B 用更少查询找到高响应条件？何种表示与迁移策略更有效？何时负迁移？

## 项目结构

```text
TransferBO/
├── configs/                 # 实验超参（初始点、预算、种子、网格）
├── data/
│   ├── raw/                 # 原始 CSV（可入库；超大表除外）
│   ├── processed/           # 清洗后的板级表（可入库）
│   ├── descriptors/         # 描述符特征表（可入库）
│   └── README.md
├── scripts/                 # 准备数据 / 跑网格 / 汇总作图
├── src/transferbo/          # GP–EI、策略、表示、指标
├── tests/
├── results/                 # 运行 JSON（本地，不入库）
├── exports/                 # HPC/离线包（本地，不入库）
└── docs/                    # 文稿与汇报（本地，不入库）
```

## 快速开始

```bash
# 1. 环境
conda create -n transferbo python=3.10 -y
conda activate transferbo
pip install -r requirements.txt
pip install -e .

# 2. 数据（真实数据放入 data/raw/；或先用 demo）
python scripts/prepare_data.py --demo

# 3. 单板 cold-start 冒烟
python scripts/run_experiment.py --config configs/default.yaml --strategy cold_start --target plate_1 --seed 0

# 4. label warm-start 原型：板1 → 板2
python scripts/run_experiment.py --config configs/default.yaml \
  --strategy label_warm --source plate_1 --target plate_2 --seed 0

# 5. 跑测试
pytest -q
```

## 计划书对齐

| 计划书项 | 本仓库落点 |
|---|---|
| 4 类策略 | `strategies/`: cold_start, diversity_warm, label_warm, multitask |
| 3 类表示 | `representations/`: ohe, morgan, fragprint（drfp 可选） |
| 预算 50/100、init 10/20、EI、≥20 种子 | `configs/*.yaml` |
| Best-so-far / top-5% / 迁移热图 | `metrics/` + `run_transfer_grid.py` |
| 第 1–2 周基线 | `configs/baseline.yaml` |
| 第 3–5 周主实验 | `configs/transfer_grid.yaml` |

## 本周可做（计划书 §9）

1. clone CHAOS，按其脚本导出四板 → `data/raw/`
2. `python scripts/prepare_data.py` 得到统一 CSV
3. 单板 GP+EI 打通（`run_experiment.py --strategy cold_start`）
4. warm-start 原型（`--strategy label_warm --source … --target …`）
5. 固定网格配置，开始积 `results/`

## 技术栈

Python · RDKit · scikit-learn GP（默认，`bo.backend: sklearn`）

可选 BoTorch 后端：

```bash
pip install -r requirements-botorch.txt
# 然后在 configs 中设 bo.backend: botorch
```

## 建议题目

**Transfer and warm-start Bayesian optimisation across related additive-screening plates: when do molecular representations help?**
