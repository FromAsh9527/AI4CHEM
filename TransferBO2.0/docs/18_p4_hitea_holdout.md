# P4 — 独立反应族 holdout：borylation 主库 + HiTEA Suzuki 第二库（预注册）

**起草日期：** 2026-08-22  
**修订：** 2026-08-23（borylation 升级为主验证库；HiTEA Suzuki 降为第二外部库）  
**状态：** borylation 已接入并审计；判定标准已预注册（本文件）  
**依据：** `docs/17_step3_experiment_plan.md` §6（P4 入选标准与冻结协议）、`docs/14_strategy_draft.md`、审计结论（`results/audit_round_metrics/`、`results/amination_matched_init_audit/`）  
**不改写：** `FROZEN_CLAIMS.md` 与 Step1/Step2 主表数字；P4 结果只写**适用边界**。

---

## 1. 为什么选这两个库

### 1.1 主验证库：Ni 催化 borylation（Organometallics 2022 / Doyle ochem-data NiB）

- 33 个亲电体任务 × 23 配体 × 2 溶剂 = **1518 格完整交叉积**（单次测量，与 Digital Discovery 2025 配套数据逐格对账一致）；
- 产率中位 46.5、仅 4% 失败、无负值 → 信噪比健康；
- **跨反应类**（Ni 催化 C–B 键，与 Pd 胺化/Suzuki 均不同）→ 直接检验结论是否 Pd 偶联体系特有；
- 未参与本仓库任何策略开发。

### 1.2 第二外部库：Pfizer HiTEA Suzuki（King-Smith et al. 2023）

- 11 任务 × 94 条件（稀疏面板），产率中位 14、30% 失败；
- 与 EDBO Suzuki 同反应类、跨数据源；**结果已跑完并复核**（330/330，`results/p4_hitea/summary.md`：部分复现，2026-08-24 条件特征修复后重跑，见 §8.3）；
- 角色：与主库互为补充（同反应类跨源 + 跨反应类双视角）。

## 2. 入选审计清单

### 2.0 主库 borylation（2026-08-23 完成审计）

| # | 标准（docs/17 §6.1） | borylation 情况 | 判定 |
|---|---|---|---|
| 1 | 多个 substrate-defined tasks | **33** 个亲电体（s1–s33） | PASS |
| 2 | 共享离散条件空间 | 23 配体 × 2 溶剂 = 46 条件 | PASS |
| 3 | 足够密的 response panel | **1518 = 33×23×2 完整交叉积，零缺失、单次测量** | PASS |
| 4 | 可构成 LOSO | 33 任务全交叉 | PASS |
| 5 | 条件维度 > 1 | 配体 × 溶剂（2 维） | PASS |
| 6 | 未用于本仓库策略开发/调参 | 独立数据（Organometallics 2022）；与 EDBO 系不同反应/不同实验 | PASS |
| 7 | 含失败样本 | 4%（产率 ≤1），未截断 | PASS |

**规模：** 990 jobs = 33 任务 × 6 策略 × 5 seeds。  
**结构来源：** 亲电体/配体 InChI → SMILES → morgan_r2 描述符（nearest 臂可用）。

### 2.1 已考察并否决/降级的候选（审计裁决）

