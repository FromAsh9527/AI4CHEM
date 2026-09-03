# 5. 数据角色与语义约定（冻结）

冻结日期：2026-08-20

## 反应集分工

| 角色 | 反应集 | 状态 |
|---|---|---|
| **主集** | EDBO 芳基胺化（Doyle/Ahneman 风格）`edbo_aryl_amination` | **已接入** → `data/db/transferbo2.db` |
| **跨化学对照** | EDBO Suzuki `edbo_suzuki` | **已接入** → `data/db/transferbo2_suzuki.db`（同 OHE+hashed / 同策略；见 `docs/07_experiment_suzuki_v1.md`） |
| 批次轨 | Roche SURF BH（`rxn_date`） | 未接入 |

## 主集字段语义

| 字段 | 含义 | 禁止误解 |
|---|---|---|
| `substrate_id` | 芳基卤底物任务，如 `sub_s1`…`sub_s15`（与 TransferBO 旧分析 ID 连续，含 s4） | — |
| `plate_id` | `logical_{substrate_id}` | **不是**独立物理批次；与底物一一对应 |
| `condition_id` | `candidate_key` = 配体×碱×添加剂 | — |
| `conditions.catalyst` | **本库暂存 `additive_smiles`**（源研究中 Pd 前体固定） | 不是 Pd 催化剂结构 |
| `conditions.ligand` / `base` | 配体 / 碱 SMILES | — |
| `yield` | 源表 `response`（产率%） | — |
| 描述符 | `hashed_smiles_v1`（底物 SMILES 哈希指纹，可后续换 Morgan/DFT） | 非量子化学描述符 |

## 为何这样定

旧 TransferBO 弯路之一是把 EDBO 的 `suz_t*` / `sub_s*` **叫成 plate**，又和 CHAOS 真四板混谈。  
2.0 主集明确：**先做跨底物迁移与安全门控**；真实板/日期效应留给 SURF 轨，不在胺化表上假装存在。

## 接入命令

```bash
python scripts/ingest_amination.py
python scripts/run_experiment.py --config configs/amination_smoke.yaml
```

产物：

- `data/processed/amination_long.csv`
- `data/db/transferbo2.db`
