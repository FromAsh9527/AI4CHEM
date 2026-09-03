# Step1 + Step2 锁档（2026-08-22）

本文件把 **效应（Step1）** 与 **机制（Step2）** 一并固定。  
改主张须改日期并写明理由。策略草稿见 `docs/14_strategy_draft.md`（Step3，可改操作细则，不得回写本锁数字）。

校验脚本：`python scripts/validate_step1_step2.py` → `results/step1_step2_validation/`

---

## 1. 范围

| 步 | 回答什么 | 锁什么 | 不锁什么 |
|---|---|---|---|
| Step1 | 历史迁移动作的可观测效应 | Q1–Q4 数字与主张 | 机制、SOP |
| Step1b | 换表示后效应是否仍成立 | 条件默认 OHE；底物近邻用 Morgan | 新表示实验 |
| Step2 M1 | 增益在 init 还是后续 BO | 「相对 cold，主增益在 init 通道」 | 共享 init 消融 |
| Step2 M2 | 池化 vs 单源；Morgan 近邻翻盘 | 「池化优于典型单源；翻盘看 init max」 | pair 全量 |

---

## 2. Step1 固定（不改数字）

权威：`FROZEN_CLAIMS.md`（2026-08-20）+ 附录（2026-08-21 产品映射）。  
收口戳：`docs/13_step1_closeout.md`。

| ID | 锁定句 |
|---|---|
| S1-A | 胺化 Q1 成立；主正效应 = 多源 **topk init**，不是 GP 加权 |
| S1-B | hashed 下全局 topk ≻ nearest（协议条件：OHE+hashed） |
| S1-C | Suzuki Q1 不成立 = **基线 BO 备注**，不是 topk 无效 |
| S1-D | Suzuki topk vs cold 为正；不得整包平移胺化部署叙事 |
| S1-E | 产品成功标准 = 策略 vs cold **和** vs random（≠ Q1） |

关键数字（靶级）：胺化 topk Δcold **+160.2 [+108.1,+211.6]**；Suzuki topk Δcold **+149.9 [+38.8,+269.8]**。

---

## 3. Step1b 固定（表示轴收口）

权威：`docs/11_step1b_representation.md` §11。

| ID | 锁定句 |
|---|---|
| R-A | Phase A：topk/cold/random 与 hashed **一致**（健全）；Morgan 下 nearest ≳ topk |
| R-B | 条件默认 **OHE**；条件 Morgan / DFT **不升默认** |
| R-C | 不回写 Step1 主张 3 的 hashed 数字 |

---

## 4. Step2 固定（机制）

### M1 — `results/step2_m1/`

| ID | 锁定句 |
|---|---|
| M1-A | 胺化 topk vs cold：ΔAUC 由 **init 通道（carried）** 主导；post_lift 相对 cold 为负（cold 起点差、后面涨得多） |
| M1-B | Suzuki topk vs cold：同样 carried 主导（约 89%） |
| M1-C | 交付含义：优先 **warm-start 清单**，不先堆 GP |

再生：`python scripts/analyze_step2_m1_init_vs_bo.py`

### M2 — `results/step2_m2/`

| ID | 锁定句 |
|---|---|
| M2-A | 胺化：池化 top5 在靶上均产 **高于** 单源平均（约 93% 靶） |
| M2-B | pair 试点同靶：池化 LOSO topk AUC **高于** 单源 pair topk |
| M2-C | Morgan 近邻翻盘：近邻源大量更换；看的是 **init max**，不是全局 Spearman 升高 |
| M2-D | 默认清单仍是 **多源池化 topk**；Morgan 下 nearest 可并列 |

再生：`python scripts/analyze_step2_m2_pool_vs_nearest.py`

---

## 5. 停止 / 仍允许

**停止（锁后）：**

- 重跑 Step1 LOSO 改主表数字（除非发现接线 bug，须开新版本冻结）  
- 用 Step1b/Step2 回写 `FROZEN_CLAIMS` 主表  
- 用 Q1 否决 Suzuki topk  
- 把机制结论写成「已完成湿实验验证」  
- pair 全量 / 新表示 / DFT 全量当主证据  

**仍允许：**

- 再生分析脚本做校验（本锁要求）  
- Step3 策略草稿修订（`docs/14_*`）  
- 共享 init 等小消融（附录，不改主锁）  
- 实现 `recommend_init` 等工程落地  

---

## 6. 校验清单（机器 + 人工）

