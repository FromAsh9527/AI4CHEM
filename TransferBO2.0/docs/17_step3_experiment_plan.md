# Step3 实验方案 — 历史条件清单的可验证性与部署边界

**起草日期：** 2026-08-22  
**状态：** P0 **完成**（2026-08-22）；P1+P2 待开  
**依据：** `docs/16_work_report_step1_step2.md`、`docs/14_strategy_draft.md`、`docs/15_step1_step2_lock.md`  
**不改写：** `FROZEN_CLAIMS.md` 与 Step1/Step2 主表数字

---

## 0. 科学主线（一句话）

> **验证「多源历史高产条件 top-k 清单」在多大程度上可稳定、可审计、可部署地 warm-start 新底物实验**——而不是继续问「历史标签能否灌入 GP」或「Suzuki 是否存在负迁移机制」。

**产品映射（已锁）：**

\[
\text{历史数据的主要价值} = \text{多源池化 top-k 条件清单（init）}
\quad\text{+ 可选的 target-only GP/EI 续跑}
\]

与「历史标签池化进同一 GP」（`pooled` / `sim_weighted`）**严格区分**。

---

## 1. 不变量（全方案冻结）

| 项 | 锁定值 | 备注 |
|---|---|---|
| 协议 | LOSO；历史 = 除靶外全部底物（多源池化） | P1/P2 子集实验在此之上做 source 抽样 |
| 条件表示 | **OHE** | 不新开条件 Morgan/DFT |
| 底物近邻（若用到） | **morgan_r2 + Tanimoto** | 仅 P1 的 nearest 臂 |
| 优化器 | GP (Matern-2.5 ARD) + **EI** | target-only；历史不进 GP |
| n_init | **5** | |
| budget | **20**（P0 另设 topk_only 臂 budget=5） | |
| topk | **5** | 池化规则 = 跨源条件产率均值降序 |
| 种子 | **0–4**（全量） | 与 Step1 一致 |
| 推断单位 | 先 seed 平均 → 再 target 汇总 | bootstrap CI，B=5000 |
| 主指标 | Optimisation AUC；Δ vs cold **和** vs random | 禁止只报 vs cold |
| 次指标 | init_best、final_best、carried/post_lift（M1 分解）、worst-target | |

**禁止：** 根据新实验结果回改 Step1 主表；在新库上调 k/表示/池化规则；把 sim_weighted/safe_gate 重新调参当主策略。

---

## 2. 优先级总览

| 优先级 | 工作包 | 决策问题 | 规模（估） | 依赖 |
|---|---|---|---:|---|
| **P0** | Suzuki shared-init / EI-vs-random 审计 | Suzuki 能否作正支持证据？cold≺random 是协议还是 GP 问题？ | ~420 jobs | **完成** |
| **P1+P2** | 历史源规模 + 清单稳定性（合并） | 至少需要几个历史底物？清单对 source 扰动是否稳健？ | 离线 **完成**；BO 可选 | `analyze_p1p2_list_stability.py` |
| **P3** | 胺化前瞻湿实验 | benchmark 能否走向真实新底物？ | 湿实验 | P0 结论 |
| **P4** | 独立 reaction-family holdout | 无湿实验时的外部验证 | 视数据而定 | 冻结协议 |
| **P5** | `recommend_init` CLI | 工程交付 | 无超算 | 与 P1/P2 可并行 |

**推荐执行顺序：** P0 →（P1+P2 离线 + 按需 BO）→ P3 或 P4 → P5 并行。

---

## 3. P0 — Suzuki shared-init / matched-post 审计

### 3.1 为什么要做

Step1 已锁：

- Suzuki **Q1 失败**：cold−random = −57.7，仅 4/12 靶 cold>random  
- Suzuki **topk vs cold 为正**：+149.9 [+38.8, +269.8]  
- Suzuki **topk vs random 弱正**：+92.2 [0.0, +186.5]

