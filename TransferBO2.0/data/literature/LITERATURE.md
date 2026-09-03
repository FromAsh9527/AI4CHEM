# 文献集导读（TransferBO 2.0）

本目录服务于课题：**跨底物 + 跨板的反应条件贝叶斯优化迁移**。
机器可读书目见 [`bibliography.bib`](bibliography.bib)；单篇笔记放在 [`reading_notes/`](reading_notes/)。

---

## A. 反应优化与 BO（必读）

| 文献 | 与本课题关系 | 优先级 |
|---|---|---|
| Shields et al., *Nature* 2021 | 反应条件 BO 里程碑；cold-start 对照范式 | ★★★ |
| Häse et al., Phoenics / Gryffin | 混合离散—连续化学变量优化 | ★★★ |
| Reker et al., 2020 | 极少实验信息下的自适应优化 | ★★ |
| Zahrt et al., *Science* 2019 | 选择性/催化剂机器学习工作流 | ★★ |

## B. 多任务 / 迁移 / Contextual BO（方法核心）

| 文献 | 与本课题关系 | 优先级 |
|---|---|---|
| Swersky, Snoek, Adams, 2013 | Multi-task BO 经典 | ★★★ |
| Bonilla et al., 2008 | Multi-task / ICM GP | ★★★ |
| Krause & Ong, 2011 | Contextual GP bandit | ★★★ |
| Feurer et al., 2015；Wistuba et al., 2018 | Warm-start / transfer surrogate | ★★ |
| Kandasamy 多保真 / 高维 BO 系列 | 上下文与保真度建模参考 | ★★ |

## C. 化学表示与反应数据

| 文献 / 资源 | 与本课题关系 | 优先级 |
|---|---|---|
| Schwaller et al., RXNFP, *Nat Mach Intell* 2021 | 反应指纹与相似性 | ★★★ |
| Ahneman et al., *Science* 2018 (Buchwald–Hartwig HTE) | C–N 偶联产率预测经典集 | ★★★ |
| Perera et al. / 其他 Suzuki HTE | 底物—条件交互 | ★★ |
| Open Reaction Database (ORD) | 跨来源 domain shift 挖掘 | ★★ |
| CHAOS / Prieto Kullmer *Science*（多板添加剂） | 真实多板 HTE；TransferBO 已用 | ★★★ |

## D. Batch effect / 稳健迁移（特色文献）

| 方向 | 用途 | 注意 |
|---|---|---|
| ComBat / Harmony / MNN（生信） | 板均值偏移思想参考 | **不可直接照搬**：化学中常有 plate×condition 交互 |
| Mixed-effects GP / run-to-run variation（过程控制） | \(b_p\)、\(v_{p,x}\) 建模 | 与本课题 plate-aware 核最贴近 |
| Domain adaptation / negative transfer 综述 | 安全门控动机 | 结合化学先验写进 gating |

## E. 推荐公开数据资源（接入清单）

| 资源 | 适合做什么 | Plate metadata |
|---|---|---|
| Buchwald–Hartwig amination HTE | 底物迁移、产率预测、BO replay | 通常弱；需自构板设定 |
| Suzuki–Miyaura HTE | 同上 | 通常弱 |
| CHAOS 四板添加剂 | 跨板迁移（底物维度弱） | **强** |
| ORD | 跨论文 domain shift | 参差不齐 |
| USPTO 衍生集 | 反应预测 | **不适合严格 BO**（缺失败与完整空间） |

理想数据检查表见 `docs/01_data_schema.md`。

## F. 阅读顺序建议（两周）

**Week 1**

1. Shields 2021（问题与指标感觉）
2. Swersky 2013 + Bonilla 2008（MTGP/ICM）
3. Krause & Ong 2011（contextual）
4. Ahneman 2018 数据与设定

**Week 2**

5. Schwaller RXNFP
6. Gryffin/Phoenics（离散条件）
7. ComBat + 一篇 mixed-effects GP
8. 写一篇笔记：`reading_notes/synthesis_negative_transfer.md`（负迁移来源清单）

## G. 笔记模板

复制 `reading_notes/_TEMPLATE.md`，每篇文献回答：

1. 问题与假设  
2. 数据是否含 plate / substrate 结构  
3. 可迁移到本课题的模块（表示 / 核 / 校正 / 指标）  
4. 对本课题的局限  
5. 可引用的一句话结论  
