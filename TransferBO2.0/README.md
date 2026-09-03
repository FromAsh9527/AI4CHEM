# TransferBO 2.0

**同一反应库下，跨底物 + 跨实验板的贝叶斯优化历史数据安全迁移。**

核心问题：

> 在同一反应模板中，来自不同底物且不同实验板的历史高通量数据，能否在显式校正板间批次效应的前提下，安全迁移到新底物的 BO 过程中，从而提升前期效率并降低负迁移风险？

相对 TransferBO（跨板添加剂筛选 warm-start），本仓库明确同时处理：

1. **跨底物迁移**（substrate transfer）
2. **跨板/批次校正**（plate / batch effect）
3. **低数据序贯优化**（low-data sequential BO）
4. **安全迁移门控**（safe transfer gating）

## 快速开始

```bash
cd TransferBO2.0
python -m venv .venv
# Windows: .\.venv\Scripts\activate
pip install -r requirements.txt
pip install -e .

# 1) 初始化 SQLite 数据库并写入 demo 反应库
python scripts/init_db.py --demo

# 2) 板效应审计（demo）
python scripts/audit_plate_effects.py

# 3) 冒烟：cold-start vs plate-aware transfer
python scripts/run_experiment.py --config configs/smoke.yaml

# 4) Leave-one-substrate-out 小网格
python scripts/run_loso.py --config configs/loso_demo.yaml

# 5) 测试
pytest -q
```

## 目录结构

```text
TransferBO2.0/
├── configs/                 # 实验配置
├── data/
│   ├── raw/                 # 原始 CSV
│   ├── processed/           # 清洗长表
│   ├── db/                  # SQLite（schema + 本地 .db）
│   └── literature/          # 文献集与书目
├── docs/                    # 研究问题、方法矩阵、路线图
├── scripts/                 # CLI 入口
├── src/transferbo2/         # 核心库
│   ├── data/                # DB / oracle / loaders
│   ├── descriptors/         # 底物相似度
│   ├── plate/               # 板效应与 anchor 校正
│   ├── bo/                  # GP + acquisition + loop
│   ├── strategies/          # 基线到 plate-aware / safe-gate
│   ├── metrics/             # BSF / AUC / regret / NTR …
│   └── benchmarks/          # LOSO / LOPO / dual
├── tests/
├── notebooks/
└── results/                 # 运行产物（不入库）
```

## 方法对照（由简到难）

| # | 策略 ID | 说明 |
|---:|---|---|
| 1 | `random` | 随机搜索 |
| 2 | `cold_start` | 仅目标底物 BO |
| 3 | `topk_warm` | 全局历史 Top-k 条件 warm-start |
| 4 | `nearest_topk_warm` | 最近邻底物 Top-k warm-start |
| 5 | `pooled` | 合并历史+目标的 pooled surrogate |
| 6 | `sim_weighted` | 按底物相似度加权迁移 |
| 7 | `contextual` | 条件 × 底物描述符 contextual GP |
| 8 | `plate_aware` | contextual + plate random intercept |
| 9 | `safe_gate` | plate-aware + 响应一致性门控 |

重点比较：

```text
Cold-start  vs  Historical warm-start  vs  Substrate-aware  vs  Plate-aware safe transfer
```

## 数据库

统一长表语义见 `docs/01_data_schema.md`。SQLite schema：`data/db/schema.sql`。

关键实体：`reactions` · `substrates` · `plates` · `conditions` · `experiments` · `anchors` · `descriptors`。

## 文献集

- 书目：`data/literature/bibliography.bib`
- 导读：`data/literature/LITERATURE.md`
- 阅读笔记模板：`data/literature/reading_notes/`

## 研究文档

| 文档 | 内容 |
|---|---|
| [docs/00_research_questions.md](docs/00_research_questions.md) | 问题定义与假设 H1–H4 |
| [docs/01_data_schema.md](docs/01_data_schema.md) | 数据字段与 metadata |
| [docs/02_methods_matrix.md](docs/02_methods_matrix.md) | 方法矩阵与实现映射 |
| [docs/03_evaluation.md](docs/03_evaluation.md) | 指标与 benchmark |
| [docs/04_roadmap.md](docs/04_roadmap.md) | 五阶段研究路线 |

## 与 TransferBO / HTEBO 的关系

| 仓库 | 角色 |
|---|---|
| `TransferBO/` | 既有跨板 warm-start 计算回顾；可作历史对照与数据复用入口 |
| `HTEBO/` | 湿实验闭环（SNAr 等）；前瞻验证可对接 |
| **`TransferBO2.0/`** | **跨底物 + 跨板 + 安全迁移** 的方法学主平台 |

## 建议论文表述

**EN:** Can historical HTE optimisation data from chemically related but non-identical substrates be safely transferred across experimental plates to accelerate Bayesian optimisation for a new substrate?

**ZH:** 在同一反应库中，来自不同底物且不同实验板的历史高通量反应数据，能否在显式校正板间批次效应的前提下，安全地迁移到新底物的贝叶斯优化过程中，从而提升前期优化效率并降低负迁移风险？