M1 事后分解**不能替代**控制实验，因为 `cold_start` 与 `random` **未共享同一组 init**。  
因此 `topk − cold > 0` 可能部分来自「cold 基线偏弱」，不能直接当作部署证明。

P0 用**匹配初始化**拆开三件事：

1. **清单本身**是否优于随机起点？  
2. **给定好起点后**，后续 EI 是否仍有价值？  
3. **cold≺random** 来自 init 运气、EI/GP 弱、还是 20-shot 全随机协议差异？

### 3.2 实验臂（预注册）

固定 B=20、n_init=5；除 `topk_only` 外预算语义与 Step1 相同。

| ID | 策略名（config） | 前 5 点 | 后 15 步 | 与 Step1 关系 | 回答的问题 |
|---|---|---|---|---|---|
| R0 | `random` | 随机（无放回） | 继续随机 | 已有 | 全随机基线 |
| R1 | `cold_start` | seed 随机 init | target-only EI | 已有 | cold-EI |
| R2 | `topk_warm` | 池化 top-5 | target-only EI | 已有 | topk-EI |
| R3 | `cold_random_post` | **与 R1 相同 init**（同 seed） | **随机**（无 GP） | **新增** | 同 init 下 EI vs 随机 |
| R4 | `topk_random_post` | **与 R2 相同 init** | **随机** | **新增** | 给定 topk 起点，EI 是否增值 |
| R5 | `topk_only` | 池化 top-5 | **无后续**（budget=5） | **新增** | 清单本身（最便宜） |

**关键比较（预注册主终点）：**

| 比较 | 公式 | 解读 |
|---|---|---|
| **C1** | R2 − R4 = topk-EI − topk-random | 给定历史高产起点，EI 是否仍有价值 |
| **C2** | R1 − R3 = cold-EI − cold-random | Suzuki cold 异常：同 init 下 EI 是否拖后腿 |
| **C3** | R2 − R1 = topk-EI − cold-EI | 同后续策略下，init 清单溢价 |
| **C4** | R5 vs R0 前 5 步 | 清单 vs 随机 init（init_best / AUC_init） |
| **C5** | R2 − R0 | 与 Step1 一致的全局对照（复现检查） |

**次终点：** init_best、final_best、M1 分解（carried / post_lift）、靶级胜率、worst-target。

### 3.3 实现规格（代码前置）

在 `src/transferbo2/strategies/` 新增：

#### `cold_random_post`

```text
rng = default_rng(seed)
init = sample_init(n, n_init, rng)   # 与 ColdStart 完全相同
post = random_permutation(remaining unobserved)[:budget - n_init]
```

- init 索引必须与 `cold_start`（同 target、同 seed）**逐点一致**。  
- 建议单测：`assert cold_start.init == cold_random_post.init`。

#### `topk_random_post`

```text
init = TopKWarm._select_init(...)    # 与 topk_warm 完全相同
post = random_permutation(remaining)[:budget - n_init]
```

- 建议单测：与 `topk_warm` init 一致。

#### `topk_only`

```text
init = TopKWarm._select_init(...)
budget_eff = min(n_init, 5)          # 只评价 init，不进入 BO 环
```

- JSON 中 `budget=5`，`n_init=5`；AUC = sum(BSF[0:5])。

**共享工具函数（建议）：**

- `select_cold_init(n, n_init, seed) -> np.ndarray`  
- `select_topk_init(hist_df, condition_ids, topk, n_init, seed) -> np.ndarray`  
- `run_random_post(y_oracle, init_idx, budget, seed) -> BOLoopResult`

### 3.4 Sanity check — 胺化 2 靶

在 Suzuki 全量前，用胺化 **2 个靶 × 5 seeds × 6 臂 = 60 jobs** 验证接线：

| 检查项 | 预期（胺化） |
|---|---|
| R1 ≈ Step1 `cold_start`（同靶同 seed AUC） | 数值一致 |
| R2 ≈ Step1 `topk_warm` | 数值一致 |
| R3 init == R1 init | 单测 + JSON meta |
| R4 init == R2 init | 单测 + JSON meta |
| C2 = R1−R3 | **明显为正**（EI 在胺化上应有效） |
| C1 = R2−R4 | 可为正、近零或略负（M1：胺化 carried 主导，post_lift 可负） |

