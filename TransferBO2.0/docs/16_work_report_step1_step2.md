# TransferBO2.0 工作汇报（Step1 效应 + Step1b 表示 + Step2 机制）

**汇报日期：** 2026-08-22  
**项目：** TransferBO2.0 — 同一反应库下，跨底物历史数据对新建底物贝叶斯优化（BO）的利用  
**产品目标：** 交付「如何用历史 BO/HTE 数据」的默认策略，而不是「冷启动 GP 是否强于随机」  
**当前状态：** Step1 数字冻结；Step1b 表示轴收口；Step2 机制完成并与 Step1 合并锁档；机器校验 **24/24 PASS**；Step3 策略草稿已写（非湿实验 SOP）

---

## 一、背景与问题

### 1.1 要解决什么

在同一反应模板下，已有多个底物上的完整条件–产率数据（历史）。面对**新底物**做条件优化时：

1. 历史数据有没有用？  
2. 哪一类用法最有效（全局高产条件 warm-start、近邻底物、相似度加权进 GP、门控等）？  
3. 结论能否从胺化平移到 Suzuki？  
4. 换化学表示后，效应是否还成立？增益究竟来自「先做对点」还是「后面 BO 更聪明」？

### 1.2 三步研究框架

| 步 | 问题 | 本阶段状态 |
|---|---|---|
| **Step1 效应** | 固定协议下，迁移动作的可观测增益是什么？ | **锁死**（`FROZEN_CLAIMS.md`） |
| **Step1b 表示** | 换底物/条件表示后，效应是否稳健？ | **收口**（不再堆表示） |
| **Step2 机制** | 增益从哪来？池化为何强？近邻何时翻盘？ | **锁死**（M1/M2 + 校验） |
| **Step3 策略** | 默认怎么用历史？ | **草稿**（`docs/14_strategy_draft.md`） |

### 1.3 统计与协议口径（全程统一）

- **推断单位：** 先对 seed 平均，再在 **target（底物/任务）** 上汇总；跨靶 bootstrap 95% CI  
- **主指标：** Optimisation AUC = Σ best-so-far（预算内逐步最优之和）  
- **主对照：** 策略 vs `cold_start`，以及 vs `random`（双对照；禁止只报 vs cold）  
- **LOSO 协议：** n_init=5，budget=20，acquisition=EI；历史 = 其余全部底物（多源池化）  
- **Step1 表示：** 条件 OHE + 底物 hashed SMILES（仅相似类策略使用）  
- **种子：** 全量 0–4（5 seeds）

---

## 二、已完成工作总览

### 2.1 实验与分析清单

| 轨道 | 规模 | 表示 | 角色 | 路径 |
|---|---|---|---|---|
| 胺化 LOSO 全量 | **450** = 15×6×5 | OHE + hashed | Step1 主表 | `results/amination_v1_full/` |
| Suzuki LOSO 全量 | **360** = 12×6×5 | OHE + hashed | Step1 跨化学对照 | `results/suzuki_v1_full/` |
| 胺化 topk 消融 | 525 | OHE + hashed | k 与 gate 敏感性 | `results/amination_topk_ablation/` |
| 胺化 / Suzuki pair 试点 | 126×2 | OHE + hashed | 单源机制材料（非主表） | `*_pair_v1_pilot/` |
| Phase A 胺化 / Suzuki | 450 / 360 | OHE + **Morgan 底物** | 表示稳健性 | `*_rep_A_morgan_sub_full/` |
| Phase B DFT 试点（Suzuki） | 36 | 条件 DFT + Morgan 底物 | 否决升全量 | `suzuki_rep_B_dft_cond_pilot/` |
| Phase B both Morgan | 450 / 360 | 条件+底物 Morgan | 否决条件 Morgan 默认 | `*_rep_B_morgan_both_full/` |
| Step2 M1 | 事后分析 | — | init vs 后续 BO | `results/step2_m1/` |
| Step2 M2 | 事后分析 | — | 池化 vs 近邻 | `results/step2_m2/` |
| 锁档校验 | 机器再生 | — | 24 项对账 | `results/step1_step2_validation/` |

合计：主效应与表示全量约 **2700+** 个 LOSO/pair job（含消融与试点）；机制层不新开超算，复用 JSON 与长表。

### 2.2 文档与工程交付

