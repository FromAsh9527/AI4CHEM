# TransferBO2.0 结论冻结（LOSO v1 / Step-1 效应）

冻结日期：2026-08-20  
附录日期：2026-08-21（产品映射，不改锁定数字）  
**统计口径（主）**：先对 seed 平均，再在 **target/task** 上汇总；bootstrap 95% CI 跨靶。  
**设计规范**：`docs/10_step1_transfer_effects.md`  
**数字底稿**：`results/step1_effects/summary.md`（由 `scripts/analyze_step1_effects.py` 再生）  
**板级图**：`results/figures/`  

协议：OHE + hashed SMILES；n_init=5，budget=20；历史 = 其余全部底物（多源池化）。  
job 级 NTR 仅附录，不作主推断单位。

本文件是本地锁。改主张必须改日期并写明理由。不得与 TransferBO 1.0（pair / Δfrac）混写成同一部署结论。

---

## 锁定问题（= Step1 Q1–Q4）

1. 冷启动 BO 是否优于随机？  
2. 何种迁移动作相对 cold 有净增益？  
3. 全局多源 topk 是否优于最近邻 topk？  
4. 胺化结论能否平移到 Suzuki？

---

## 锁定主张（措辞不得回退）

1. **胺化 Q1 成立。** 靶级 cold−random = **+107.8**，95% CI **[+75.2, +145.4]**；**15/15** 靶 cold>random。  
2. **胺化主正效应是全局 topk init，不是历史进 GP。**  
   - topk vs cold：**+160.2 [+108.1, +211.6]**，**13/15** 靶 > cold；vs random：**+268.0**，**15/15** > random  
   - nearest vs cold：+117.0 [+69.9, +160.8]，13/15 > cold（弱于 topk）  
   - sim / safe_gate vs cold：CI 贴近 0 或含 0（+19.3 / +11.5），不得当主策略  
3. **全局多源 topk ≻ 最近邻 topk**（init 暖启动家族内）。不得写成「凡多源都更好」。  
4. **Suzuki Q1 不成立。** 靶级 cold−random = **−57.7**，CI **[−140.9, +1.9]**（含 0）；仅 **4/12** 靶 cold>random。  
5. **Suzuki topk vs cold 为正，但不得单独写成可部署。** +149.9 [+38.8, +269.8]；vs random +92.2 [0.0, +186.5]。板异质大；random 亦常赢 cold → 存在“相对烂 cold 的夸大”。  
6. **Q4：禁止跨化学平移部署叙事。** 胺化效应成立 ≠ Suzuki 可照搬。  
7. **语义与范围：** 逻辑板；多源 LOSO ≠ 一对一 pair；效应 ≠ 机制 ≠ 策略。  
8. **Step1 已按 DoD 收口**（见 `docs/10_step1_transfer_effects.md` §5）。后续机制/策略不得改写本步问题。

---

## 锁定数字（靶级主表）

### 胺化（15 targets × 5 seeds）

| strategy | Δcold mean [95% CI] | 靶胜率>cold | Δrandom mean [95% CI] | 靶胜率>random | job NTR* |
|---|---|---:|---|---:|---:|
| topk_warm | **+160.2 [+108.1, +211.6]** | **0.87** | **+268.0 [+216.3, +316.1]** | **1.00** | 0.093 |
| nearest_topk_warm | +117.0 [+69.9, +160.8] | 0.87 | +224.7 [+178.5, +267.7] | 1.00 | 0.173 |
| sim_weighted | +19.3 [−1.1, +35.5] | 0.73 | +127.1 [+97.3, +153.5] | 1.00 | 0.387 |
| safe_gate | +11.5 [−17.6, +35.2] | 0.67 | +119.3 [+93.7, +141.8] | 1.00 | 0.320 |
| cold_start | — | — | +107.8 [+75.2, +145.4] | 1.00 | — |
| random | −107.8 [−145.4, −75.2] | 0.00 | — | — | 0.667 |

\*附录。

### Suzuki（12 targets × 5 seeds）

| strategy | Δcold mean [95% CI] | 靶胜率>cold | Δrandom mean [95% CI] | 靶胜率>random | job NTR* |
|---|---|---:|---|---:|---:|
| topk_warm | +149.9 [+38.8, +269.8] | 0.83 | +92.2 [0.0, +186.5] | 0.83 | 0.283 |
| safe_gate | +80.7 [+27.9, +143.7] | 0.75 | +23.0 [−16.5, +62.2] | 0.50 | 0.400 |
| random | +57.7 [−1.9, +140.9] | 0.67 | — | — | 0.467 |
| sim_weighted | +53.1 [+20.7, +87.9] | 0.83 | −4.6 [−71.4, +54.3] | 0.50 | 0.417 |
| nearest_topk_warm | +24.0 [−159.0, +193.0] | 0.75 | −33.6 [−198.6, +93.1] | 0.67 | 0.483 |
| cold_start | — | — | **−57.7 [−140.9, +1.9]** | **0.33** | — |

---

## 停止 / 仍允许

**停止：** 用 job-IID 重写主结论；Suzuki 只报 vs cold；把胺化整包叙事平移到 Suzuki；把 Step1 写成策略完成。  

**仍允许：** 再生校验（`scripts/validate_step1_step2.py`）；Step3 策略草稿修订；更严弃权门控（须新实验）；pair / 共享 init 作附录材料；SI 图。  
**Step2 机制已锁：** `docs/15_step1_step2_lock.md`（2026-08-22）。不得用机制回写上表数字。  

## 终局一句

胺化多源池化下，历史高产条件 warm-start 有稳健正效应；加权进 GP 不是主收益。Suzuki 上冷启动 BO 不可靠，**不得把胺化部署叙事整包平移**；topk 相对 cold 的正增益仍是历史利用策略的证据（见附录）。

---

## 附录（2026-08-21）— 产品映射，不改上面数字

**理由：** 产出定义为「历史 BO 数据利用策略」。Q1 回答的是冷启动 GP 相对 20-shot 随机是否成立，与「topk 是否优于同预算基线」不是同一句话。附录只约束**读法**；Q1–Q4 数字与 2026-08-20 锁定主张不改。

1. **产品成功标准 ≠ Q1。** 策略是否可行：相对 **cold 与 random** 是否有净增益。Q1 只描述基线 BO 质量。  
2. **主张 5 的精确含义：** 「不得单独写成可部署」= 不得因 topk>cold 就宣称与胺化同级、可跨库照搬。**不是**「topk 无效」。Suzuki topk vs cold = +149.9 [+38.8, +269.8]；不存在 topk≺cold。vs random = +92.2，CI 下沿贴 0 → 可行但脆。  
3. **主张 3 的协议条件：** topk ≻ nearest 锁定在 **OHE + hashed**。底物 Morgan 下 nearest ≳ topk（Step1b），属稳健性发现，**不回写**主张 3。  
4. **主张 6 不变：** 禁止跨化学平移**部署叙事**；允许分开报告 Suzuki 上 topk 的效应量。  
5. **表示轴已收口**（`docs/11_*`）：不重开本文件数字。条件默认 OHE；DFT / 条件 Morgan 不升默认。

规划：`docs/12_plan_after_step1.md`。收口戳：`docs/13_step1_closeout.md`。  
Step1+Step2 锁：`docs/15_step1_step2_lock.md`。校验：`results/step1_step2_validation/report.md`。
