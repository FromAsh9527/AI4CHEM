# 4. 五阶段研究路线

## 阶段 1 — 数据审计与效应拆解

- 跨板重复条件差异
- 板内/板间方差分解
- PCA/UMAP 看板聚类
- mixed-effects：`y ~ condition + substrate + plate`
- 交互：`y ~ condition * plate`
- 跨板条件排序相关性

脚本：`scripts/audit_plate_effects.py`

## 阶段 2 — 可靠基线

实现并固定：`random` / `cold_start` / `topk_warm` / `nearest_topk_warm` / `pooled` / `sim_weighted`。

回答：历史数据有没有用？最简单方法是否已足够好？

## 阶段 3 — Contextual / Multi-task + plate

优先 \(f(x,\phi(s))+b_p\)；比较 AUC、threshold attainment、NTR。

## 阶段 4 — 安全迁移与主动校准

Anchor、source selection、transfer gating、动态权重。

## 阶段 5 — 真实前瞻验证

与 `HTEBO/` 对接：相似 / 中等 / OOD 底物各 2–3 个，不同板/日期执行。

## Demo 数据角色

`scripts/init_db.py --demo` 生成的合成库用于框架跑通与单元测试，**不可作为论文结论**。公开或自有 HTE 数据接入后替换 `data/processed/` 并重新 `import_csv_to_db.py`。