| 类型 | 路径 |
|---|---|
| Step1 数字与主张锁 | `FROZEN_CLAIMS.md` |
| Step1 设计规范 | `docs/10_step1_transfer_effects.md` |
| 表示轴 | `docs/11_step1b_representation.md` |
| 收口后规划 | `docs/12_plan_after_step1.md` |
| Step1 收口戳 | `docs/13_step1_closeout.md` |
| 策略草稿 | `docs/14_strategy_draft.md` |
| **Step1+Step2 合并锁** | `docs/15_step1_step2_lock.md` |
| 结果总览 | `results/ALL_RESULTS_ANALYSIS.md` |
| 校验脚本 | `scripts/validate_step1_step2.py` |
| M1 / M2 分析 | `scripts/analyze_step2_m1_*.py`、`analyze_step2_m2_*.py` |
| HPC 提交与打包 | `scripts/hpc/`（胺化/Suzuki 全量、Phase A/B） |

---

## 三、Step1：效应结论（主锁）

### 3.1 预注册问题（Q1–Q4）

1. 冷启动 BO 是否优于随机？  
2. 何种迁移动作相对 cold 有净增益？  
3. 全局多源 topk 是否优于最近邻 topk？  
4. 胺化结论能否平移到 Suzuki？

### 3.2 胺化（15 靶 × 5 seeds）— 效应成立

| strategy | AUC | Δcold [95% CI] | 靶胜率>cold | Δrandom |
|---|---:|---:|---:|---:|
| **topk_warm** | 1359.5 | **+160.2 [+108.1, +211.6]** | 0.87 | **+268.0** |
| nearest_topk_warm | 1316.2 | +117.0 [+69.9, +160.8] | 0.87 | +224.7 |
| sim_weighted | 1218.6 | +19.3 [−1.1, +35.5] | 0.73 | +127.1 |
| safe_gate | 1210.8 | +11.5 [−17.6, +35.2] | 0.67 | +119.3 |
| cold_start | 1199.3 | — | — | +107.8 |
| random | 1091.5 | −107.8 | 0.00 | — |

**锁定主张：**

1. **Q1 成立：** cold−random = +107.8 [+75.2, +145.4]；**15/15** 靶 cold>random。  
2. **主正效应是全局多源 topk init，不是历史进 GP。** sim / safe_gate 相对 cold 近 null，不得当主策略。  
3. **hashed 协议下** topk ≻ nearest（主张 3 仅锁 OHE+hashed）。

### 3.3 Suzuki（12 靶 × 5 seeds）— 基线 BO 差，但 topk 仍有证据

| strategy | AUC | Δcold [95% CI] | Δrandom |
|---|---:|---:|---:|
| **topk_warm** | 1576.2 | **+149.9 [+38.8, +269.8]** | +92.2（CI 下沿贴 0） |
| cold_start | 1426.3 | — | **−57.7**（CI 含 0） |
| random | 1484.0 | +57.7 | — |

**锁定主张：**

1. **Q1 不成立：** 仅 4/12 靶 cold>random → **冷启动 BO 质量备注**，不是「历史策略失败」。  
2. **topk vs cold 清楚为正**；不存在 topk≺cold。vs random 弱正、偏脆。  
3. **禁止把胺化整包部署叙事平移到 Suzuki**；允许分库报告 topk 效应量。  
4. **产品成功标准 ≠ Q1：** 策略是否可行看 vs cold **和** vs random（2026-08-21 附录）。

### 3.4 附录实验（不升格主表）

**topk 消融（胺化）：** n_init=5 时 k=5 ≡ k=10 ≡ 现有 `topk_safe_gate`（门槛未触发弃权）；k=3≈k=5；k=1 略差。→ 默认 **k=5**。

**Pair 试点：** 单源下 topk≡nearest；胺化单源 topk AUC（约 1020）明显弱于同靶 LOSO 池化 topk。→ 为 Step2「池化优于单源」提供线索，**不作主证**。

---

## 四、Step1b：表示轴稳健性（已收口）

### 4.1 Phase A — 只换底物为 Morgan（条件仍 OHE）

**科学问题：** 化学相似是否改变「近邻 vs 全局 topk」？

| 库 | 关键发现 |
|---|---|
| 胺化 | topk/cold/random 与 hashed **数值完全一致**（接线健全）；**nearest Δcold +117→+171**，略高于 topk |
| Suzuki | topk 不变；**nearest +24→+166**；Q1 仍失败 |