配置：`configs/amination_p0_shared_init_sanity.yaml`（2 靶子集）。  
**若 sanity 失败，禁止上 Suzuki 全量。**

### 3.5 Suzuki 全量

| 项 | 值 |
|---|---|
| 库 | Suzuki 12 靶 |
| 臂 | R0–R5 共 6 |
| jobs | 12 × 6 × 5 = **360** |
| 配置 | `configs/suzuki_p0_shared_init_hpc.yaml` |
| 输出 | `results/suzuki_p0_shared_init/` |
| HPC 说明 | `scripts/hpc/README_P0_SHARED_INIT_HPC.md` |

### 3.6 预注册成功判定（跑前写死，事后不得改）

| 结果模式 | 对 Suzuki 叙事 | 对 Step3 策略 |
|---|---|---|
| **C1 ≤ 0**（topk-EI ≈ topk-random） | 可写：后续 BO 非主杠杆 | **默认产品 = 推荐前 5 个条件**；EI 标为可选 |
| **C1 > 0** 且 CI 不含 0 | topk + EI 有附加价值 | 策略可写「init + target-only EI」 |
| **C2 < 0**（cold-EI < cold-random，同 init） | Q1 失败 = **GP/EI 问题**，非 init 运气 | 不得用 cold 单独否定 topk |
| **C3 > 0 但 C5 vs Step1 缩小** | vs cold 有夸大；看 C4/C5 vs random | topk 清单证据仍看 **vs random** |
| **C4、C5 均失败**（清单打不过随机） | Suzuki 降为**不可作部署证明** | 仅胺化作主交付库 |
| **C2 ≈ 0，C1 > 0** | 协议混合问题 + topk 后续仍有益 | 分靶报告 |

**不改写：** 胺化 Step1 主结论；Suzuki topk vs cold 的锁档数字（P0 只改**解释边界**）。

### 3.7 分析产出

| 产出 | 路径 |
|---|---|
| 效应表 | `results/suzuki_p0_shared_init/effects.csv` |
| 关键比较 C1–C5 | `results/suzuki_p0_shared_init/key_comparisons.csv` |
| M1 分解 | `results/suzuki_p0_shared_init/m1_decomposition.csv` |
| 摘要 | `results/suzuki_p0_shared_init/summary.md` |
| 脚本 | `scripts/analyze_p0_shared_init.py` |

分析脚本须输出：靶级均值/中位数/CI、胜率、worst-target、与 Step1 `suzuki_v1_full` 的 R1/R2/R0 一致性检查。

### 3.8 P0 结果（2026-08-22，已跑完）

| 轨道 | jobs | 路径 |
|---|---:|---|
| 胺化 sanity | **60/60** | `results/amination_p0_shared_init_sanity/` |
| Suzuki 全量 | **360/360** | `results/suzuki_p0_shared_init/` |

Step1 复现：同靶 `cold_start` / `topk_warm` / `random` 的 AUC 与 `*_v1_full` **差值 = 0**。  
init 匹配：`cold_start` 与 `cold_random_post` 的 init_best 相同；`topk_warm` 与 `topk_random_post` 相同。

**胺化 sanity（2 靶，接线验证）**

| 比较 | ΔAUC [95% CI] | 解读 |
|---|---|---|
| C2 cold-EI − cold-random | **+129.4** [+32.8, +226.0] | 同 init 下 EI ≫ 续随机；实现正确 |
| C1 topk-EI − topk-random | +153.8 [0, +307.7] | 仅 2 靶，CI 宽 |

**Suzuki 全量（12 靶，主结论）**

