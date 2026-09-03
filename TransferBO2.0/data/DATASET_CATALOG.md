# 公开 HTE / 反应优化数据集完整清单

> 供选型研究用。更新：2026-08-20。  
> **不预设最终主集**；标注本地是否已有、反应类型、规模、meta、适合回答的问题。

---

## 0. 关于“几个底物就几个板”——先对齐概念

你的理解在实验室叙事里很常见：

> 一块板跑一个（或一对）底物的条件筛选 → **底物数 ≈ 板数**。

很多公开表也正是这样整理的（如本地 `edbo_*_plates.csv` 里 `plate_id = suz_t1…` 实际就是**一个底物任务一块逻辑板**）。

这对课题有两种完全不同的含义：

| 设定 | 数据长什么样 | 能检验什么 | 检验不了什么 |
|---|---|---|---|
| **A. 一底物一板（自然整理）** | 每个 `substrate_id` 只出现在一个 `plate_id` | 跨底物迁移（substrate transfer） | **拆不开**板效应与底物效应（二者完全共线） |
| **B. 同底物跨多板 / 跨日期** | 同一底物（或共享条件）在多个 `plate_id`/`date` 上有重复 | 板/批次校正、anchor、负迁移中的板风险 | 需要真实跨板重复，或**人为**把同一底物的条件分到多板并注入板偏差 |
| **C. 真·多板同库（如 CHAOS）** | 同一套添加剂/条件在 4 块板上，反应骨架不同 | 跨板迁移 | 不是“新底物条件优化”同构问题 |

研究方案里的难点是：

\[
y = f(s,x) + b_{\mathrm{plate}} + \epsilon
\]

若永远是「一底物一板」，则 \(s\) 与 \(plate\) 一一对应，模型无法分辨“差在底物”还是“差在板”。  
因此：

- 若你的第一阶段只想先做 **跨底物 BO 迁移** → 用设定 **A** 完全够，把 `plate_id` 当 task id 即可。  
- 若还要做 **plate-aware / 安全迁移** → 必须有设定 **B**（真实跨板/跨日，或对稠密网格做**同底物多板**仿真），不能只靠“有几个底物就几个板”。

下面清单按反应类型列出；“板 meta”列会标明是 **真板/日期/screen** 还是 **仅任务 ID**。

---

## 1. 本地已有（`../TransferBO/data`）——优先可立刻用