**含义：** hashed 下「近邻弱于全局 topk」是表示问题；Morgan+Tanimoto 后近邻可变强。主张 3 **不回写**，只加协议条件。

### 4.2 Phase B — 条件表示

| 实验 | 结论 |
|---|---|
| Suzuki 条件 DFT 试点（36 jobs） | topk 相对同子集 OHE **约 −157 AUC**；**不升全量** |
| 胺化/Suzuki 条件+底物 both Morgan 全量 | random 不变（健全）；胺化 cold 绝对 AUC 下降；Suzuki topk Δcold CI 跨 0 | **条件默认保持 OHE**；条件 Morgan/DFT 不升默认 |

### 4.3 表示轴收口决定

1. 条件特征默认：**OHE**  
2. 底物近邻相关工作：**morgan_r2 + Tanimoto**  
3. 不再为「再换一套指纹」开主实验  

---

## 五、Step2：机制（已完成并锁档）

### 5.1 M1 — 增益在 init 还是后续 BO？

把 AUC = Σ BSF 拆成：

- **AUC_init：** 前 5 步  
- **carried（init 通道）：** 前 5 步面积 + 15 × init_best（起点被后续带着走）  
- **post_lift：** 后 15 步因 BSF 继续上升多出的面积  

**胺化 topk vs cold：**

| 分量 | ΔAUC |
|---|---:|
| 总（与 Step1 相同） | **+160.2** |
| init 通道（carried） | **+278.5**（占比 174%） |
| 后 15 步额外抬升 | **−118.3** |

解读：topk 把起点抬高（init_best 约 65.7 vs cold 53.4）；cold 后面涨得更多，只是因为起点差、还有空间。约一半 topk job 在 init 后不再提升。

**Suzuki topk vs cold：** carried 约占 **89%** → 相对 cold 仍是 init 通道。  
**Suzuki topk vs random：** random 的 5-shot 运气可接近 topk 的 init_best，净增益更多在后 15 步 BO vs 继续随机——不否定清单，但说明对 random 不能只报 init。

**机制结论 M1：** 相对 cold，交付物优先是 **历史高产条件清单（warm-start）**，不是先堆更聪明的 GP。

### 5.2 M2 — 池化为什强？Morgan 近邻为何翻盘？

用长表条件×底物产率矩阵，把各策略会选的 top-5 **放到靶上的真实产率**；并对照 pair 试点 AUC。

**胺化（15 靶）清单质量：**

| 清单 | 靶上 top5 均产 | 靶上 top5 最高产（≈init_best） |
|---|---:|---:|
| 池化 LOSO top5 | **59.6** | **65.7** |
| 单源 top5 平均 | 52.4 | — |
| hashed 近邻 top5 | 55.0 | 62.6 |
| Morgan 近邻 top5 | 55.9 | **68.6** |
| 靶 oracle top5 | 69.8 | — |

- 池化 > 单源平均：**93%** 靶  
- pair 同靶同 seed：LOSO topk AUC − pair topk ≈ **+83.5**（池化更强；pair 里只有一个源故 topk≡nearest）  
- Morgan：近邻源 **100% 换人**；**max** 62.6→68.6（已高于池化 topk 的 65.7）  
- **全局 Spearman 并不升高**（hashed-NN 0.76 vs Morgan-NN 0.50）→ 翻盘看的是 **init 最高点**，不是「整条排序更像靶」

**Suzuki：** 池化仍优于单源平均；Morgan 近邻 init max 68.1→78.7，与 Phase A nearest 变强一致。

**机制结论 M2：** 默认清单 = **多源池化 topk**；Morgan 下 nearest 可并列（改的是 init 质量）；sim 加权不改 init，不是主通道。

---

## 六、策略草稿（Step3，可执行默认）

权威：`docs/14_strategy_draft.md`（草稿，非湿实验 SOP）。

### 6.1 一句话

> **多源池化历史高产条件 top-k=5 作为新底物初始化；条件用 OHE；不要默认把历史塞进 GP 加权。**

### 6.2 决策摘要