| 比较 | ΔAUC [95% CI] | 预注册判定 | 解读 |
|---|---|---|---|
| **C2** cold-EI − cold-random | **−21.3** [−60.3, +9.0] | C2 < 0 | Q1 失败 = **target-only GP/EI 偏弱**，非 init 运气（**弱证据**：CI 含 0，点估计支持但未排除 C2 ≥ 0） |
| **C1** topk-EI − topk-random | **+75.5** [+15.5, +161.7] | C1 > 0 | 给定 topk 起点，**后续 EI 仍有价值** |
| C3 topk − cold | +149.9 [+38.8, +269.8] | 与 Step1 一致 | vs cold 正增益成立 |
| C5 topk − random | +92.2 [0.0, +186.5] | 与 Step1 一致 | vs random 弱正、偏脆 |
| C4 topk_only − random（init_best） | −0.88 [−12.9, +9.0] | — | **仅前 5 点**清单 ≈ 随机 init；净增益靠 topk+EI 后 15 步 |

**P0 锁定读法（不改 Step1 数字）：**

1. Suzuki **禁止**把 cold 当可靠部署路径；cold-EI 在同 init 下弱于续随机。  
2. Suzuki **仍可用** pooled topk **+ target-only EI**（C1、C5 支持）；不得声称与胺化同级稳健。  
3. Suzuki **不得**写成「只做 5 个历史条件就够」——init 段 alone 不稳赢随机（C4）；胺化仍以 init 为主（M1 + 2026-08-22 胺化 matched-init 审计 C1/C2）。  
4. 报告必须双对照 vs cold **和** vs random；单独 vs cold 在 Suzuki 上易夸大。  
5. **C2 证据强度限定**：Suzuki C2 = −21.3 的 CI 含 0，「GP/EI 偏弱」是点估计支持的弱证据，写作时须限定「与 GP/EI 偏弱一致」，不得写成已证实。

分析摘要：`results/suzuki_p0_shared_init/summary.md`、`key_comparisons.csv`。

---

## 3.9 胺化 matched-init 审计（2026-08-22，审计补跑）

**动机（审计发现）：** P0 只在 Suzuki 做了 matched-init 全量；正效应主库胺化上「历史起点后 EI 续跑是否增值（C1）」只有 2 靶 sanity + M1 事后分解。本次补跑把胺化升级为控制实验。

**设计：** 150 jobs = 15 靶 × {`cold_random_post`, `topk_random_post`} × 5 seeds；与 Step1 `cold_start`/`topk_warm` 共享同一 init（单测 + AUC@5/init_best Δ=0 双重校验）。配置：`configs/amination_matched_init_audit.yaml`；产出：`results/amination_matched_init_audit/`；分析：`scripts/analyze_amination_matched_init.py`。

**结果（靶级 bootstrap 95% CI）：**

| 比较 | AUC Δ [95% CI] | final_best Δ | 读法 |
|---|---:|---:|---|
| **C1** topk+EI − topk+random | +26.0 [−5.9, +71.7]（0.47 靶>0） | +2.16 [−0.2, +5.6] | 给定 topk 起点，EI 续跑**增值弱**（CI 含 0） |
| **C2** cold+EI − cold+random | +67.7 [+37.0, +100.4]（0.87 靶>0） | +5.30 [+3.2, +7.7] | 冷启动下 EI **明显有效**（CI 排除 0） |
| **C3** topk − cold（同 EI） | +160.2 [+105.7, +211.6]（复现锁档） | +2.24 [+0.1, +4.2] | init 清单优势不变 |
| topk+random − cold+EI | +134.2 [+49.2, +208.0]（0.93 靶>0） | +0.07 [−4.0, +3.4] | 历史清单配**任何续跑**都赢 cold-BO；终点相同 |

**与 Suzuki P0 的镜像结论（2026-08-22 审计核心发现）：**

| | 胺化（主库） | Suzuki（P0） |
|---|---|---|
| C2（冷启动下 EI 有效？） | **+67.7**，CI 排除 0 | −21.3，CI 含 0（弱证据） |
| C1（topk 起点下 EI 增值？） | +26.0，CI 含 0（弱正） | **+75.5**，CI 排除 0 |
| 历史价值所在 | **第 1 轮清单**（EI 可选） | **EI 续跑**（清单 alone 不稳） |

