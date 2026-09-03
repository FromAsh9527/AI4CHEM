# Step3 策略草稿（2026-08-22；2026-08-23 P4 跨源升级；2026-08-24 策略研究机制化升级）

状态：**草稿（可执行默认）；跨源方向已验证（P4 borylation 强复现）；策略四组件已机制化（`docs/24` §7）**，不是湿实验 SOP，也不是论文终稿。  
依据：Step1 效应锁 + Step1b 表示收口 + Step2 M1/M2 + **P0** + **P1 离线** + **胺化 matched-init 审计（2026-08-22，`docs/17` §3.9）** + **P4 外部验证（2026-08-23：borylation 强复现、HiTEA 部分复现；2026-08-24 HiTEA 条件特征修复后重跑复核，`docs/18` §8–9）** + **策略研究（2026-08-24：清单规则/续跑/探针门，`docs/24` §7、`results/strategy_*`）**。  
数字不改写 `FROZEN_CLAIMS.md`。

产品目标：给定历史 HTE/BO 数据与新底物，**默认怎么用历史**。

---

## 0. 评估纪律（2026-08-24 确认，全程适用）

1. **主指标一律为 Optimisation AUC**（Σ BSF，默认 B=20）；策略判定、对比、升级与否**只以 AUC 为准**；
2. **B 的取值**：默认 20，依据部署语义 = 每轮 5 次实验 × 4 轮（常规 BO 4 轮内可收敛）；原则上可按条件库大小调整（如小条件空间可缩小 B），但任何调整必须在对比的两侧一致；
3. init_best / AUC@k / 轮次指标 = **辅助诊断**，用于解释 AUC 差异的来源（init 段 vs 续跑段），**不作策略判定依据**（2026-08-24 经验：init 层 +1.78 的结论被 AUC@20 复核推翻）；

---

## 1. 一句话默认

> **多源池化 top-5 条件清单作 round-1（k=5，默认 mean 规则）；条件特征用 OHE；历史不进 GP；round-1 后可选选源门控（免费）；续跑（EI）按库型决定。**

- **胺化**：增益主要在「先做对点」（M1 carried 主导；**2026-08-22 胺化 matched-init 审计**：C2 = +67.7 [CI 排除 0] 证明冷启动 EI 有效，C1 = +26.0 [CI 含 0] 证明给定 topk 起点后 EI 增值弱，topk+随机续跑已赢 cold+EI +134.2）；后续 BO **可选**。
- **Suzuki（P0）**：前 5 点清单 alone ≈ 随机 init；**推荐 topk init + target-only EI 续跑**（P0 C1 +75 AUC）。

---

## 2. 决策表

