# 超算提交：amination_v1 full LOSO（TransferBO2.0）

协议：`docs/06_experiment_amination_v1.md`  
配置：`configs/amination_exp_v1_full.yaml`  
输出：`results/amination_v1_full/`（每 job 一个 JSON + `loso_summary.csv`）

## 规模

| 项 | 数 |
|---|---|
| 总 job | **450** = 15 底物 × 6 策略 × 5 seeds |
| 表示 | 条件 OHE + 底物 hashed SMILES |
| 预算 | n_init=5, budget=20 |
| 依赖 | sklearn GP；**不需要 GPU / RDKit** |

试点已 Go；本包仅跑全量。

## 1. 本机打包

在 `TransferBO2.0/`：

```bash
python scripts/hpc/pack_amination_v1_full_hpc.py
```

产出：`transferbo2_amination_v1_full_hpc.tgz`（含 `data/db/transferbo2.db`，约数 MB）。  
用蓝图心算【文件管理】传到远程家目录（与旧 TransferBO 同款；不要依赖 `scp user@hpc`）。

## 2. 超算解压与环境

```bash
mkdir -p ~/TransferBO2.0
cd ~/TransferBO2.0
tar -xzf ~/transferbo2_amination_v1_full_hpc.tgz

source $HOME/miniconda3/etc/profile.d/conda.sh
conda activate base   # 可复用 TransferBO 的 base；缺包再 pip
pip install -r requirements.txt   # 已装过可跳过
export PYTHONPATH=$PWD/src${PYTHONPATH:+:$PYTHONPATH}

mkdir -p results/amination_v1_full logs
python scripts/run_loso.py --config configs/amination_exp_v1_full.yaml --dry-run
# 应打印 Total jobs: 450
```

## 3. 推荐：dsub 按 seed 分片（5 片）

```bash
cd ~/TransferBO2.0
python scripts/hpc/run_amination_v1_full_shard.py --shard-id 0 --n-shards 5 --dry-run

bash scripts/hpc/submit_amination_v1_full_dsub.sh
# 或 DRY_RUN=1 bash scripts/hpc/submit_amination_v1_full_dsub.sh
```

可调：`N_SHARDS=5 JOB_CPU=16 JOB_MEM_MB=32768 ACCOUNT=...`  
每片 1 个 seed × 90 job；`--skip-existing` 可断点续跑。

## 4. 备选：Slurm / nohup

```bash
mkdir -p logs
sbatch scripts/hpc/run_amination_v1_full_array_slurm.sh   # 0-4
# 或单节点:
# sbatch scripts/hpc/run_amination_v1_full_slurm.sh
# 登录节点小心试跑:
# WORKERS=8 bash scripts/hpc/run_amination_v1_full_nohup.sh
```

## 5. 进度与回收

```bash
find results/amination_v1_full -name '*.json' ! -name 'loso_records.json' | wc -l
# 目标 450

python scripts/run_loso.py --config configs/amination_exp_v1_full.yaml --rebuild-only
python scripts/summarize_results.py --summary-csv results/amination_v1_full/loso_summary.csv
```

打包结果回传：

```bash
tar -czf ~/amination_v1_full_results.tgz results/amination_v1_full
```

本地汇总同命令。主看：相对 cold 的 ΔAUC、NTR、`topk_warm` vs `nearest_topk_warm`。