**锁定读法（不改 Step1 主表数字）：**

1. 胺化上「历史数据加速 BO」的精确表述 = **历史清单提供更好起点，协议整体更快到达高产出（命中 top-5% 早 ~1 轮、AUC@5 +93.6）；终点水平几乎不变（final_best +2.2）**。  
2. 胺化 EI 续跑**可选**：C1 弱正（点估计 +26，CI 含 0）；topk 清单 + 随机续跑已可赢 cold+EI（+134.2）。  
3. 轮次口径警示：优势集中在相对/前段指标；**绝对阈值 ≥70% 下优势大幅缩水**（r70 Δ≈0、20 步内达标率仅 ~0.47）——对外表述不得承诺「更快达到 70% 产率」。  
4. 与 P0 共同构成双库机制镜像：**迁移价值的位置是库相关的**（胺化在 init、Suzuki 在 EI），策略必须分库写。

---

## 4. P1+P2 — 历史源规模与清单稳定性（合并设计）

### 4.1 决策问题

1. **P1：** 新底物到来时，至少需要多少个历史底物，pooled top-5 才值得用？  
2. **P2：** 条件清单对 source 组成扰动是否稳健？  

二者共用 **leave-sources-out（LSO）** 框架：对靶 \(t\)，从 \(n_{\text{all}}-1\) 个历史源中抽大小为 \(n_s\) 的子集，重建 pooled top-5。

### 4.2 源规模网格

\[
n_s \in \{1, 2, 3, 5, \text{all}\}
\]

| 库 | 历史源总数（LOSO） | 备注 |
|---|---:|---|
| 胺化 | 14 | **主统计库** |
| Suzuki | 11 | 辅助边界库 |

每个 \(n_s\)：对胺化抽 **K=20** 次子集（固定种子序列 `subset_seed=0..19`），Suzuki **K=10**。

### 4.3 策略臂（每个子集只跑 init 相关 + 一条续跑）

| 臂 | 说明 | 是否需 BO |
|---|---|---|
| `pooled_topk` | 子集上池化 top-5 | init 离线可算；完整 AUC 需 BO |
| `random_source_topk` | 从子集**随机选 1 源**，取该源 top-5 | 离线 + 可选 BO |
| `nearest_topk`（Morgan） | 子集内 Morgan 最近邻源 top-5 | 离线 + 可选 BO |
| `cold_start` | 对照 | BO |
| `random` | 对照 | BO |

**离线必算（不需超算）：**

- \(\mathrm{Jaccard}(\text{Top5}_{\text{full}}, \text{Top5}_{\text{sub}})\)  
- 子集清单在靶上的 **init_best**、**mean(top5 yields)**  
- **source coverage**：每个推荐条件被多少源支持  
- \(\Delta \text{init\_best}\) vs full-pool baseline  

**按需 BO（省算力）：**

- 仅对胺化 \(n_s \in \{1, 3, \text{all}\}\) 跑 `pooled_topk` + `cold_start` + `random` 全 BO  
- Suzuki 只对 \(n_s \in \{3, \text{all}\}\) 跑 `pooled_topk`  

### 4.4 主指标

| 指标 | 用途 |
|---|---|
| \(\Delta\mathrm{AUC}_{\text{cold}}(n_s)\) | 源规模–效应曲线 |
| \(\Delta\mathrm{AUC}_{\text{random}}(n_s)\) | 双对照 |
| \(P(\Delta\mathrm{AUC} < 0)\) | 负迁移风险 |
| worst-target / worst-decile | 部署下限 |
| mean Jaccard vs \(n_s\) | 清单稳定性（P2） |
| \(\Delta\)init_best vs \(n_s\) | 清单质量衰减 |

### 4.5 预注册读法