| 场景 | 默认动作 | 不要做 | 证据 |
|---|---|---|---|
| **历史底物数量** | **≥3 启用池化 top-5；推荐 ≥5**；报 source coverage | n=1 冒充多源池化；承诺固定 5 个 ID | P1：n=1 Jaccard≈0.17；n=5 init≈全池；**跨源（borylation/HiTEA）n=3 不充分，≥5 更稳** |
| **清单规则** | **默认 mean（跨源产率均值）**；Suzuki 类（完整网格、排序保持低）可选 rank_median；**稀疏面板（HiTEA 类）禁用 rank_median** | 全面改用 rank_median（init 层 +1.78 但 **AUC@20 pooled +1.5 持平、HiTEA −30.0 不显著**，`results/rankmed_audit_compare/`；2026-08-24 HiTEA 特征修复后复核） | 策略研究第 1 步 init 层 + **AUC 层复核（2026-08-24，HiTEA 2026-08-24 重跑）**：Suzuki AUC@5 +20.3 显著 |
| 胺化、多源历史、条件 OHE | **`topk_warm`，k=5（mean 规则）** + target-only EI（可选） | 默认 `sim_weighted` / `safe_gate` | Step1 + P0 + **胺化 matched-init 审计**（C1 +26 CI 含 0 → EI 可选；C2 +67.7 → cold 下 EI 有效）+ **P4 borylation 强复现**（+107.6 vs cold，CI 排除 0） |
**门控（round-1 后，免费）** | **待验证**：用 round-1 5 点观测算每源-目标一致性，剔除低于中位数的源重新池化（G2；仅 init 层证据：探针有效性 +0.319、init_best 三库正）——**AUC@20 未验证**（单步 EI 协议内无操作空间），验证须在批量协议（湿实验，每轮 5 个）下进行 | 旧 `safe_gate`（绑定 sim_weighted）；事前元特征门（Phase 0 证伪）；把 G2 当当前协议内已验证策略 | 策略研究第 3 步（`results/strategy_probe_gate/`）：init 层信号 + 机制一致；**AUC 层待批量回放** |
| **加速表述口径** | 用 **AUC@k / 命中 top-5% / 相对阈值**描述「更快到达好结果」 | 承诺「更快达到 ≥70% 产率」 | 审计：胺化 topk 命中 top-5% 早 ~1 轮、AUC@5 +93.6；**r70 Δ≈0、20 步内达标率仅 ~0.47** |
| 仅有单源历史 | 仍可用该源 top-k init；**预期弱于多源池化** | 把单源结果说成等同 LOSO | pair≺LOSO（胺化 topk +83 AUC 差） |
| 底物描述符 = Morgan + Tanimoto | **池化 topk 与 `nearest_topk_warm` 并列** | 用 hashed 近邻当化学相似 | M2：Morgan 换源 100%；init max 可超池化 |
| 底物描述符 = hashed | **只用池化 topk** | hashed 近邻当默认 | Step1 nearest ≺ topk |
| **Suzuki** | **池化 topk + target-only EI**（B=20） | 用 cold-EI 当路径；只报 vs cold；声称「只做 5 点就够」 | P0：C2 −21（cold-EI 弱）；C1 +75（topk+EI 有益）；C5 +92 vs random |
| 条件表示 | **OHE** | 条件 Morgan / DFT 默认 | Phase B 否决 |
| 续跑决策 | 分库（init 型 EI 可选、Suzuki 类 EI 必选）；探针后事中确认 | 事前 R² 分档（策略研究第 2 步证伪：R² 是库级量、无信号） | C1 库级差异（Suzuki +75.5 vs +8~26）+ 策略研究第 2 步负结果 |
| **历史进后段 GP（warm 续跑）** | **不把历史产率当 warm 点加入 target GP**——历史价值只经 init 清单注入 | "全程把 topk 条件加入 BO"（warm 参与后段） | **策略研究第 5 步四臂实验（2026-08-24，`results/continuation_arms_compare/`）**：Suzuki 类（EDBO + HiTEA，n=23）：B=top-5 历史行 warm **−59.1 [−139.0, −3.6] 显著负**；C=全部历史 warm（≤120）**−28.5 [−66.2, +4.3] 负趋势**；均不优于 A=纯 EI（warm 广度>精度但都不如无 warm）；与"排序可迁移、数值不可迁移"一致 |

---

## 3. 操作规格

### 3.1 胺化默认路径