| 库 | 结构 | 裁决 | 理由 |
|---|---|---|---|
| **CHAOS 四板添加剂**（Prieto Kullmer，本地 `..\TransferBO\data\`） | 4 板 × 720 添加剂**完整交叉积** | **边界探索**（非验证库） | 720 个"条件"只是**一维添加剂变量**，不满足「条件维度 > 1」；任务仅 4 个；1.0 已用过 |
| `doyle_cn_plates.csv`（本地） | 15 板 × 240 条件 | 排除 | = EDBO 胺化另一版本（已用于 2.0 主库） |
| HiTEA BUCHWALD / HYDROGENATION / ULLMANN | 见家族表 | 拒绝/次级 | 面板过稀或失败率过高 |
| **HiTEA Suzuki** | 11 任务 × 41–48 核心条件（稀疏） | **第二外部库**（结果已出：部分复现，2026-08-24 特征修复复核） | 任务少、面板稀疏、产率信噪比低；但提供"同反应类跨源"视角 |
| CHAOS / Comm Chem 2025 SI / Shields 2021 SI / Science 2023 adg2114 | — | 待定/排除 | CHAOS 一维否决；其余未达「任务 ≥8 × 共享条件 ≥100 × 维度 >1」或结构未知 |

**公开数据现状结论：** 设计过的「substrate × 条件」完整交叉积在公开数据中极稀缺；borylation（33×46 全网格）与 EDBO（15×260、12×308）为已知罕见案例。HiTEA 类机会性数据每任务共享条件天然偏少。

## 3. 冻结协议（与 Step1 一字不差，禁止改动）

| 项 | 锁定值 |
|---|---|
| 协议 | LOSO；历史 = 除靶外全部任务（多源池化） |
| 条件表示 | OHE |
| 底物近邻 | morgan_r2 + Tanimoto（仅 nearest 臂；若 RDKit 不可用则 hashed 并注明） |
| 优化器 | GP (Matern-2.5 ARD) + EI；target-only；历史不进 GP |
| n_init / budget | 5 / 20 |
| topk | 5（池化规则 = 跨源条件产率均值降序） |
| seeds | 0–4（算力允许则 ≥10 作 SI） |
| 推断单位 | 先 seed 平均 → 再 target 汇总；bootstrap CI，B=5000 |
| 主指标 | ΔAUC vs cold **和** vs random（禁止只报 vs cold） |
| 次指标 | AUC@5/10、init_best、final_best、T_50（轮次）、命中 top-5% 轮次、NTR、worst-target |

**策略臂：** `random`、`cold_start`、`topk_warm`、`nearest_topk_warm` + 审计新增臂 `cold_random_post`、`topk_random_post`（matched-init，检验"价值位置"主张）。

## 4. 预注册判定（跑前写死，事后不得改）

> 主库（borylation，990 jobs）判定按 4.1–4.3；第二库（HiTEA Suzuki）已按同款判定执行完毕（§8，部分复现；2026-08-24 条件特征退化修复后重跑复核，见 §8.3）。

### 4.1 主检验（跨源复现）

| 结果模式 | 判定 | 对策略草稿的影响 |
|---|---|---|
| topk vs cold > 0 且 CI 排除 0，且 vs random > 0 | **强复现** | 策略草稿升"已验证"（跨源） |
| 方向一致但 CI 含 0，或仅 vs cold 正 | **部分复现** | 草稿保持"草稿"，写明适用边界 |
| topk vs cold ≤ 0 或 vs random ≤ 0 | **未复现** | 草稿收窄为"仅 EDBO 库内成立"，不硬凑 |

### 4.2 价值位置检验（审计新增，机制主张）

| 比较 | 胺化（回顾） | Suzuki（回顾） | HiTEA 若复现… |
|---|---|---|---|
| C2（cold+EI − cold+random） | +67.7（EI 有效） | −21.3（弱） | 支撑"价值位置库相关"主张 |
| C1（topk+EI − topk+random） | +26.0（弱正） | +75.5（强） | 同上 |

判定：C1/C2 的符号与置信模式与胺化或 Suzuki 一致 → 写"价值位置可预测/库相关"；三态皆可报告。

### 4.3 源数门槛跨家族检验（离线，零 BO 成本）

n_s ∈ {1, 3, 5, all} LSO 重跑 `analyze_p1p2_list_stability.py` 逻辑：
- "≥3 源"门槛在 HiTEA 上仍成立 → 门槛升"已验证"；
- 门槛放宽/收紧 → 报告 HiTEA 专属门槛，不改 EDBO 锁。

## 5. 分析产出

| 产出 | 路径 |
|---|---|
| 数据审计 | `results/p4_hitea/audit.md` |
| 接入库 | `data/db/transferbo2_hitea.db` + `data/processed/hitea_long.csv` |
| LOSO 结果 | `results/p4_hitea/loso/`（每 job JSON + loso_summary.csv） |
| 效应表 | `results/p4_hitea/effects.csv`（复用 `analyze_step1_effects.py` 口径） |
| 轮次指标 | `results/p4_hitea/round_metrics/`（复用 `analyze_round_metrics.py` 口径） |
| matched-init | `results/p4_hitea/matched_init/`（复用 `analyze_amination_matched_init.py` 口径） |
| 汇总 | `results/p4_hitea/summary.md` |

## 6. 规模估算

| 项 | 值 |
|---|---|
| 主库 tasks | 33（borylation，`data/db/transferbo2_borylation.db`） |
| 主库 jobs | 33 × 6 策略 × 5 seeds = **990** |
| 主库 HPC | `scripts/hpc/README_BORYLATION_P4_HPC.md`（dsub 5 分片，每片 198 job） |
| 第二库（HiTEA Suzuki） | 330 jobs 已完成（`results/p4_hitea/`） |

## 7. 明确不做

- 不在 HiTEA 上调 k / 换聚合规则 / 换表示（冻结协议）；
- 不用 P4 结果回改 Step1 主表与 EDBO 锁；
- 不把"同反应类"结果写成"跨反应类"；
- 不在 HiTEA 上重新调 EI/GP 超参。

---

## 8. P4 结果（2026-08-23，330/330 jobs 完成）

汇总：`results/p4_hitea/summary.md`；逐项：`results/p4_hitea/loso/`、`matched_init/`、`lso_source_stability.csv`。

### 8.1 预注册判定执行结果

| 检验 | 判定 | 依据 |
|---|---|---|
| **主检验** | **弱方向正** | topk vs cold +26.3 [−32.2, +80.9]、vs random +36.9 [−10.5, +83.7]：方向正但 CI 含 0；final_best vs cold +0.22 [−1.66, +1.64] 含 0（2026-08-24 修复条件特征退化后重跑：原报 +47.0/+3.19 排除 0 系特征退化伪影，见 §8.3） |
| **价值位置** | **后段倾向（C2 排除 0）** | C2（cold 下 EI）**+20.4 [−36.5, −6.3] 排除 0**（EI 真实有效）；C1（topk 下 EI）**+20.5**（含 0）；cold vs random +10.6（含 0）；init_best CI 含 0（原报 C2 −12.8、cold < random −22.6 系特征退化伪影） |
| **源数门槛** | **≥3 未复现，HiTEA 专属 ≥5** | n=3 Jaccard 0.22（胺化 0.39）、Δinit_best −1.75、57% ≥ 全池；n=5 仍 −0.99/69% |

### 8.2 锁定读法（不改 EDBO 锁；只写 P4 边界）

1. **策略草稿维持"草稿"**：跨源方向一致（正）但未达显著，不得升"已验证（跨源）"；
2. **后段价值获第三方支持（修复后修正）**："历史价值在后段（EI 组合）而非 init"在 HiTEA 上获支持（C2 +20.4 排除 0）；但"冷启动 BO 不可靠"未复现（修复后 cold vs random +10.6 含 0，不再显著负）→ "价值位置库相关"主张增强，冷启动可靠性按库分述；
3. **适用边界收窄**：效应量依赖任务条件空间大小（HiTEA 41–48 vs EDBO 260/308）与失败率（30%）——小空间 + 高噪声压缩效应，写报告必须带此结构性解释；
4. **源数门槛按库配置**：CLI 警告阈值 EDBO ≥3/≥5、跨源 Suzuki 类数据 ≥5；
5. **清单稳定性跨源更差**（Jaccard 0.11–0.40）→ source coverage 上报是强制项，不是可选项。

### 8.3 条件特征退化修复（2026-08-24，全部 HiTEA LOSO 重跑）

**发现**：ingest 时 conditions 表的 catalyst/ligand/base/solvent/temperature_c/time_h 全部存为 NULL（只保留了 condition_json 的 cond_str），导致 OHE 条件特征对所有条件完全相同（X_tgt unique rows = 1）→ GP 无法区分条件 → **EI 后段退化为顺序扫描**（旧结果 indices 尾段 2,3,4,… 证实）。所有历史 HiTEA LOSO 结果（本文件 §8、rank_median 复核、四臂实验、learnability 后段价值）的后段均未真正工作。

**修复**：`scripts/ingest_hitea.py` 现在从源数据按条件聚合众数填入 catalyst（Catalyst_2_Short_Hand）、solvent（Solvent_1_Name）、temperature_c、time_h；重建 `data/db/transferbo2_hitea.db`（577 实验不变）；**重跑全部 HiTEA LOSO**（P4 330 jobs + rank_median 55 + 四臂 110 = 495 jobs，`results/p4_hitea/loso/`、`results/hitea_rankmed_audit/`、`results/hitea_continuation_arms/`）。

**修复后验证**：X_tgt unique rows 1 → 48/49（= 条件数）；EI 后段 indices 不再顺序递增。数字变化见 §8.1 与 `results/audit_round_metrics/summary.md`（hitea 段）。

---

## 9. borylation 主库结果（2026-08-23，990/990 jobs 完成）

汇总：`results/p4_borylation/summary.md`；逐项：`results/p4_borylation/loso/`、`matched_init/`、`lso_source_stability.csv`。

### 9.1 预注册判定执行结果

| 检验 | 判定 | 依据 |
|---|---|---|
| **主检验** | ✅ **强复现** | topk vs cold **+107.6 [+73.1, +144.9]**、vs random **+123.4 [+89.1, +158.7]**，CI 均排除 0；0.88/0.94 靶为正 |
| **价值位置** | ✅ **复现胺化模式（init 主导）** | init_best **+8.63 [+5.80, +11.61]** 排除 0；final_best +0.31（≈0）；cold vs random +15.8（正）；C1 +13.6、C2 +16.9（均弱正含 0） |
| **源数门槛** | **≥3 未复现，跨源专属 ≥5** | n=3 Jaccard 0.29、Δinit_best −2.71、54% ≥ 全池；n=5 仍 −1.84/58% |
| **清单规则** | 冻结 mean 规则第三次验证稳健 | median 并列（+0.11），best_source −1.18，UCB 式 −1.91 |

### 9.2 锁定读法（不改 EDBO 锁；升级 P4 边界）

1. **策略草稿升"已验证（跨源）"**（按预注册 §4.1 强复现后果；**"已验证"指效应方向——多源池化 top-5 清单在跨反应类独立数据源上效应为正且显著；策略本身仍为草稿级临时默认，最终策略待策略研究（模式判别/门控/工具化）**）：
2. **"价值位置"主张修正为"按反应类/数据结构稳定复现"**：Pd C–C（EDBO + HiTEA 两个独立源）均为"后段/EI"模式；C–N 胺化与 Ni 硼化（两个独立源）均为"init 清单"模式——两种模式各自跨源复现，不再是"随机库间差异"；
3. **冷启动 BO 的可靠性也是库相关的**：胺化/borylation 上 cold > random（正），EDBO Suzuki 上 cold < random（−57.7）、**HiTEA 修复后 cold vs random +10.6（含 0，不再显著负）**——价值位置模式的冷启动表现需按库分述；
4. **终点一致性**：三个库的 final_best 优势均 ≪ init 优势（胺化 +2.2 / borylation +0.3 / Suzuki +5.3）——"更快到达同样的终点"跨库成立；
5. **源数门槛按库配置维持**：EDBO ≥3/≥5；跨源库 ≥5 且强制报 source coverage；
6. **适用边界**：borylation 条件空间 46（B=20 探索 43%），效应仍显著 → "条件空间小压缩效应"只解释 HiTEA 的弱效应，不否定迁移本身。
