# Step1 收尾之后：规划（2026-08-21）

产品目标：**一套对历史 BO 数据的利用策略**（默认动作 + 适用边界），不是「冷启动 GP 是否强于随机」。

三步框架不变：效应 → 机制 → 策略。本文件是 Step1 **收口后**的执行规划。

| 步 | 文档 | 状态 |
|---|---|---|
| 效应（Step1） | `docs/10_*` + `FROZEN_CLAIMS.md` | **锁死** |
| 表示稳健性（Step1b） | `docs/11_*` | **锁死**（收口） |
| 机制（Step2） | M1/M2 + `docs/15_*` | **锁死**（校验 PASS） |
| 策略交付（Step3） | `docs/14_strategy_draft.md` | **草稿**（可改细则，不回写锁） |

执行清单（短）：`docs/09_next_steps_post_frozen.md`  
**合并锁档：** `docs/15_step1_step2_lock.md` · 校验：`results/step1_step2_validation/report.md`

---

## 0. 收尾后锁定的读法（不重开实验）

1. **胺化**：多源 **topk init（k=5）** 是主正效应；GP 加权 / 现有 gate 不是。  
2. **Suzuki**：Q1（cold vs random）失败 = **冷启动 BO 质量备注**，不是历史策略否决。topk vs cold 为正（+150），vs random 弱正（CI 贴 0）→ **策略可行、稳健性弱于胺化**。禁止把胺化整包叙事平移。  
3. **表示**：条件默认 **OHE**；底物近邻相关工作用 **Morgan+Tanimoto**。条件 Morgan / DFT **不升默认、不升全量**。  
4. **Q3 条件化**：hashed 下 topk ≻ nearest；Morgan 下 nearest ≳ topk。Step1 主张 3 只锁 hashed 协议。

停止：再换指纹、DFT 全量、pair 全量当主表、用 job-IID 改结论、把 Step1 写成策略完成。

---

## P0 — Step1 收尾（**完成**，核对 2026-08-22）

无新实验。对齐主张与文档，使「产品成功标准 ≠ Q1」成为仓库默认读法。

核对戳：`docs/13_step1_closeout.md`

- [x] `FROZEN_CLAIMS.md` 附录（日期、理由；数字不改）
- [x] `docs/10` 交界表：Q1 失败不再写成「默认弃权/冷启动」
- [x] `docs/11` 表示轴收口；Suzuki 不再用 Q1 否决 topk
- [x] `results/ALL_RESULTS_ANALYSIS.md` + 生成脚本叙事对齐
- [x] 本规划 + `docs/09` 执行单
- [x] 结果摘要 / Canvas 去掉「用 Q1 否决 topk」的旧句
- [x] 收口清单 `docs/13_step1_closeout.md`

---

## P1 — Step2 机制（下一周期，优先胺化）

不问新算法。用**已有 JSON / 试点**回答两个问题。

### M1 — 增益在 init 还是在后续 BO？（**完成**）

产出：`results/step2_m1/`。胺化 vs cold：**init 通道**；Suzuki vs cold 同；vs random 则后 15 步 BO 贡献更大。  
→ 胺化交付优先是 **topk 清单**，不先堆 GP。

### M2 — 池化为什优于单源？Morgan 下近邻为何翻盘？（**完成**）

产出：`results/step2_m2/`。  
池化 top5 在靶上优于典型单源（胺化 93% 靶）；pair topk < 同靶 LOSO topk。  
Morgan 近邻 **100% 换源**；翻盘看 **init max** 而非全局 Spearman。

**先不要** pair 全量。

### 可选小消融（不重开 Q1）→ **升格为 Step3 P0**

已写入预注册方案：`docs/17_step3_experiment_plan.md` §3。  
共享 init：6 臂（含 `cold_random_post`、`topk_random_post`、`topk_only`）；胺化 2 靶 sanity → Suzuki 360 jobs。

---

## P2 — Step3 策略草稿（**完成**，2026-08-22）

全文：`docs/14_strategy_draft.md`

| 场景 | 默认动作 |
|---|---|
| 胺化、多源、条件 OHE | **topk k=5**；不要默认 sim 加权 |
| 底物 Morgan | topk 与 nearest **并列**（比 init max / 池化优先+近邻备选） |
| hashed 近邻 | 不作默认 |
| Suzuki | 仍可用 topk；不承诺胺化同级；双对照报告 |
| 门控 | 暂无可用门 |

---

## P3 — Step3 验证实验（**当前**，2026-08-22 起）

权威方案：`docs/17_step3_experiment_plan.md`

| 优先级 | 内容 | 状态 |
|---|---|---|
| **P0** | Suzuki shared-init / EI-vs-random 审计 | **完成**（420 jobs，2026-08-22） |
| **P1+P2 离线** | 源规模 + 清单稳定性 | **完成**（2026-08-22） |
| P1 BO（可选） | subset LOSO | 脚本就绪 |
| P3/P4 | 湿实验 / 外部 holdout | 方案 |
| P5 | `recommend_init` CLI | 方案 |

**不做：** pair 全量、板校正主实验、contextual GP、sim_weighted 调参、MTGP 主线。
