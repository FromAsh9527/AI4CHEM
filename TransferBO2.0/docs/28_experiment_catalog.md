# TransferBO2.0 实验全览（2026-08-24 整理）

> **用途**：把所有做过的实验按研究阶段登记——每个实验的**设计目的、规模、主结果、结论、对应可视化图**。
> 数字均为锁定值（FROZEN_CLAIMS / P4 摘要 / 策略研究摘要），与 `results/paper_numbers/manifest.md` 核对一致。
> 图统一存放：`results/figures/<exp>_<name>.png`；生成脚本：`scripts/make_experiment_figs.py`（可复跑）。
> 推断口径：target 级（seed 平均→靶级→配对 bootstrap 95% CI，B=5000）；主指标 AUC@20。

---

## 0. 总览表

| # | 阶段 | 实验名 | 目录 | 规模 | 图 |
|---|---|---|---|---|---|
| 1 | Step1 效应 | 胺化 LOSO 主表 | `results/amination_v1_full` | 450 jobs (15×6×5) | `step1_amination_effects.png`, `bsf` |
| 2 | Step1 效应 | Suzuki LOSO 主表 | `results/suzuki_v1_full_rt/suzuki_v1_full` | 360 jobs (12×6×5) | `step1_suzuki_effects.png`, `bsf` |
| 3 | Step1 补充 | 胺化 topk 消融 | `results/amination_topk_ablation` | 525 | （旧图 per_plate） |
| 4 | Step1 补充 | pair 试点（单源→靶） | `amination/suzuki_pair_v1_pilot` | 126×2 | （旧图 per_plate） |
| 5 | Step1b | Rep-A Morgan 底物 | `amination/suzuki_rep_A_morgan_sub_full` | 450+360 | `step1b_repA_morgan_substrate.png` |
| 6 | Step1b | Rep-B DFT 条件试点 | `suzuki_rep_B_dft_cond_pilot` | 36 | `step1b_repB_dft_pilot.png` |
| 7 | Step1b | Rep-B both Morgan | `morgan_both_(suzuki|amination)_full` | 450+360 | （表格见 ALL_RESULTS_ANALYSIS） |
| 8 | Step2 机制 | M1 init vs 续跑 | `results/step2_m1` | 胺化+Suzuki | `step2_m1_init_vs_post.png` |
| 9 | Step2 机制 | M2 池化 vs 近邻 | `results/step2_m2` | 四库 | `step2_m2_pool_vs_nearest.png` |
| 10 | Step3 P0 | Suzuki shared-init/matched-post | `results/suzuki_p0_shared_init` | 360 | `p0_matched_init.png` |
| 11 | Step3 P0 | 胺化 matched-init（C1/C2/C3） | `results/amination_matched_init_audit` | 150 | `p0_matched_init.png` |
| 12 | Step3 P1/P2 | 源数门槛+清单稳定性 | `results/p1p2_source_robustness` | 离线 | `p1p2_source_robustness.png` |
| 13 | P4 外部验证 | borylation（主外部库） | `results/p4_borylation` | 990 jobs | `p4_borylation_effects.png`, `per_target` |
| 14 | P4 外部验证 | HiTEA Suzuki（第二外部库） | `results/p4_hitea` | 330 jobs（08-24 修复重跑） | `p4_hitea_effects.png`, `per_target` |
| 15 | 机制 | 排序保持+双通道 | `results/rank_preservation` | 离线 | `rank_preservation.png` |
| 16 | 策略研究 | 清单聚合规则 | `results/strategy_list_rules` | 四库 | `strategy_list_rules.png` |
| 17 | 策略研究 | 续跑事前规则（additive R²） | `results/strategy_continuation` | 离线 | `strategy_continuation_c1.png` |
| 18 | 策略研究 | 探针门 G2 | `results/strategy_probe_gate` | 离线回放 | `strategy_probe_gate.png` |
| 19 | 策略研究 | rank_median AUC 复核 | `results/rankmed_audit_compare` | 355 jobs | `rankmed_audit_compare.png` |
| 20 | 策略研究 | 四臂 warm 续跑 | `results/continuation_arms_compare` | 230 jobs (Suzuki 类) | `continuation_arms.png` |
| 21 | 边界验证 | CHAOS 一维 | `results/chaos_validation` | 100 jobs | `chaos_validation.png` |

---

