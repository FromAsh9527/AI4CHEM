# 超算提交：Ni borylation P4 主外部验证 LOSO（TransferBO2.0）

预注册：`docs/18_p4_hitea_holdout.md`（§2.1 裁决：borylation 升级为主验证库）  
数据审计：`results/p4_borylation/`（33 任务 × 23 配体 × 2 溶剂 = 1518 格**完整交叉积**，单次测量；产率中位 46.5、失败 4%）  
出处：Organometallics 2022（10.1021/acs.organomet.2c00089）/ Doyle lab ochem-data NiB；与 Digital Discovery 2025 配套 borylation.csv 逐格对账一致  
配置：`configs/borylation_p4_holdout_hpc.yaml`  
输出：`results/p4_borylation/loso/`（每 job 一个 JSON + `loso_summary.csv`）

## 规模

| 项 | 数 |
|---|---|
| 总 job | **990** = 33 任务 × 6 策略 × 5 seeds |
| 策略 | random / cold_start / topk_warm / nearest_topk_warm / cold_random_post / topk_random_post |
| 表示 | 条件 OHE；底物 **morgan_r2** + Tanimoto（nearest 臂；SMILES 由 InChI 转换） |
| 预算 | n_init=5, budget=20, EI |
| 依赖 | sklearn GP；**LOSO 运行不需要 RDKit**（描述符已预计算入库） |
| 数据 | `data/db/transferbo2_borylation.db`（33 任务 × 46 条件） |

本地 pilot 已 Go（12/12 jobs，`results/p4_borylation/pilot/`）。

## 1. 本机打包

```bash
python scripts/hpc/pack_borylation_p4_hpc.py
```

产出：`transferbo2_borylation_p4_hpc.tgz`（含 DB + long CSV）。用蓝图心算【文件管理】传到远程家目录。

## 2. 超算解压与环境

```bash
mkdir -p ~/TransferBO2.0
cd ~/TransferBO2.0
tar -xzf ~/transferbo2_borylation_p4_hpc.tgz

source $HOME/miniconda3/etc/profile.d/conda.sh
conda activate base
pip install -r requirements.txt   # 已装过可跳过
export PYTHONPATH=$PWD/src${PYTHONPATH:+:$PYTHONPATH}

python scripts/run_loso.py --config configs/borylation_p4_holdout_hpc.yaml --dry-run
# 应打印 Total jobs: 990
```

## 3. 提交：dsub 按 seed 分片（5 片）

```bash
DRY_RUN=1 bash scripts/hpc/submit_borylation_p4_dsub.sh   # 先试
bash scripts/hpc/submit_borylation_p4_dsub.sh
```

每片 1 个 seed × 198 job；`--skip-existing` 断点续跑。

## 4. 进度与回收

```bash
find results/p4_borylation/loso -name '*.json' ! -name 'loso_records.json' | wc -l
# 目标 990

python scripts/run_loso.py --config configs/borylation_p4_holdout_hpc.yaml --rebuild-only
tar -czf ~/borylation_p4_results.tgz results/p4_borylation
```

回传本机后：解压到 `results/p4_borylation/`，运行 `scripts/analyze_round_metrics.py`（已含 borylation 库）与
`python scripts/analyze_amination_matched_init.py --results-dir results/p4_borylation/loso --frozen-dir results/p4_borylation/loso --out-dir results/p4_borylation/matched_init`。

## 5. 预注册判定速查（docs/18 §4）

| 结果 | 判定 |
|---|---|
| topk vs cold > 0 且 CI 排除 0，且 vs random > 0 | **强复现** → 策略草稿升"已验证（跨源）" |
| 方向一致但 CI 含 0，或仅 vs cold 正 | 部分复现 → 草稿保持，写明边界 |
| topk vs cold ≤ 0 或 vs random ≤ 0 | 未复现 → 收窄适用边界 |

C1/C2（matched-init）与胺化/Suzuki/HiTEA 对照 → "价值位置库相关"主张。  
LSO 源数门槛 → `scripts/analyze_hitea_lso.py` 同款逻辑（borylation 33 源，K=20）。

**禁止：** 调 k / 换聚合规则 / 换表示 / 回改 Step1 主表与 EDBO 锁。