1. **门槛**：至少 **3** 个其他底物的历史数据；**推荐 ≥5**。不足则警告并勿承诺池化清单质量。  
2. **历史池**：除目标外全部底物（或满足门槛的子集）；按条件 ID **跨源产率均值**排序（默认规则；**Suzuki 类（完整网格、排序保持低）可选 rank_median——跨源排名中位数**；稀疏面板禁用 rank_median，AUC 层复核见 2026-08-24 注释、2026-08-24 HiTEA 特征修复后复核：HiTEA rank_median −30.0 不显著）。  
3. **选点**：池化排名前 **k=5**；输出每个条件的 **source support**（被多少源支持）。  
4. **预算**：5 点 init + 15 点 target-only EI；主增益在 init（M1 + matched-init 审计 C1/C2）；**EI 续跑可选**（C1 弱正，CI 含 0；topk+随机续跑已赢 cold+EI）。  
5. **报告**：vs cold **和** vs random。  
6. **口径警示**：对外用「更快到达好结果 / 命中高产区 / 前段 AUC」表述（命中 top-5% 早 ~1 轮、AUC@5 +93.6、达标率 100% vs 91%/60%）；**不要**承诺「更快达到 ≥70% 产率」——该绝对阈值下优势几乎消失（r70 Δ≈0，20 步内达标率两策略均仅 ~0.47，一半靶根本达不到）。  
7. **round-1 后门控（待验证，不进当前默认）**：用 round-1 的 5 点观测算每个历史源与目标的一致性，剔除低于中位数的源后重新池化（G2）——**仅 init 层证据（init_best 三库正、探针有效性 +0.319）；AUC@20 未验证**（单步 EI 协议内无操作空间）。验证须在**批量协议**（湿实验 `docs/23`，每轮 5 个）下进行：round-1 后决定 round-2 推荐用 EI 还是 G2 修正清单。

### 3.2 Suzuki（P0 + P1 修订）

1. **门槛**：更严——建议 **≥5** 历史偶联对；清单 ID 稳定性差（n=5 Jaccard≈0.26）。  
2. 同样用 **池化 top-5** + **target-only EI** 续跑（P0 C1）。  
3. 不要用 cold-EI；不要假设 5 点 alone 够（P0 C4）。  
4. 双对照；分库叙述。

---

## 4. Morgan 并列规则（可选增强）

当底物指纹为 `morgan_r2` + Tanimoto 时：

1. 生成清单 A = 池化 top-5。  
2. 生成清单 B = Morgan 最近邻源上的 top-5。  
3. **推荐**：比较 init 段最高产；取更高者开跑。离线推荐时默认仍交 **池化 A**，B 作备选。  
4. 不要用 sim 加权替代上述 init 选择。

---

## 5. 明确不做（本草稿）

- 为「让 GP 更聪明」先堆 contextual / multi-task / 新采集  
- 条件 DFT 或条件 Morgan 默认化  
- pair 全量当主交付  
- 把 Suzuki Q1 失败写成「topk 无效」  
- 在 Suzuki 上把 **cold-EI** 当默认或唯一正对照  
- 宣称旧 `safe_gate`（绑定 sim_weighted）已安全弃权——**门控用 G2 选源池化（round-1 后，免费），不用旧 safe_gate**  
- 事前元特征门控（Phase 0 证伪：元特征无法跨库判别）

~~共享 init 消融~~ → **已完成**（P0，`docs/17_step3_experiment_plan.md` §3.8）。

---

## 6. 对用户怎么说（短）

- **胺化**：有多源历史时，优先做历史上跨底物排名靠前的 5 个条件，再继续优化；前 5 次实验是主价值。  
- **Suzuki**：同样用历史 top-5 开跑，但**请继续用 BO 优化**；不要单独依赖 5 点；冷启动 GP 本身不可靠（P0 已证实）。  
- **相似底物**：Morgan 指纹下，近邻源清单可与池化并列；hashed 近邻不可靠。  
- **说「加速」的口径**：用「更快命中高产区 / 前几轮表现更好」描述（胺化命中 top-5% 平均早 ~1 轮）；**不说**「更快达到 70% 产率」（审计显示该绝对阈值下无优势）。  
- **round-1 之后**：如果发现某些历史底物和你差别很大，可以只保留与你一致的底物重新推荐 5 个条件——不额外花实验（探针门，免费）。

---

## 7. 锁定关系

| 文档 | 角色 |
|---|---|
| `FROZEN_CLAIMS.md` | 效应数字锁 |
| `docs/15_step1_step2_lock.md` | Step1+Step2 锁 + **P0 附录** |
| `docs/17_step3_experiment_plan.md` | P0 预注册与结果 |
| `results/suzuki_p0_shared_init/` | P0 分析产物 |
| **本文件** | 策略默认草稿 |

改默认动作须改本文件日期并写明理由；不得回写冻结数字。