| 场景 | 默认 | 不要做 |
|---|---|---|
| 胺化多源 + OHE | `topk_warm` k=5 | 默认 sim 加权 / 现有 safe_gate |
| 仅单源 | 可用该源 top-k；预期弱于池化 | 说成等同 LOSO |
| 底物 Morgan | 池化 topk **与** nearest 并列（比 init max） | hashed 近邻当化学相似 |
| Suzuki | 仍可用池化 topk | 声称与胺化同级；只报 vs cold |
| 条件表示 | OHE | 条件 Morgan/DFT 默认 |
| 门控 | 暂无 | 宣称 safe_gate 已安全弃权 |

---

## 七、结论固定与校验

### 7.1 锁档文件

- 效应数字：`FROZEN_CLAIMS.md`（2026-08-20）+ 产品映射附录（2026-08-21）  
- 合并锁：`docs/15_step1_step2_lock.md`（2026-08-22）  
- **改主张须改日期并写明理由；不得用机制回写 Step1 主表数字。**

### 7.2 机器校验结果（2026-08-22）

命令：`python scripts/validate_step1_step2.py`  
报告：`results/step1_step2_validation/report.md`  
结果：**PASS=24 / FAIL=0**

覆盖：job 数、冻结 ΔAUC 再生对账、胺化/Suzuki Q1 形态、Phase A 健全性（不受影响策略 Δ=0）、M1 carried/post_lift、M2 池化占比与 Morgan 换源/init max、文档指针齐全。

### 7.3 对外可引用的固定句（建议）

1. 胺化多源池化下，历史高产条件 **topk init** 有稳健正效应；加权进 GP 不是主收益。  
2. 该增益相对 cold **主要来自初始化清单**，而非后续 BO。  
3. 池化清单优于典型单源；化学底物 Morgan 可使近邻清单的 **init 最高点** 显著改善。  
4. Suzuki 冷启动 BO 不可靠（Q1 失败），但 **topk 相对 cold 仍为正**；不得整包照搬胺化部署叙事。  
5. 条件表示默认 OHE；条件 DFT/Morgan 不升默认。

---

## 八、明确未做 / 后置

| 项 | 说明 |
|---|---|
| 共享 init 消融 | 可解释 Suzuki cold≺random 有多少是协议问题；不改主锁 |
| pair 全量 | 试点已够机制材料 |
| 板效应主实验 / contextual GP / 新采集 | M1 表明主杠杆在 init，不优先 |
| 真实前瞻湿实验 | Step3 之后 |
| 工程 `recommend_init` CLI | 允许落地，属实现层 |

---

## 九、资源与复现

### 9.1 关键路径速查

```
FROZEN_CLAIMS.md
docs/10_step1_transfer_effects.md
docs/11_step1b_representation.md
docs/14_strategy_draft.md
docs/15_step1_step2_lock.md
results/ALL_RESULTS_ANALYSIS.md
results/step1_effects/
results/step2_m1/summary.md
results/step2_m2/summary.md
results/step1_step2_validation/report.md
```

### 9.2 再生命令

```bash
python scripts/analyze_step1_effects.py
python scripts/analyze_step2_m1_init_vs_bo.py
python scripts/analyze_step2_m2_pool_vs_nearest.py
python scripts/validate_step1_step2.py   # 须 24/24 PASS
```

### 9.3 计算说明

- Step1 / Step1b 全量主要在超算（dsub）完成；本机做分析、汇总与校验。  
- 机制 M1/M2 **不新跑 BO**，复用已有 job JSON 与 `data/processed/*_long.csv`。

---

## 十、汇报结语

本阶段完成了从「有没有效应」到「效应从哪来、默认怎么用」的闭环：

| 阶段 | 交付 |
|---|---|
| 效应 | 双库 LOSO 全量 + 冻结主张 + 产品标准澄清 |
| 表示 | Morgan 底物稳健性；条件表示否决并收口 |
| 机制 | init 通道 + 池化优于单源 + Morgan 近邻 init-max 翻盘 |
| 策略 | 可执行默认草稿（topk k=5 + OHE） |
| 质量 | 锁档文档 + 24 项再生校验全通过 |

**建议对外口径：** TransferBO2.0 在胺化上证明「多源历史高产条件 warm-start」有效且机制上主要吃初始化；Suzuki 上同策略相对 cold 仍有正增益但稳健性较弱，不可与胺化同级宣称。下一步优先工程落地与可选附录消融，**不再重开 Step1/Step2 主结论。**

---

*本汇报与 `docs/15_step1_step2_lock.md`、`results/step1_step2_validation/report.md` 一致。数字冲突时以 `FROZEN_CLAIMS.md` 为准。*
