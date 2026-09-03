# Step 1 — 历史迁移对新底物 BO 的效应（研究纲领，做扎实）

冻结日期：2026-08-20  
阶段定位：研究框架第 **1** 步（效应）  
下游：第 2 步机制、第 3 步策略——**不得反向改写本步问题**  
总锁：`FROZEN_CLAIMS.md`（主张）← 本文件（设计与统计规范）← `results/step1_effects/`（数字）

---

## 0. 本步只回答什么

在**固定协议**下，历史数据以不同迁移动作进入回路后，对新底物序贯 BO 的**可观测效应**是什么？

不回答：化学机制、最优门控、工业部署 SOP、1.0 pair-Δfrac 等价性。

---

## 1. 预注册问题（Q1–Q4）

| ID | 问题 | 主对照 | 成功/失败读法 |
|---|---|---|---|
| **Q1** | 冷启动 BO 是否优于随机？ | cold − random | 靶级均值 Δ>0 且多数靶 cold>random → 基线成立 |
| **Q2** | 哪类迁移动作相对 cold 有净增益？ | strategy − cold | 报告效应量 + 靶级胜率；不以单 seed 故事定论 |
| **Q3** | 全局多源 topk 是否优于最近邻 topk？ | topk − nearest（靶级） | 仅限 init 暖启动家族 |
| **Q4** | 胺化结论能否平移到 Suzuki？ | 同协议跨库对照 | 任一库 Q1 失败或符号冲突 → **禁止**跨库部署叙事 |

辅问题（不升格为主终点）：final_best、hit10；job 级 NTR（连续性）。

---

## 2. 设计锁定

| 项 | 锁定内容 |
|---|---|
| 协议 | LOSO；历史 = 其余全部底物（**多源池化**） |
| 库 | 胺化 15×260；Suzuki 12×308 |
| 表示 | 条件 OHE；底物 hashed SMILES（仅相似/加权策略） |
| 优化器 | GP (Matern-2.5 ARD) + EI；n_init=5，budget=20 |
| 策略集 | random, cold_start, topk_warm, nearest_topk_warm, sim_weighted, safe_gate |
| 种子 | 0–4（全量） |
| 板语义 | 逻辑任务板，非物理批次 |

一对一 \(S\to T\)、topk 消融、新门控属于 **Step1 的敏感性/延伸**，不替换主表；主表以 `amination_v1_full` / `suzuki_v1_full` 为准。

---

## 3. 统计规范（严谨性核心）

### 3.1 推断单位

**Target / task（底物或偶联对）**，不是把每个 (target, seed) job 当 IID。

步骤：

1. 对每个 (strategy, target) 先对 seed 取平均 → 得到靶级 AUC；  
2. 在靶上计算 Δ（vs cold / vs random）；  
3. 跨靶报告：均值、中位数、**靶 bootstrap 95% CI**（B=5000）；  
4. 靶级胜率：\(P_{\mathrm{target}}(\mathrm{AUC}_{str}>\mathrm{AUC}_{ref})\)。

### 3.2 主终点 / 次终点

- **主终点**：靶级 mean ΔAUC vs cold；Q1 额外要求 vs random。  
- **次终点**：靶级 ΔAUC vs random；hit10；final_best；job 级 NTR（附录）。

### 3.3 禁止的夸大

- 只用 job 级均值、不报靶异质性。  
- Suzuki 上仅报 vs cold、隐瞒 vs random。  
- 把试点或单板故事写成全库效应。  
- 把 Step1 效应写成“已可部署策略”。

---

## 4. 产出清单（扎实 = 可复核）

| 产出 | 路径 |
|---|---|
| 本纲领 | `docs/10_step1_transfer_effects.md` |
| 分析脚本 | `scripts/analyze_step1_effects.py` |
| 效应表 | `results/step1_effects/effects_{amination,suzuki}.csv` |
| 靶级明细 | `results/step1_effects/target_deltas_*.csv` |
| 文字摘要 | `results/step1_effects/summary.md` |
| 森林图 | `results/step1_effects/forest_*_vs_{cold,random}.png` |
| 板级柱/热图 | `results/figures/*_per_plate_*`（已有） |
| 主张锁 | `FROZEN_CLAIMS.md` |

再生：

```bash
python scripts/analyze_step1_effects.py
python scripts/plot_per_plate_gain.py
```

---

## 5. Step1 完成判据（DoD）

全部满足才算“第一步扎实”：

1. Q1–Q4 均有预注册式回答，且胺化 / Suzuki **分开写**。  
2. 主表为**靶级**效应 + CI + 胜率；job NTR 仅附录。  
3. 同时给出 vs cold 与 vs random。  
4. 板级图齐全，异常靶（如胺化 s4/s6、Suzuki t10/t11）在正文点名但不单独改结论。  
5. 明确边界：多源池化 ≠ pair；效应 ≠ 机制 ≠ 策略。  
6. `FROZEN_CLAIMS.md` 与 `results/step1_effects/summary.md` 数字一致（靶级为主）。

---

## 6. 与第 2、3 步的交界

| 若 Step1 显示… | 则 Step2/3 应… |
|---|---|
| 胺化 topk 强正、sim 弱 | 机制上优先解释 **init 条件共享**，而非 GP 加权 |
| Suzuki Q1 失败 | **基线 BO 备注**（cold 不可靠）；**不要**因此默认弃权。历史策略仍看 topk vs cold **和** vs random；禁止胺化整包叙事平移 |
| hashed 下近邻 < 全局 topk | 机制上质疑 hashed 相似；Step1b 已表明 Morgan 下近邻可追上（不回写 Q3 数字） |

未完成 Step1 DoD 前，不开放大规模策略搜索。  
Step1 DoD 已满足（2026-08-20）。产品读法与后续顺序：`FROZEN_CLAIMS.md` 附录、`docs/12_plan_after_step1.md`。
