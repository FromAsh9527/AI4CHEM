# 1. 数据 Schema 与 Metadata

## 设计原则

实验记录以 **长表** 存储；板效应研究优先补齐 metadata，其价值常高于再增加普通条件点。

## 逻辑实体

| 实体 | 含义 |
|---|---|
| `reactions` | 反应模板/反应库（Buchwald–Hartwig、Suzuki、…） |
| `substrates` | 底物或底物对（可拆 electrophile / nucleophile） |
| `plates` | 实验板 / 批次 / 日期 / 仪器状态 |
| `conditions` | 条件向量 \(x\)（催化剂、配体、碱、溶剂、T、t、当量…） |
| `experiments` | 单次观测 \((s,x,p,y,\mathrm{well},\ldots)\) |
| `anchors` | 跨板桥接/标准条件标记 |
| `descriptors` | 底物或条件描述符缓存 |

## 推荐长表列（CSV / ORM 对齐）

| 列 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `experiment_id` | TEXT | ✓ | 唯一 ID |
| `reaction_id` | TEXT | ✓ | 反应模板 |
| `substrate_id` | TEXT | ✓ | 底物/底物对 |
| `plate_id` | TEXT | ✓ | 板/批次 |
| `condition_id` | TEXT | ✓ | 条件编码 |
| `well` | TEXT | | 如 `A01` |
| `row` / `col` | INT | | 孔位 |
| `date` | TEXT | | ISO 日期 |
| `yield` | REAL | ✓ | 主响应（越大越好） |
| `selectivity` | REAL | | 可选第二目标 |
| `replicate` | INT | | 重复编号 |
| `is_anchor` | INT | | 1=桥接条件 |
| `reagent_lot` | TEXT | | 试剂批次 |
| `instrument_id` | TEXT | | 分析仪器 |
| `operator` | TEXT | | 操作者 |
| `quality_flag` | TEXT | | ok / suspect / fail |

条件变量可存 JSON（`condition_json`）或拆列；描述符存独立表按 `entity_id` 连接。

## SQLite

- Schema：`data/db/schema.sql`
- 本地库：`data/db/transferbo2.db`（gitignore）
- 初始化：`python scripts/init_db.py --demo`

## 理想公开数据应满足

1. 同一反应模板  
2. 多个底物  
3. 条件空间基本一致  
4. 各底物有足够条件评估  
5. 有 plate / batch / date / well  
6. 有部分跨板重复（anchor）条件  

若无 plate 信息，应通过实验设计或可控仿真构造跨板设置，而不是仅在算法上假设 batch effect。
