# docs 目录索引（2026-08-23 整理）

**约定：** 锁定文档（标 🔒）只读，改数字须按各自文件的纪律流程；草稿（标 📝）可修订；参考（标 📄）。
主入口：`docs/19_work_snapshot.md`（成稿快照）→ `docs/21_paper_framework.md`（论文框架）。

## A. 研究框架与数据语义（参考）

| 文件 | 内容 | 状态 |
|---|---|---|
| [00_research_framework.md](00_research_framework.md) | 三步研究框架（效应→机制→策略）+ 当前指针 | 📄 参考 |
| [00_research_questions.md](00_research_questions.md) | 问题定义与假设 H1–H4 | 📄 参考 |
| [01_data_schema.md](01_data_schema.md) | 数据字段与 metadata | 📄 参考 |
| [02_methods_matrix.md](02_methods_matrix.md) | 方法矩阵与实现映射 | 📄 参考 |
| [03_evaluation.md](03_evaluation.md) | 指标与 benchmark 定义 | 📄 参考（seed 建议 ≥20，与实际 5 不一致，见 19 §7） |
| [04_roadmap.md](04_roadmap.md) | 早期路线图 | 📄 历史 |
| [05_data_roles.md](05_data_roles.md) | 主集语义：substrate vs 逻辑板 | 🔒 冻结 |

## B. 实验方案（参考/历史）

| 文件 | 内容 | 状态 |
|---|---|---|
| [06_experiment_amination_v1.md](06_experiment_amination_v1.md) | 胺化 v1 全量协议 | 📄 历史（已被 10/17 取代） |
| [07_experiment_suzuki_v1.md](07_experiment_suzuki_v1.md) | Suzuki v1 全量协议 | 📄 历史 |
| [08_experiment_pair_v1.md](08_experiment_pair_v1.md) | pair 轨（可选轨，非主线） | 📄 历史 |

## C. Step1–2 锁定与收口（主证据层）

| 文件 | 内容 | 状态 |
|---|---|---|
| [09_next_steps_post_frozen.md](09_next_steps_post_frozen.md) | 冻结后短执行单 | 📄 历史 |
| [10_step1_transfer_effects.md](10_step1_transfer_effects.md) | Step1 设计规范与统计口径 | 🔒 锁 |
| [11_step1b_representation.md](11_step1b_representation.md) | 表示轴收口（Morgan/DFT 结论） | 🔒 锁 |
| [12_plan_after_step1.md](12_plan_after_step1.md) | 收口后规划 | 📄 历史 |
| [13_step1_closeout.md](13_step1_closeout.md) | Step1 收口清单 | 🔒 锁 |
| [15_step1_step2_lock.md](15_step1_step2_lock.md) | **Step1+Step2+ P0/P1 附录合并锁** | 🔒 锁 |

## D. 策略与当前工作（活文档）

| 文件 | 内容 | 状态 |
|---|---|---|
| [14_strategy_draft.md](14_strategy_draft.md) | 策略草稿（可执行默认，跨源方向已验证） | 📝 草稿 |
| [16_work_report_step1_step2.md](16_work_report_step1_step2.md) | Step1+Step2 详细工作汇报 | 📄 汇报 |
| [17_step3_experiment_plan.md](17_step3_experiment_plan.md) | Step3 预注册实验方案（P0–P5，含胺化 matched-init 审计 §3.9） | 📝 进行中 |
| [18_p4_hitea_holdout.md](18_p4_hitea_holdout.md) | **P4 外部验证（borylation 主库 + HiTEA 第二库）预注册与结果锁定** | 📝 结果已锁 |
| [19_work_snapshot.md](19_work_snapshot.md) | **工作成稿快照（全部结论 + 局限）** | 📝 主入口 |
| [20_gating_research_plan.md](20_gating_research_plan.md) | 门控研究方案（已固定，未执行） | 📝 方案 |
| [21_paper_framework.md](21_paper_framework.md) | **论文框架 + 摘要草稿（中英）** | 📝 草稿 |
| [26_paper_maintext_draft.md](26_paper_maintext_draft.md) | **正文初稿 v1（英文投稿版）** | 📝 初稿 |
| [22_p3_wet_lab_validation.md](22_p3_wet_lab_validation.md) | **P3 湿实验前瞻验证方案（预注册，验证核心）** | 📝 方案 |
| [24_strategy_research_mechanism_driven.md](24_strategy_research_mechanism_driven.md) | 策略研究（机制驱动，四步完成 + 四臂 warm 实验） | 📝 活文档 |
| [25_chaos_1d_validation.md](25_chaos_1d_validation.md) | **CHAOS 一维独立验证（4 反应 × 720 添加剂）** | 📝 边界验证 |
| [28_experiment_catalog.md](28_experiment_catalog.md) | **实验全览（设计用途+结果+可视化图索引）** | 📝 全览 |

## E. 交付物（非 md）

- 论文摘要与大纲（docx）：`docs/TransferBO2.0_abstract_outline.docx`（由 `scripts/build_paper_docx.py` 生成）

## 推荐阅读顺序（新成员）

1. `docs/19_work_snapshot.md`（全貌）→ 2. `docs/15_step1_step2_lock.md`（主证据锁）→
3. `docs/18_p4_hitea_holdout.md`（外部验证）→ 4. `docs/21_paper_framework.md`（论文）→
5. `docs/20_gating_research_plan.md`（后续方向）