| 发现 | 策略写法 |
|---|---|
| \(n_s=3\)–\(5\) 已接近 all-source 的 ΔAUC 与 Jaccard | 「≥3 个历史底物即可默认 pooled top-5」 |
| 必须 \(n_s \gtrsim 10\) 才接近 all | 收窄适用边界；CLI 必须报 source count 警告 |
| Jaccard 低但 init_best 稳 | 清单成员变但质量稳 → 报 coverage 而非固定 ID |
| Jaccard 与 init_best 双低 | 必须要求更多源；默认策略加硬门槛 |

### 4.6 实现

| 组件 | 说明 |
|---|---|
| 配置 | `configs/amination_p1_source_robustness_hpc.yaml`、`configs/suzuki_p1_source_robustness_hpc.yaml` |
| 脚本 | `scripts/run_source_subset_loso.py`（新） |
| 离线分析 | `scripts/analyze_p1p2_list_stability.py`（新） |
| 输出 | `results/p1p2_source_robustness/{amination,suzuki}/` |

**冻结：** k=5、池化均值规则、OHE、EI 设置；**禁止**按 \(n_s\) 调 k 或换聚合方式。

### 4.7 离线分析（2026-08-22，已完成）

```bash
python scripts/analyze_p1p2_list_stability.py --library both
```

产出：`results/p1p2_source_robustness/{amination,suzuki}/`

| 文件 | 内容 |
|---|---|
| `list_stability_detail.csv` | 每靶 × n_s × replicate × list_type |
| `list_stability_summary.csv` | 聚合 Jaccard / Δinit_best |
| `pooled_curve_by_n_sources.csv` | 池化清单随 n_s 曲线 |
| `pooled_curve.png` | 图 |
| `summary.md` | 可读摘要 |

### 4.8 P1+P2 离线结果与读法（2026-08-22）

**胺化（主库，15 靶 × 20 replicate）— pooled top-5 vs 全历史**

| n_sources | Jaccard [CI] | Δinit_best [CI] | frac init ≥ full |
|---:|---:|---|---:|
| 1 | 0.17 [0.16, 0.19] | −1.66 [−2.65, −0.59] | 0.54 |
| 2 | 0.29 [0.27, 0.31] | −0.73 [−1.75, +0.28] | 0.61 |
| 3 | 0.39 [0.36, 0.41] | −0.33 [−1.20, +0.56] | 0.70 |
| 5 | 0.50 [0.47, 0.52] | +0.71 [−0.15, +1.62] | 0.79 |
| all | 1.00 | 0 | 1.00 |

**Suzuki（辅助，12 靶 × 10 replicate）**

| n_sources | Jaccard [CI] | Δinit_best [CI] |
|---:|---:|---|
| 1 | 0.09 [0.07, 0.11] | −4.18 [−7.70, −0.44] |
| 3 | 0.23 [0.20, 0.27] | −0.90 [−4.69, +2.96] |
| 5 | 0.26 [0.22, 0.29] | +1.55 [−2.28, +5.62] |

**锁定读法（离线层，不改 Step1 数字）：**

1. **清单 ID 随 n_s 变化大**（胺化 n=1 Jaccard≈0.17）→ 产品应报 **source coverage / support**，不能只承诺固定 5 个条件 ID。  
2. **胺化 init 质量**：n≥5 时靶均 init_best（66.4）已接近/超过全池（65.7）；n=3 时 CI 仍跨 0 → **默认门槛：≥3 个历史底物，推荐 ≥5**。  
3. **单源（n=1）明显弱于多源池化** → 与 Step2 pair≪LOSO 一致；禁止单源冒充多源策略。  
4. **Suzuki 清单更不稳定**（n=5 Jaccard 仅 0.26）→ 边界库；适用边界写得更窄。  
5. n=all 时 **Morgan 近邻 init_best（胺化 68.6）可高于池化（65.7）** → 与 M2 一致，Morgan 并列规则仍成立。

**BO 轨（可选）：** `scripts/run_source_subset_loso.py` — 胺化 675 jobs（n∈{1,3,all}×3策略×5seed）；待超算或本地续跑。

