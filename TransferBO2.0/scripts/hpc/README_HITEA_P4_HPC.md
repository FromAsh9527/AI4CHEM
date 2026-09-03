# 超算提交：HiTEA Suzuki P4 holdout LOSO（TransferBO2.0）

预注册：`docs/18_p4_hitea_holdout.md`  
数据审计：`results/p4_hitea/audit.md`（SUZUKI 11 任务 ≥40 核心条件；30% 失败样本）  
配置：`configs/hitea_p4_holdout_hpc.yaml`  
输出：`results/p4_hitea/loso/`（每 job 一个 JSON + `loso_summary.csv`）

## 规模

| 项 | 数 |
|---|---|
| 总 job | **330** = 11 任务 × 6 策略 × 5 seeds |
| 策略 | random / cold_start / topk_warm / nearest_topk_warm / cold_random_post / topk_random_post |
| 表示 | 条件 OHE；底物 **morgan_r2** + Tanimoto（nearest 臂） |
| 预算 | n_init=5, budget=20, EI |
| 依赖 | sklearn GP + **RDKit**（仅 ingest 用；HPC 上跑 LOSO 不需要 RDKit，但已随包带上） |
| 数据 | `data/db/transferbo2_hitea.db`（11 任务 × 94 条件；plate_id = 真实 screen 批次） |

本地 pilot 已 Go（12/12 jobs，`results/p4_hitea/pilot/`）。

## 1. 本机打包

```bash
python scripts/hpc/pack_hitea_p4_hpc.py
```

产出：`transferbo2_hitea_p4_hpc.tgz`（含 `data/db/transferbo2_hitea.db` 与 long CSV，约几 MB）。  
用蓝图心算【文件管理】传到远程家目录。

## 2. 超算解压与环境

```bash
mkdir -p ~/TransferBO2.0
cd ~/TransferBO2.0
tar -xzf ~/transferbo2_hitea_p4_hpc.tgz

source $HOME/miniconda3/etc/profile.d/conda.sh
conda activate base
pip install -r requirements.txt   # 已装过可跳过
export PYTHONPATH=$PWD/src${PYTHONPATH:+:$PYTHONPATH}

python scripts/run_loso.py --config configs/hitea_p4_holdout_hpc.yaml --dry-run
# 应打印 Total jobs: 330
```

## 3. 提交：dsub 按 seed 分片（5 片）

```bash
DRY_RUN=1 bash scripts/hpc/submit_hitea_p4_dsub.sh   # 先试
bash scripts/hpc/submit_hitea_p4_dsub.sh
```

可调：`N_SHARDS=5 JOB_CPU=16 JOB_MEM_MB=32768 ACCOUNT=...`  
每片 1 个 seed × 66 job；`--skip-existing` 断点续跑（shard runner 已带）。

## 4. 进度与回收

```bash
find results/p4_hitea/loso -name '*.json' ! -name 'loso_records.json' | wc -l
# 目标 330

python scripts/run_loso.py --config configs/hitea_p4_holdout_hpc.yaml --rebuild-only
tar -czf ~/hitea_p4_results.tgz results/p4_hitea
```

回传本机后：

```bash
tar -xzf hitea_p4_results.tgz -C results
# 主看（三态判定，docs/18 §4）：
python scripts/analyze_step1_effects.py   # 或按需复用审计脚本
python scripts/analyze_round_metrics.py --results-dir results/p4_hitea/loso 2>nul
python scripts/analyze_amination_matched_init.py --results-dir results/p4_hitea/loso
```

## 5. 预注册判定速查（docs/18 §4，跑前写死）

| 结果 | 判定 |
|---|---|
| topk vs cold > 0 且 CI 排除 0，且 vs random > 0 | 强复现 → 策略草稿升"已验证（跨源）" |
| 方向一致但 CI 含 0，或仅 vs cold 正 | 部分复现 → 草稿保持，写明边界 |
| topk vs cold ≤ 0 或 vs random ≤ 0 | 未复现 → 收窄为"仅 EDBO 库内成立" |

C1/C2（matched-init）符号模式与胺化/Suzuki 比较 → 检验"价值位置库相关"主张。  
LSO 源数门槛跨家族检验 → 离线重跑 `analyze_p1p2_list_stability.py` 逻辑（零 BO 成本）。

**禁止：** 在 HiTEA 上调 k / 换聚合规则 / 换表示 / 回改 Step1 主表。