## 1. Step1 效应（主锁，08-20）

### 1.1 胺化（Pd C–N，15×260，450 jobs）— `step1_amination_effects.png`

**设计**：LOSO——每个目标底物，历史 = 其余 14 个底物（多源池化）；6 策略 × 5 seeds；回答"历史能否加速新底物 BO"。
**主结果**（锁定，FROZEN）：

| 策略 | AUC@20 | vs cold | frac>cold | vs random |
|---|---|---|---|---|
| **topk_warm** | 1359.5 | **+160.2 [+108.1, +211.6]** | 0.87 | +268.0 [+216.3, +316.1] |
| nearest | 1316.2 | +117.0 | 0.87 | +224.7 |
| sim_weighted | 1218.6 | +19.3（null） | 0.73 | +127.1 |
| safe_gate | 1210.8 | +11.5（null） | 0.67 | +119.3 |
| cold | 1199.3 | — | — | +107.8 [+75.2, +145.4] |
| random | 1091.5 | — | — | — |

**结论**：冷启动 BO 本身优于随机（15/15）；**全局多源 topk 清单是主正增益**（+160，CI 排除 0）；sim/safe_gate ≈ null → "历史进 GP 无效，历史进清单有效"。**BSF 曲线**（`step1_amination_bsf.png`）：前 5 步即拉开 ~25 产率点。

### 1.2 Suzuki（Pd C–C，12×308，360 jobs）— `step1_suzuki_effects.png`

**主结果**：cold vs random **−57.7**（仅 4/12 靶赢 random）→ **Q1 失败 = 冷启动 BO 在此模板不可靠（备注，非 topk 无效）**；topk vs cold **+149.9 [+38.8, +269.8]**（排除 0）；vs random +92.2 [0.0, +186.5]（**可行但脆**——CI 贴 0）。

**读法纪律**：不得把胺化叙事整包平移；"Suzuki topk 仍成立但脆弱，且价值位置不同（见 M1）"。

### 1.3 补充：topk 消融 + pair 试点

- **topk 消融**（525 jobs）：k=5 ≡ k=10；k=3≈k=5；safe_gate 未触发弃权——k=5 是设计单元（每轮 5 个，湿实验同款）。
- **pair 试点**（126×2，单源→靶）：单源 topk 弱于池化 LOSO；Suzuki 仍见 cold≺random 倾向 → **1.0 pair 负效应的机制线索：单源噪声被当知识**。

---

## 2. Step1b 表示轴稳健性（08-21）

### 2.1 Rep-A 底物 Morgan（450+360 jobs）— `step1b_repA_morgan_substrate.png`

**设计**：只换底物指纹（hashed → Morgan r2，条件仍 OHE），检验主锁对表示的敏感性。
**结果**：topk 效应**不变**（健全）；**nearest 大幅变强**（胺化 → +171 高于 topk、Suzuki hashed 近 null → Morgan +166）——但 M2 判定：**默认仍是池化 topk；Morgan 下 nearest 可并列**（不升默认）。

### 2.2 Rep-B 条件 DFT 试点（36 jobs）— `step1b_repB_dft_pilot.png`

topk 相对 OHE −157；cold≈random → **不升全量**，条件默认 **OHE**。both-Morgan（条件+底物均 Morgan）同样不支持升级。

---

## 3. Step2 机制（08-22）

### 3.1 M1：init 通道 vs 续跑通道 — `step2_m1_init_vs_post.png`

**设计**：把 topk vs cold 的 ΔAUC 分解为 carried（init 段优势，含"起点即领先"）与 post_lift（后段额外提升），回答"价值在哪"。
**结果**（四库）：

| 库 | carried Δ | post_lift Δ | 判定 |
|---|---|---|---|
| 胺化 | +278 | −118 | **init 主导** |
| Suzuki | +134 | +16 | init 主导*（弱） |
| borylation | +186 | −78 | **init 主导** |
| HiTEA | +46 | −20 | 两通道皆弱 |

*Suzuki 的 post_lift 相对 cold 为正在 M1 里是 +16，但绝对 topk post（+189）是四库最大（见 M1 补充/双通道节）——**价值位置库相关**，这是后续"分库续跑规则"的机制来源。

### 3.2 M2：池化 vs 近邻 — `step2_m2_pool_vs_nearest.png` + `step2_m2_morgan_mechanism.png`