---

## 5. P3 — 胺化前瞻湿实验（最小方案）

### 5.1 目标

\[
\text{retrospective LOSO} \rightarrow \text{prospective validation on new substrates}
\]

### 5.2 设计

| 项 | 规格 |
|---|---|
| 新底物 | **2–4** 个未参与策略开发的芳基胺化底物 |
| 条件空间 | 与主库相同离散候选集（或明确可比的子集） |
| 臂 | pooled top-5；Morgan-nearest top-5（若有指纹）；随机 5 点；可选 cold-EI / random 续跑 |
| 预算 | **5–20** 次真实反应/底物（不必跑满整板） |
| 主终点 | \(\max_{x \in \text{前 5 次}} y_t(x)\)（init_best） |
| 次终点 | 达可接受产率所需实验次数；若续跑则 AUC |

### 5.3 冻结协议

与 Step3 策略草稿一致：k=5、池化规则、OHE、Morgan Tanimoto、不将历史并入 GP。

### 5.4 产出

- 湿实验记录表（底物、条件 ID、产率、臂）  
- `docs/18_wet_lab_protocol.md`（湿实验 SOP，P3 启动时再写）  
- 结果：`results/p3_wet_lab/`

---

## 6. P4 — 独立 reaction-family holdout（无湿实验替代）

### 6.1 入选标准

- 多个 substrate-defined tasks  
- 共享离散条件空间  
- 每 task 有完整或足够密的 response panel  
- 可构成 LOSO  
- 条件维度 > 1  
- **未用于**本仓库策略开发/调参  

### 6.2 验证协议

完全冻结：k=5、pooled 均值规则、OHE、Morgan 定义、B=20、n_init=5、EI、主比较 vs cold **和** vs random。

### 6.3 产出

- 数据入库脚本 + 一份 holdout 配置  
- `results/p4_holdout/`  
- 若找不到合格库：在论文/报告中明确「外部 holdout 未做」而非凑数据集  

---

## 7. P5 — `recommend_init` CLI（工程，与科学验证分离）

### 7.1 范围

**只实现**当前锁定策略；不做 MTGP、不做 safe_gate 自动迁移。

### 7.2 接口（草案）

```text
Input:
  historical yield table (long format)
  target metadata (+ optional Morgan fingerprint)
  candidate condition table

Output:
  pooled top-5 conditions
  optional Morgan-nearest top-5
  per-condition source support count
  pooled score / rank / yield coverage
  nearest source Tanimoto
  warnings: insufficient sources; no validated safe gate
  explicit: do NOT merge historical labels into target GP by default
```

### 7.3 命令（已实现，2026-08-24）

```bash
python -m transferbo2.cli recommend-init \
  --db data/db/transferbo2.db \
  --target-substrate <id> \
  --topk 5 \
  --rule rank_median \
  --out recommendations.json
# 可选 G2 门控（round-1 观测 CSV）：
#   --probe-obs round1_obs.csv
```

实现：`src/transferbo2/cli.py::recommend_init_main`（entry point `tbo2-recommend-init`）；规则 = **rank_median**（策略研究第 1 步，`docs/14` v2026-08-24）。

### 7.4 验收（2026-08-24 更新）

- 对胺化 LOSO 每个靶，离线 top-5 与策略研究 rank_median 规则一致（原验收对照 Step1 mean 规则；规则升级后对照 `results/strategy_list_rules/`）；
- 输出含 audit 字段（per-condition source coverage、源数警告、G2 门控可选）；
- 单元测试：`tests/test_cli.py`（规则/coverage/警告/G2 门控），16/16 全套通过。

---

## 8. 明确不做（纪律）

| 不做 | 理由 |
|---|---|
| 继续堆条件表示 | Phase B 已否决默认升级 |
| 调 sim_weighted / safe_gate 成正 | 近 null；易 overfit |
| MTGP / contextual GP 主线 | M1：主杠杆在 init |
| naive pooling 进 GP 的「安全」研究 | 另一套迁移定义 |
| pair 全量 | 不挡主交付 |
| 用 P0/P1 结果回改 Step1 主表 | 只升级 Step3 叙事与边界 |

