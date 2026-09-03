# 论文框架（v2 成文主干版，2026-08-24）

> **成文逻辑（用户定）**：目标是找到一个正增益的应用策略——先定指标，再拿最有信服力的证据说话；
> 研究过程的曲折（Phase 0 负结果、统计边界、机制验证细节）不进主线，存备忘录（docs/19/24、results/*）。
> **主干一句话：1.0 用单源 pair 切入，效应为负；2.0 改用多源池化切入，找到正增益策略（池化 top-5 清单），
> 它有效的化学原因是"条件排序由模板通用化学决定、跨底物保持，产率水平由底物化学决定、不可迁移"。**

---

## 0. 主干（论文就讲这一个故事）

**目标**：历史 HTE 数据能否提升新底物 BO？（找一个正增益的应用方式）

**切入点的教训**：单源 pair 迁移（1.0）在 Suzuki 上效应为负——因为单源把"一个底物的特异噪声"当成了知识；换成**多源池化**（2.0），把多个底物排序投票，特异噪声平均掉，留下的通用排序——效应转正。

**发现**：在四库（71 任务、三个反应类、含跨反应类独立源）上，**池化 top-5 条件清单作第 1 轮**是唯一稳健的正增益形态；进 GP、门控无效。

**化学解释**：同一反应模板下，决定条件**好坏排序**的是配体/碱/催化剂的**本征化学性质**（对模板所有底物通用），决定产率**水平**的是**底物自身的反应活性**（底物特异）——所以排序可迁移、数值不可迁移，清单（只带排序）有效、GP（学数值）无效。

---

## 0b. 写作筛选原则（哪些实验进正文，哪些进 SI/备忘录）

> **叙事顺序遵循正常研究逻辑**（问题 → 方法 → 实验 → 结果 → 分析 → 结论），不做"结论前置"的重构；
> 本节只规定**筛选**：正文只写与研究问题直接相关的实验和结果，无关紧要的进 SI 或备忘录。
> 研究过程中走过的弯路全部留在备忘录（docs/19/24、results/*），正文不描述过程曲折。

| 层级 | 内容 | 理由 |
|---|---|---|
| **正文（主证据）** | 策略比较主表（正结果 + 两个关键负结果）、matched-init 审计、四库外部验证、排序保持分析、化学解释 | 直接支撑"找到一个正增益策略 + 为什么有效" |
| **SI（辅助查证）** | 轮次指标全套、源数门槛曲线、聚合规则消融、表示轴（Step1b）细节、统计边界 | 审稿人可查，不占正文 |
| **备忘录（不进论文）** | Phase 0 元特征判别、批次单样本提示、早期 pilot、策略研究曲折 | 研究过程记录，属内部资产 |

## 1. Title

> **"Throw most of it away: historical HTE data accelerates Bayesian optimization for new substrates through a five-condition list, not a transfer model"**

## 2. Abstract（主干版，只讲一个故事）

**EN:**

Historical HTE data should help Bayesian optimization (BO) for new substrates, but how it enters the loop matters: single-source transfer gave negative effects in our earlier pair-based setup, while **pooling the history across substrates turns it positive**. Across four HTE libraries spanning three reaction classes (71 substrate-defined tasks; 2,130 leave-one-substrate-out runs; one frozen protocol with dual controls), the only robustly positive strategy is a **pooled top-five condition list used as round-one initialization** (+160 and +108 AUC vs. cold start on the two full-grid libraries; 88–94% of targets improved); injecting historical labels into the surrogate never produced a robust positive-gain strategy — null or negative in every library, and significantly negative when historical warm points ran through the entire continuation in the Suzuki class. The chemistry behind this is simple: within one reaction template, the *ranking* of conditions is set by ligand/base properties that act on every substrate alike, while the *level* of yields is set by each substrate's own reactivity—so the ranking transfers across substrates and the magnitudes do not. A list carries the ranking; a GP learns magnitudes. Deployment rules follow: pool ≥3 history substrates (≥5 recommended), report per-condition source coverage, and choose the continuation (EI) by library type. We conclude with an honest scope: the five-condition list is the positive-gain strategy in the libraries we tested; its boundary is set by substrate diversity and template generality.

**ZH（供内部）:**

历史 HTE 数据理应能帮新底物的 BO，但**以什么方式进入回路是关键**：我们早先的单源 pair 切入效应为负，改用**跨底物多源池化**后效应转正。在四个 HTE 库、三个反应类（71 个底物任务、2,130 个 LOSO run、一套冻结协议与双对照）上，唯一稳健的正增益策略是**多源池化 top-5 条件清单作第 1 轮**（两个完整网格库 +160/+108 AUC vs cold，88–94% 靶提升）；把历史标签注入代理模型在所有库上都未成为稳健正增益策略——null 或负，且 Suzuki 类把历史 warm 点跑满整个续跑时显著为负。背后的化学很简单：同一反应模板内，条件的**好坏排序**由配体/碱对模板所有底物都成立的本征性质决定，产率的**水平**由每个底物自身的反应活性决定——所以**排序跨底物可迁移，数值不可迁移**；清单携带排序，GP 学的是数值。部署规则：≥3 个历史底物池化（推荐 ≥5）、逐条件上报 source coverage、续跑（EI）按库类型选择。结论范围如实收窄：五条件清单是我们在测试库中找到的正增益策略，其边界由底物多样性与模板通用性决定。

## 3. 正文结构（只保留主干，细节进 SI）

### 1. Introduction（两段式）
- 问题与目标：找一个正增益的历史数据应用方式（不是检验冷启动 BO 本身）；
- 切入点的教训：单源 pair（负）→ 多源池化（正）——为什么"怎么用历史"比"用不用历史"更重要。

### 2. Results（四个节，主证据各一个表）
- **2.1 什么有效**：池化 top-5 清单——主证据两个数字：胺化 +160.2、borylation +107.6（CI 排除 0，88–94% 靶为正）；更快而非更高（init_best 优势大、final_best ≈ 0）。
- **2.2 什么无效**：历史标签进 GP（sim_weighted/contextual 四库无正增益策略——胺化/borylation null、Suzuki 类加权进 GP 相对 cold 曾显著正但相对 random 弱、**2026-08-24 四臂实验：Suzuki 类 warm 续跑显著负**）；门控（无可用门）。负结果与正结果同框，说明"扔掉大部分历史"不是直觉退化而是证据结论。
- **2.3 为什么有效（化学性）**：排序保持的化学根源——
  1. 模板通用性：配体（位阻/供电子性）与碱（碱性/溶解性）决定条件好坏，对模板内所有底物成立；
  2. 底物特异性：芳基卤的电子效应/位阻决定产率水平（活化能整体移动），不翻转条件排序——除非极端位阻底物×极端位阻配体冲突（这就是"部分保持"的化学来源，也因此只取顶部排序而非全部）；
  3. 池化的化学意义：对多个底物排序投票 = 平均掉单一底物的特异噪声，留下的就是模板通用的配体/碱主效应——这是"分离通用性质与底物特异性质"的朴素但正确的实现；
  4. 数值不可迁移：产率绝对值含底物活性因子，跨底物/跨批次不可比——所以只用排序、不用数值。
- **2.4 怎么用（应用规则）**：k=5 清单 + ≥3/≥5 源门槛 + coverage 上报 + 分库续跑（init 型库 EI 可选、Suzuki 类 EI 必选）；表述口径（相对指标，不承诺绝对产率）。

### 3. Methods（正常研究逻辑，一页纸）
- 3.1 数据与协议：四库与来源；LOSO、k=5、OHE、GP-EI、n_init=5/B=20、seeds 0–4、双对照（vs cold 与 vs random）、靶级 bootstrap；
- 3.2 策略集与对照：清单类（池化 top-5 / 单源 top-5）、模型类（sim_weighted 等）、基线（random/cold）；matched-init 审计（C1–C4，分离起点效应与过程效应）；
- 3.3 分析：排序保持（跨底物条件排序 Spearman）、轮次指标、源数门槛；
- 3.4 复现声明（2,130 jobs、脚本、数据可用性）。

### 4. Discussion（三个问题，各一段）
- 为什么进 GP 无用（化学：GP 学数值，数值含底物特异水平，不可迁移）；
- 为什么门控学不会（排序保持度可事后测但元特征猜不中——门的方向是探针直接测量，未来工作）；
- 边界与局限（四库范围、回顾性、无湿实验前瞻、seed=5——如实收窄，符合事实即可）。

### 5. Conclusion
五条件清单是正增益策略；化学根基 = 排序可迁移/数值不可迁移；范围 = 测试库与模板通用性之内。

### SI（备忘录区：不占正文，供审稿人查证）
- S1 四库与协议细节、S2 matched-init 全表、S3 轮次指标、S4 源数门槛曲线、
- S5 聚合规则消融、S6 排序保持与双通道机制验证（`results/rank_preservation/`）、
- S7 策略研究 Phase 0（元特征不可跨库判别——备忘录）、S8 批次单样本提示、S9 种子敏感性（待做）、
- S10 CHAOS 一维边界验证（docs/25：清单机制不依赖多维条件结构；排序保持 0.694 为五库最高）。

## 4. 叙事红线（成文版，简化）

1. 主线永远讲"找策略"：目标 → 切入点（pair 负/池化正）→ 发现 → 化学解释 → 应用；
2. 主证据只挑最有信服力的（胺化 +160、borylation +108 两个数字开路），其余进 SI；
3. 化学解释必须落地到"配体/碱通用性质 vs 底物特异活性"，不堆机制验证细节；
4. 负结果只说两层（进 GP 无效、门控不可行），不展开曲折过程；
5. 结论范围可以收窄，但必须符合事实（四库、回顾性、边界如实）。

## 5. 待办

- [x] 主干与化学解释成文框架（本文件 v2）
- [x] 正文初稿（`docs/26_paper_maintext_draft.md`，2026-08-24，英文投稿版 **v2**——按"证据冻结+叙事校正"意见书重写：主题式结构、pair 因果链修正、2,130 口径定义、跨板表述降级、Table 3 无效策略表、双通道象限框架、Claims register 冻结）
- [ ] 正文初稿审阅与数字复核（用户）
- [ ] P3 湿实验（前瞻验证；未做则在 Discussion 如实写明）
- [ ] SI 表格整理（S1–S11）