| # | 检查 | 通过标准 |
|---|---|---|
| V1 | 胺化/Suzuki job 数 | 450 / 360 JSON |
| V2 | 再生 Step1 效应 vs 冻结表 | 关键 Δ 与冻结值 \|差\| ≤ 0.2 |
| V3 | Phase A topk 与 hashed | 胺化 topk Δcold 差 = 0（健全） |
| V4 | M1 胺化 topk vs cold | carried 占比 ≥ 1.0 且 post_lift < 0 |
| V5 | M2 胺化池化 vs 单源 | frac 池化>单源平均 ≥ 0.8 |
| V6 | M2 Morgan 换源 | 胺化 nn_changed 比例 ≥ 0.9 |
| V7 | 文档指针齐全 | 本文件 + FROZEN + M1/M2 summary + 策略草稿存在 |

跑完后看 `results/step1_step2_validation/report.md`：须全部 PASS 才算本锁生效。

---

## 附录 A — P0 shared-init 审计（2026-08-22）

**不改写**上文 Step1/Step2 主表数字；仅补充 Suzuki **解释边界**与 Step3 策略依据。

| ID | 主张 | 数值 / 判定 |
|---|---|---|
| P0-1 | 胺化接线健全；Step1 可复现 | sanity 60/60；\|ΔAUC\| vs `amination_v1_full` = 0 |
| P0-2 | Suzuki 全量完成 | 360/360；\|ΔAUC\| vs `suzuki_v1_full` = 0 |
| P0-3 | init 匹配有效 | cold ≡ cold_random_post init_best；topk ≡ topk_random_post |
| P0-4 | Suzuki Q1 失败 ≈ **EI 弱**，非 init 运气（**弱证据**：CI 含 0，写作须限定「与 EI 弱一致」） | C2 = cold-EI − cold-random = **−21.3** [−60.3, +9.0] |
| P0-5 | Suzuki topk+EI 后续仍有益 | C1 = topk-EI − topk-random = **+75.5** [+15.5, +161.7] |
| P0-6 | Suzuki init alone ≈ 随机 5 点 | C4 init_best Δ ≈ **−0.9**；不得写成「只做 5 点就够」 |
| P0-7 | Step1 Suzuki 效应量不变 | C3 +149.9、C5 +92.2 与冻结表一致 |

权威细节：`docs/17_step3_experiment_plan.md` §3.8 · `results/suzuki_p0_shared_init/summary.md`

---

## 附录 B — P1+P2 清单稳定性（2026-08-22，离线）

不改写 Step1 主表；补充 **部署门槛** 与 CLI 审计字段。

| ID | 主张 |
|---|---|
| P1B-1 | 胺化 pooled top-5 的 **条件 ID** 对 source 子集敏感：n=1 Jaccard≈0.17，n=5≈0.50 |
| P1B-2 | 胺化 **init_best**：n=5 靶均 66.4 vs 全池 65.7；n=3 Δinit CI 仍跨 0 |
| P1B-3 | **默认门槛**：≥3 历史底物启用；**推荐 ≥5**；必须报 source coverage |
| P1B-4 | n=1 明显弱于多源（Δinit≈−1.7）→ 禁止单源冒充 LOSO 池化 |
| P1B-5 | Suzuki 更不稳定（n=5 Jaccard≈0.26）→ 边界库，门槛建议 ≥5 |

---

## 附录 C — 胺化 matched-init 审计（2026-08-22，审计补跑）

不改写 Step1 主表；把胺化「EI 续跑价值」从 M1 事后分解 + 2 靶 sanity 升级为**全靶控制实验**（150 jobs）。权威细节：`docs/17_step3_experiment_plan.md` §3.9 · `results/amination_matched_init_audit/summary.md`。

| ID | 主张 | 数值 / 判定 |
|---|---|---|
| MIA-1 | 胺化 init 匹配有效 | C1/C2 的 AUC@5、init_best Δ = 0（与 P0-3 同构） |
| MIA-2 | 冷启动下 EI 有效 | C2 = cold-EI − cold-random = **+67.7** [+37.0, +100.4]，0.87 靶>0 |
| MIA-3 | topk 起点下 EI 增值**弱**（CI 含 0） | C1 = topk-EI − topk-random = **+26.0** [−5.9, +71.7]，0.47 靶>0 |
| MIA-4 | 历史清单配任何续跑都赢 cold-BO | topk+random − cold+EI = **+134.2** [+49.2, +208.0]；final_best Δ = +0.07（终点相同） |
| MIA-5 | **镜像结论**：迁移价值位置库相关 | 胺化价值在 init（EI 可选）；Suzuki 价值在 EI（C1 +75.5） |
| MIA-6 | 轮次口径警示 | 优势在命中 top-5%（早 ~1 轮）/ AUC@5（+93.6）；**绝对 ≥70% 阈值下优势消失**（r70 Δ≈0，达标率 ~0.47） |

产出：`results/p1p2_source_robustness/` · 脚本：`scripts/analyze_p1p2_list_stability.py`