---

## 9. 工程清单与里程碑

### 9.1 代码（P0 开跑前）

- [x] `cold_random_post`、`topk_random_post`、`topk_only` 策略  
- [x] 抽取共享 `select_cold_init` / `select_topk_init`  
- [x] 单测：init 一致性（`tests/test_p0_shared_init.py`）  
- [x] `scripts/analyze_p0_shared_init.py`  
- [x] `configs/amination_p0_shared_init_sanity.yaml`  
- [x] `configs/suzuki_p0_shared_init_hpc.yaml`  
- [x] `scripts/hpc/README_P0_SHARED_INIT_HPC.md`  
- [x] HPC submit + 全量跑完（420/420 jobs）

### 9.2 代码（P1+P2）

- [x] `src/transferbo2/benchmarks/source_subset.py`  
- [x] `scripts/analyze_p1p2_list_stability.py`（离线，已跑）  
- [x] `scripts/run_source_subset_loso.py`（BO 轨）  
- [x] 胺化/Suzuki P1 配置  
- [ ] P1 BO 全量（胺化 675 + Suzuki 360，可选超算）

### 9.3 文档更新（各阶段完成后）

- [x] P0 完成 → 更新 `docs/14_strategy_draft.md` Suzuki 行 + `docs/15_step1_step2_lock.md` 附录（仅边界，不改主数字）  
- [ ] P1+P2 完成 → Step3 策略从「草稿」升为「已验证」  
- [ ] P3/P4 完成 → 外部证据节  

### 9.4 资源估算

| 阶段 | 超算 jobs | 备注 |
|---|---:|---|
| P0 sanity（胺化） | 60 | 2 靶 × 6 × 5 |
| P0 全量（Suzuki） | 360 | 12 × 6 × 5 |
| P1+P2 离线 | 0 | 长表 + 子集枚举 |
| P1+P2 BO（按需） | ~2k–5k | 按 9.2 裁剪 |
| P3 湿实验 | — | 10–80 反应 |
| P5 CLI | 0 | 本地 |

---

## 10. 与锁档文档的关系

```
FROZEN_CLAIMS.md          ← Step1 数字（不改）
docs/15_step1_step2_lock  ← Step1+Step2 机制（不改）
docs/14_strategy_draft    ← P0–P2 可升级细则与 Suzuki 边界
docs/17_step3_experiment_plan ← 本文件（预注册新实验）
```

**P0 可能改变的只有：** Suzuki 在正文/产品中的**表述强度**（弱支持 vs 协议反例），不改变胺化主结论。

---

## 11. 快速启动（P0）

```bash
# 1. 实现新策略后本地单测
pytest tests/test_p0_shared_init.py -q

# 2. 胺化 sanity（2 靶）
python scripts/run_loso.py --config configs/amination_p0_shared_init_sanity.yaml --dry-run
python scripts/run_loso.py --config configs/amination_p0_shared_init_sanity.yaml --workers 8

# 3. 分析 sanity
python scripts/analyze_p0_shared_init.py --results-dir results/amination_p0_shared_init_sanity

# 4. Suzuki 全量（sanity PASS 后）
python scripts/run_loso.py --config configs/suzuki_p0_shared_init_hpc.yaml --dry-run
# → 360 jobs；见 scripts/hpc/README_P0_SHARED_INIT_HPC.md
```

---

## 12. 参考文献（仓库内）

| 文档 | 角色 |
|---|---|
| `docs/16_work_report_step1_step2.md` | 已完成工作汇报 |
| `docs/14_strategy_draft.md` | 当前策略草稿 |
| `docs/15_step1_step2_lock.md` | 锁档与校验 |
| `results/step2_m1/` | M1 分解（P0 假设来源） |
| `results/step2_m2/` | 池化机制（P1/P2 假设来源） |