**结果**：胺化池化 +160.2 > nearest +117.0；Suzuki 池化 +149.9 > nearest +24.0（hashed）/Morgan 下 nearest 翻盘但仍不稳定；**多源池化是稳健默认**（2026-08-24 复核：borylation/HiTEA nearest 数值更高但跨库不一致、无法事前识别——"nearest 是彩票"）。

**Morgan 机制解释（M2-C 锁定，机制图 `step2_m2_morgan_mechanism.png`）**：Morgan 下 nearest 翻盘 ≠ 全局排序更准——
- **换源**：近邻源几乎全部更换（胺化 100%），hashed 的"相似"是字符串相似，Morgan（ECFP r2）才是化学子结构相似；
- **看 init max 不是 Spearman**：胺化 hashed-NN Spearman 0.761 → Morgan-NN **0.503（更低）**，但 top-5 落到靶上的最好条件 **62.6 → 68.6（更高，超池化 65.7）**；Suzuki max 68.1 → **78.7**；
- **为什么 AUC 吃 max**：M1 已证明主增益在 init 通道（carried），AUC 直接吃"第 1 轮最好条件"——Morgan 化学近邻更容易把至少一个高产条件送进 init；
- **结论**：表示救的是"选对源、送进顶条件"，不是"整体排序更准"；sim 加权不改 init（Morgan 下仍 null +16），不是主通道。

---

## 4. Step3 P0/P1/P2（08-22，策略研究前奏）

### 4.1 Suzuki shared-init / matched-post（360 jobs）+ 胺化 matched-init（150 jobs）— `p0_matched_init.png`

**设计**：固定 init、只换后段（EI vs random），分离"起点价值"与"过程价值"。
**结果**：
- Suzuki **C1**（topk+EI − topk+random）≈ +75 → 给定好起点后 EI 有正价值；
- 胺化 **C1** = +26.0（CI 含 0，topk 后 EI 边际弱）、**C2** = +67.7（CI 排除 0，cold 下 EI 有效）；
- → "**历史管起点，优化器管精修**"；C1/C2 的库间差异 = 分库续跑规则直接依据。

### 4.2 P1/P2 源数门槛（离线）— `p1p2_source_robustness.png`

n=1 Jaccard≈0.17、init_best 低于全池 2%；**≥3 启用、≥5 推荐**；清单稳定性跨源差（HiTEA 0.11–0.40）→ **source coverage 强制上报**。

---

## 5. P4 外部验证（08-23；HiTEA 08-24 修复重跑）

### 5.1 borylation — Ni C–B，33×46，990 jobs（主外部库）— `p4_borylation_effects.png` / `p4_borylation_per_target.png`

**结果**（锁定）：topk vs cold **+107.6 [73.1, 144.9]**、vs random **+123.4 [89.1, 158.7]**（均排除 0）；88%/94% 靶为正；init_best +8.63 排除 0、final_best +0.31≈0 → **强复现（init 模式）→ 策略升"跨源已验证"**；跨反应类（Ni C–B）验证。

### 5.2 HiTEA Suzuki — Pd C–C，11×41–48，330 jobs（第二外部库）— `p4_hitea_effects.png` / `p4_hitea_per_target.png`

**结果**（08-24 特征退化修复后重跑版）：topk vs cold **+26.3 [−32.2, +80.9]**、vs random +36.9 [−10.5, +83.7]（方向正、CI 含 0）；final_best +0.22 含 0；**C2 修复后 +20.4 排除 0**（后段 EI 真实有效）。→ **弱方向正（部分复现）**；小空间（41–48）+ 30% 失败压缩效应。

> ⚠️ 修复记录：原报 +47.0/+3.19 排除 0 系 ingest 因子列全 NULL → OHE 退化 → EI 顺序扫描伪影；08-24 修复（众数填充）+ 重跑，结论如实降级（docs/18 §8.3）。

---

## 6. 排序保持机制（08-24）— `rank_preservation.png`

