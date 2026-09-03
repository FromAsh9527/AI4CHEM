# 实验协议 v1：胺化主集 LOSO（OHE + hashed SMILES）

冻结日期：2026-08-20  
实验 ID：`amination_v1`

## 1. 科学问题（本轮只答这些）

在 **Doyle/EDBO 芳基胺化**（15 底物 × 260 条件）上：

1. 冷启动 GP-BO 是否优于随机？  
2. 历史 Top-k / 最近邻 Top-k warm-start 是否改善前期效率？  
3. 相似度加权迁移、`safe_gate` 相对 cold 的 AUC / 负迁移率如何？  
4. `sub_s4`（旧工作正迁移对照）在本协议下是否仍可见正迁移迹象？

**本轮不答**：真实板效应、Morgan/DFT 表示、Suzuki 跨化学对照（另轨）。

## 2. 材料清单（就绪状态）

| 材料 | 路径 | 状态 |
|---|---|---|
| 数据库 | `data/db/transferbo2.db` | 15×260，已接入 |
| 长表 | `data/processed/amination_long.csv` | 3900 行 |
| 条件表示 | OHE(配体×碱×添加剂) | 代码内建 |
| 底物表示 | `hashed_smiles_v1`（32 维） | DB descriptors |
| 优化器 | sklearn GP (Matern-2.5 ARD) + EI | 默认 |
| 试点配置 | `configs/amination_exp_v1_pilot.yaml` | 已写 |
| 全量配置 | `configs/amination_exp_v1_full.yaml` | 已写 |
| 预检 | `python scripts/preflight_amination_v1.py` | 见下 |
| 汇总 | `python scripts/summarize_results.py --summary-csv ...` | 已有 |

语义：`docs/05_data_roles.md`（`plate_id` = 逻辑板，本轮 `use_plate_correction: false`）。

## 3. 方法固定

### 协议：LOSO

对每个目标底物 \(s_t\)：

- 历史 = 其余底物全部实验  
- 目标 = \(s_t\) 的 260 条件真值表（Oracle 回放）  
- 不允许使用目标底物除 init/序贯已选点以外的标签

### 策略（本轮 6 个）

| ID | 作用 |
|---|---|
| `random` | 下界 |
| `cold_start` | 无历史 BO 基线 |
| `topk_warm` | 全局历史高产条件 init |
| `nearest_topk_warm` | 最近邻底物高产条件 init |
| `sim_weighted` | 历史点按底物相似度加权进 GP（`warm_strength=0.5`） |
| `safe_gate` | Spearman 门控后再决定是否加权迁移 |

**排除** `plate_aware`（本库 plate≠物理批次）。

**已知现象（预检）**：`sim_weighted` 在 hashed SMILES 下可能对 `sub_s4` 表现很差（历史淹没目标 → 强负迁移）。这本身是可报告结果，不是停跑理由；试点 Go 条件要求其**不崩溃**，不要求其优于 cold。已修复：warm 子采样与 init 使用**分离 RNG**，保证同 seed 下与 cold 的 init 可比。

### 预算与种子

| | Pilot | Full |
|---|---|---|
| 目标底物 | s4, s1, s7, s10, s15（5 个） | 全部 15 |
| seeds | 0,1,2 | 0–4 |
| n_init | 5 | 5 |
| budget | 20 | 20 |
| 运行量级 | 5×6×3 = **90** BO | 15×6×5 = **450** BO |

### 指标

- AUC（best-so-far 曲线积分）— 主终点  
- final_best  
- hit10_top5pct  
- 相对 cold 的 \(\Delta\)AUC；按策略算 **NTR** \(P(\mathrm{AUC}_{tr}<\mathrm{AUC}_{cold})\)

## 4. 运行命令

```bash
# 0) 预检
python scripts/preflight_amination_v1.py

# 1) 试点（推荐先跑）
python scripts/run_loso.py --config configs/amination_exp_v1_pilot.yaml

# 2) 汇总
python scripts/summarize_results.py --summary-csv results/amination_v1_pilot/loso_summary.csv

# 3) 试点正常后再全量（本机小规模 / 调试）
python scripts/run_loso.py --config configs/amination_exp_v1_full.yaml --skip-existing --workers 8

# 3b) 超算全量（推荐）：见 scripts/hpc/README_AMINATION_V1_FULL_HPC.md
#     快捷条：scripts/hpc/START_AMINATION_V1_FULL.txt
#     打包：python scripts/hpc/pack_amination_v1_full_hpc.py
#     提交：bash scripts/hpc/submit_amination_v1_full_dsub.sh
```

单底物深挖（可选）：

```bash
python scripts/run_experiment.py --config configs/amination_smoke.yaml
```

## 5. 成功 / 失败判据（试点）

**Go → 全量**，若同时满足：

1. 全部 90 个 run 无崩溃，产出 `loso_summary.csv`  
2. `cold_start` 平均 AUC **明显高于** `random`  
3. `sim_weighted` 不再出现冒烟时那种近零 best（明显管线故障）  
4. 至少能读出：s4 上 warm/gate 相对 cold 的符号（正/负均可，但要稳定可复现）

**No-Go / 修协议**：cold ≤ random；或某策略系统性崩溃。

## 6. 预计耗时（粗估）

本机 sklearn GP、budget=20、warm≤100：试点约 **0.5–2 小时**量级（视 CPU）；全量大约 ×5。  
可先跑预检 + 单策略单底物估时。

## 7. 与旧 TransferBO 的关系

- 同一胺化库、同一 `sub_s*` ID  
- 本轮是 **序贯 BO 回放**，不是旧 pair 级 Δfrac 网格  
- 不在本轮试图“翻盘 Suzuki”；胺化试点通过后再开跨化学对照轨