| ID | 名称 | 反应 | 规模（约） | 底物/任务 | 条件密度 | 板/批次 meta | 本地路径 | 备注 |
|---|---|---|---|---|---|---|---|---|
| L1 | CHAOS 四板添加剂 | Ni 光氧化还原脱羧芳基化 + 添加剂 | 2880 | 4 反应×720 添加剂 | 720/板 | **真 `plate_id`×4** | `processed/additives_four_plates.csv` | 跨板强；底物对叙事弱 |
| L2 | EDBO Suzuki 任务表 | Suzuki–Miyaura | 3696 | **12 底物对** | **308/对** | `plate_id`=任务（一底物一板） | `processed/edbo_suzuki_plates.csv` | 稠密，适合跨底物 BO |
| L3 | EDBO 胺化任务表 | C–N / 胺化类 | 3900 | **15 底物** | **260/底物** | 同上 | `processed/edbo_amination_plates.csv` | 稠密 |
| L4 | Doyle CN 板表 | Buchwald–Hartwig + isoxazole 添加剂 | 3600 | **15 底物** | **240/底物** | 同上；配体4×碱3×添加剂20 | `processed/doyle_cn_plates.csv` | Ahneman *Science* 2018 衍生 |
| L5 | cn-processed | 同上精简 | 3600 | 15 | 240 | 无独立真板 | `raw/external/cn-processed.csv` | 与 L4 同源 |
| L6 | SURF Suzuki all | Suzuki–Miyaura（Roche） | 3426 | **7 对** | 中位~480 | **`rxn_date`×9**；可跨日共享条件 | `raw/surf/sm_all.csv` | [Zenodo 18185850](https://doi.org/10.5281/zenodo.18185850) |
| L7 | SURF BH all | Buchwald–Hartwig（Roche） | 10138 | **32 对** | 中位~192 | **`rxn_date`×41**；6 对有跨日 anchor-like | `raw/surf/bh_all.csv` | 最接近真实批次 shift |
| L8 | SURF SM/BH positive | 同上，仅 product>5% | 1878 / 3441 | 子集 | — | 同日期字段 | `raw/surf/*_positive.csv` | BO 建议用 all（含失败） |
| L9 | aryl-scope-ligand | 芳基–配体范围 | 1536 | 8×8 对 | **24 配体/对** | 无 | `raw/external/aryl-scope-ligand.csv` | 条件维偏窄 |
| L10 | merck-cn | Merck C–N 相关 | 1536 | 6×11 | 催化剂/碱 | 无 | `raw/external/merck-cn.csv` | 需核对与 Ahneman 关系 |
| L11 | amidation | 酰胺化 | 960 | 10 nucleophile | 碱/溶剂/活化剂 | 无 | `raw/external/amidation.csv` | |
| L12 | BH curated 统一集 | BH 多来源 | ~27k 量级 | 强 | 中–强 | **`Source` 跨来源** | `raw/external/BH_HTE_Curated_*.csv` | **本地文件疑似损坏**，需重下 |

描述符缓存（非原始实验）：`descriptors/edbo_*`、`chaos_*` 等。

---

## 2. 公开可下载（本地未必完整）

| ID | 名称 | 反应 | 规模 | 底物结构 | 条件密度 | 板/批次/时间 | 获取链接 | 适合 |
|---|---|---|---|---|---|---|---|---|
| P1 | Ahneman–Doyle BH HTE | Pd C–N + 添加剂 | ~3955 | 多芳基卤 + 胺；15 底物常用划分 | 高（配体×碱×添加剂） | 1536-well 实验，公开表少见 well | [doylelab/rxnpredict](https://github.com/doylelab/rxnpredict)；[rxn_yields](https://rxn4chemistry.github.io/rxn_yields/data/) | 跨底物经典 |
| P2 | Perera Pfizer Suzuki | Suzuki | **5760** | ~15 couplings（喹啉–吲唑变离去基团） | **12 配体×8 碱×4 溶剂** | 流动纳米级；公开表通常无板号 | 原文 SI；Gauche/`rxn_yields` 等转存 | 稠密跨底物 |
| P3 | Sandfort 结构反应性平台转存 | BH / 其它 | 随仓库 | — | — | — | Chem 2020；rxn_yields 引用 | 辅助 |
| P4 | Roche SURF SM/BH | SM / BH | 见 L6–L8 | 多起始原料对 | 较高但不一定全因子 | **日期** | [Zenodo 18185850](https://doi.org/10.5281/zenodo.18185850) | 批次+底物 |
| P5 | Pfizer HiTEA 全量 | 多反应类 | **~39k–47k** | 极广、不均衡 | 不齐 | `SCREEN_ID`/`NOTEBOOK`；部分 `*_with_time`+`Year` | [emmaking-smith/HiTEA](https://github.com/emmaking-smith/HiTEA) | 工业分布/时间漂移 |
| P5b | HiTEA Buchwald_with_time | BH | 3083 | 37 对 | **中位~15（稀）** | SCREEN×39，Year×8 | HiTEA `cleaned_datasets/` | 稀，不利单底物 BO |
| P5c | HiTEA 其它清洗集 | 氢化等 | 见仓库 | — | — | with_time 变体 | 同上 | 反应类型扩展 |
| P6 | JnJ BH 新 HTE + curated | BH | **~11.3k + 16k ≈ 27.5k** | 强 | 中–强；文中 384-well | **`Source`**；孔位未必在 CSV | [bh-hte-ood](https://github.com/schwallergroup/bh-hte-ood)；Zenodo pickle | 跨来源 OOD |
| P7 | CHAOS / Prieto Kullmer | 添加剂筛选 | 4×720 | 4 反应 | 720 | **真四板** | Science [abn1885](https://doi.org/10.1126/science.abn1885)；[chaos](https://github.com/schwallergroup/chaos) | 跨板方法 |
| P8 | Angello heteroaryl SMC | Suzuki 通用条件 | 闭环多轮；~11 底物对×条件矩阵 | 多杂芳基对 | 中等 | 机器人；公开偏 Zenodo 代码/图 | [Science adc8743](https://doi.org/10.1126/science.adc8743)；Zenodo 7099435 / 7106075 / 6517012 | 跨底物“通用条件” |
| P9 | Shields EDBO Nature 基准 | 直接芳基化等 1–5 | 论文基准集 | 少底物深度优化 | BO 轨迹向 | 通常单战役 | [b-shields/edbo](https://github.com/b-shields/edbo) | cold-start BO 对照，非迁移主集 |
| P10 | EDBO+ 多目标 | 多种 | 教程/案例 | — | — | — | [edboplus](https://github.com/doyle-lab-ucla/edboplus) | 工具+少量数据 |
| P11 | Doyle XEC–Novartis | Ni/光氧化还原交叉亲电偶联 | <400 起建模型，可扩展 | 大虚拟底物空间 | active learning **稀疏** | 实验 batch 轮次 | [XEC-novartis](https://github.com/doyle-lab-ucla/XEC-novartis) | 底物空间探索，非稠密 BO 网格 |
| P12 | ORD Pfizer HiTEA 镜像 | 同 P5 | ~39k | 同 | 同 | ORD provenance | ORD `ord_dataset-d92976309c3a48a3a64a4cf5e7048086` | 标准格式 |
| P13 | ORD Chan-Lam sulfonamide HTE | Chan-Lam | 三重复筛：44 磺酰胺×2 硼酸×4 Cu×21 碱×4 溶剂 | 多 | 较完整筛 | 见 ORD 描述 | [ORD 条目](https://open-reaction-database.org/dataset/ord_dataset-5c9a10329a8a48968d18879a48bb8ab2) | 另一反应模板 |
| P14 | ORD 全体 / HuggingFace | 多反应 | 很大 | 杂 | 极不齐 | provenance 参差 | [ord-data](https://github.com/open-reaction-database/ord-data) | 需挖掘，成本高 |
| P15 | ORDerly 条件/产率基准 | 多（偏 USPTO/ORD 清洗） | 大 | — | — | 弱 | [ORDerly](https://github.com/sustainable-processes/ORDerly) | 条件预测，非 HTE 板 |
| P16 | Olympus / Opti Suzuki | Suzuki | 247 等 | 少 | 连续变量优化基准 | 无 | [basf mopti](https://basf.github.io/mopti/datasets/suzuki/) | 算法基准，非多底物 HTE |
| P17 | Denmark Lucid Somnambulist BH | BH | 见仓库 | — | — | — | [SEDenmarkLab](https://github.com/SEDenmarkLab/Lucid_Somnambulist) | 额外 BH |
| P18 | phactor 示例 HTE | 反应发现数组 | 示例级 | — | 24/96 well 工作流 | well 友好 | [cernaklab/public-phactor-example-files](https://github.com/cernaklab/public-phactor-example-files) | 格式参考，非大库 |

---

## 3. 按“你能立刻开干的问题”分组

### 只做跨底物迁移（一底物一板即可）

- **首选稠密**：L2 EDBO Suzuki、L3/L4 Doyle/EDBO 胺化、P2 Perera 5760  
- **备选**：P1 Ahneman 原表、P8 Angello（需确认长表）

### 要做真实批次/板效应（不要和底物完全绑死）

- **首选**：L7 SURF BH、L6 SURF SM（`rxn_date`）  
- **其次**：P5/P5b HiTEA（`SCREEN_ID`/`Year`，但 BH 偏稀）  
- **跨来源粗粒度**：P6 / L12（`Source`）  
- **真四板**：L1 CHAOS（问题定义略偏添加剂）

### 若坚持“同底物多板”才能拆效应

公开完美集极少 → 只能：  
1) SURF/HiTEA 里挑**跨日/跨 screen 重复条件**；或  
2) 对 L2/L3/L4/P2 等稠密网格做**同底物条件的人为分板+注噪**（这与“几个底物几块板”不是同一件事）。

---

## 4. 明确不推荐作本课题主 BO 基准

| 数据 | 原因 |
|---|---|
| USPTO / 多数 ORDerly 产率集 | 缺失败实验与完整条件空间 |
| HiTEA 单对中位~15 | 撑不起 20–50 步 BO 曲线 |
| aryl-scope 仅 24 配体 | 条件维过窄 |
| Olympus Suzuki 247 | 单体系连续优化玩具集 |

---

## 5. 建议你怎么读这个表

1. 先定叙事：只要 **substrate transfer**，还是必须 **substrate + plate** 可识别？  
2. 若只要前者：在 L2 / L3 / L4 / P2 里选 1–2 个稠密集。  
3. 若必须后者：主看 L6/L7，CHAOS 作板方法预验证；稠密集仅在需要仿真同底物多板时再用。  
4. 选定后我再帮你：入库适配器、审计脚本、LOSO 配置。

相关短文：`DATASETS.md`（评分与策略）；审计脚本在 `scripts/_audit_*.py`、`_score_datasets.py`、`_surf_batch_overlap.py`。