**设计**：四库跨底物条件排序 Spearman + 池化 top-5 在靶内落位，回答"为什么排序可迁移、数值不可迁移"。
**结果**：ρ = 胺化 0.577 / borylation 0.361 / Suzuki 0.264 / HiTEA 0.088 / CHAOS 0.694（五库全正）；顶部比整体更稳（池化 top-5 落位 22.7/260、14.6/46 vs 87.7/308、38/48）。
**化学解释**：条件好坏排序由配体/碱本征性质（模板通用）决定；产率水平由底物活性（特异）决定 → 排序可迁移、数值不可；**清单带排序、GP 学数值**；池化 = 跨底物排序投票平均掉特异噪声。
**附**：learability 靶级 borylation +0.427 (p=0.01) 系脚本哈希种子伪影，08-24 确定性修复后 +0.098 不显著（靶级显著证据撤回，分工机制保留库级方向 + additive R² 负相关）。

---

## 7. 策略研究四组件（08-24）

### 7.1 清单规则 — `strategy_list_rules.png`
init 层：rank_median +1.78 显著；**AUC@20 复核**：pooled +1.5 持平、Suzuki +34.8（AUC@5 +20.3 显著）、HiTEA −30.0（不显著）→ **默认 mean；rank_median 仅 Suzuki 类可选；稀疏面板禁用**。

### 7.2 续跑规则 — `strategy_continuation_c1.png`
C1 库级差异（Suzuki +75.5 > 胺化 +26.0/borylation +13.6/HiTEA +20.5）→ **init 型库 EI 可选、Suzuki 类 EI 必选**；additive R² 分档事前规则不可行（p=0.69）。

### 7.3 探针门 G2 — `strategy_probe_gate.png`
round-1 的 5 点观测 = 探针（零额外成本）；探针有效性 +0.319（四库全正）、G2 选源池化 init_best 三库正；**AUC@20 未验证**（单步 EI 协议无操作空间）→ 定位**批量协议（湿实验）下待验证组件**。

### 7.4 rank_median AUC 复核 — `rankmed_audit_compare.png`
355 jobs（四库重跑，mean vs rank_median）：pooled +1.5 [−14.8, +18.4]（持平）、Suzuki +34.8、HiTEA −30.0 → 结论修正：**不全面升级**。

### 7.5 四臂 warm 续跑 — `continuation_arms.png`
**设计**：回答"为什么不全程把 topk 条件加入 BO"——A=topk+EI；B=+top-5 历史行 warm；C=+全部历史 warm；D=topk+random（Suzuki 类 23 靶，230 jobs）。
**结果**：**B vs A −59.1 [−139.0, −3.6] 显著负**；C vs A −28.5 [−66.2, +4.3] 负趋势；C vs B +53（warm 广度>精度，但都不如无 warm）→ **历史数据不应以 warm 点进入 target GP；清单（init）是历史价值的正确载体**。

---

## 8. CHAOS 一维边界验证（08-24）— `chaos_validation.png`

**设计**：4 固定反应 × 720 共享添加剂（Science 2022）；条件空间一维；板内 z(log UV) 去水平保排序；检验"清单机制是否依赖多维条件结构"。
**结果**：排序保持 **0.694（五库最高）**；topk 4/4 靶正（+8.1，n=4 方向性）；**续跑零增益**（topk vs topk_random Δ=0，清单一次吃光信号）→ 机制不依赖多维结构；**一维下清单=全部信号（极端 init 模式）**。

---

## 9. 汇总：证据链闭合图

```
Step1 效应（胺化+160✅/Suzuki+150 脆）→ Step1b 表示稳健（OHE+Morgan 收口）
→ Step2 机制（M1 init/续跑分位、M2 池化>近邻、C1/C2 分离）
→ P0 匹配初始化（C1 弱/C2 强）→ P1/P2 源数门槛（≥3/≥5、coverage）
→ P4 外部验证（borylation 强复现 ✅ / HiTEA 弱方向正，2026-08-24 修复重跑）
→ 排序保持机制（五库 ρ 全正 + 顶部更稳 + 化学解释）
→ 策略四组件（mean 清单 / 分库续跑 / G2 待验证 / coverage）
→ 四臂 warm 负结果（历史只进 init）
→ CHAOS 一维边界（机制不依赖多维结构）
→ 正文 v2 + Claims register（docs/26）
```

---

## 10. 复现说明

- 全部图：`python scripts/make_experiment_figs.py`（matplotlib，中文字体 Microsoft YaHei）
- 论文数字：`python scripts/make_paper_numbers_manifest.py` → `results/paper_numbers/manifest.md`
- 结果 JSON 路径见 `docs/19_work_snapshot.md` §9 与各实验 `summary.md`
