# 公开数据集接入清单

> Demo 库仅用于跑通框架，**不能写论文结论**。真实研究请按本清单接入数据。

## 优先候选

| 数据集 | 反应类型 | 多底物 | 条件空间 | Plate meta | 接入建议 |
|---|---|---|---|---|---|
| Ahneman et al. 2018 BH amination | C–N | 强 | 强 | 弱 | LOSO 主战场；人为划分伪 plate / 日期批次做 LOPO 敏感性 |
| Suzuki HTE（多来源） | C–C | 强 | 强 | 弱 | 与 BH 对照底物泛化 |
| CHAOS 四板添加剂（Science / TransferBO） | 添加剂筛选 | 弱（添加剂≠底物对） | 中 | **强** | LOPO / plate-aware 方法预验证 |
| ORD | 多反应 | 强 | 杂 | 参差 | domain shift 挖掘；需严格过滤同一模板 |
| USPTO 衍生 | 多反应 | 强 | 弱 | 无 | **不推荐**作严格 BO |

## 接入步骤

1. 整理为长表 CSV（列见 `docs/01_data_schema.md`）
2. `python scripts/import_csv_to_db.py --csv ... --replace`
3. 若有描述符：写入 `descriptors` 表或 `data/descriptors/*.csv`
4. `python scripts/audit_plate_effects.py` 确认板效应是否显著
5. `python scripts/run_loso.py --config configs/loso_demo.yaml`（改配置指向真实目标）

## 与既有仓库

- `../TransferBO/data/`：CHAOS / EDBO 描述符与结果可复用
- `../HTEBO/`：湿实验前瞻验证对接点
