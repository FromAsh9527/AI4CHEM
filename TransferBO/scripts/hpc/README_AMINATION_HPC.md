# 超算提交 W8：EDBO amination min S0

协议：`configs/transfer_grid_edbo_amination_min_s0.yaml`  
输出：`results/external_edbo_amination_min_s0/`  
汇总：`python scripts/summarize_amination_min_s0.py --root results/external_edbo_amination_min_s0`

## 规模

| 项 | 数 |
|---|---|
| 总 job | **2560** |
| cold_start | 320 = 2 reps × 8 plates × 20 seeds |
| label_warm | 2240 = 2 × 8×7 directed pairs × 20 seeds |
| 表示 | Morgan + DFT |
| 预算 | B=100（主终点仍报 B∈{30,40,50}） |

本地试点（可忽略/勿混进全量目录）：`results/external_edbo_amination_min_s0_pilot/`

## 1. 打包上传（本机 `TransferBO/`）

```bash
cd TransferBO
tar -czf transferbo_amination_hpc.tgz \
  configs/transfer_grid_edbo_amination_min_s0.yaml \
  configs/protocol.yaml \
  src \
  scripts/run_transfer_grid.py \
  scripts/run_experiment.py \
  scripts/summarize_amination_min_s0.py \
  scripts/hpc \
  pyproject.toml requirements.txt \
  data/processed/edbo_amination_plates.csv \
  data/descriptors/edbo_amination_condition_dft.csv
# scp transferbo_amination_hpc.tgz user@hpc:~/
```

超算上：

```bash
mkdir -p ~/TransferBO && cd ~/TransferBO
tar -xzf ~/transferbo_amination_hpc.tgz
# 若已有 conda 环境则复用 A3 的 transferbo / base
pip install -r requirements.txt   # 或已装过则跳过
mkdir -p results/external_edbo_amination_min_s0 logs
```

依赖：sklearn + RDKit（Morgan）+ numpy/pandas；**不需要 GPU**。

## 2. 推荐：dsub 按 seed 分片（与 A3 同款）

```bash
cd ~/TransferBO
# 先确认分片命令
python scripts/hpc/run_amination_shard.py --shard-id 0 --n-shards 20 --dry-run

# 正式提交 20 片（每片 1 个 seed，workers=申请核数）
bash scripts/hpc/submit_amination_dsub.sh

# 或只生成作业脚本不提交
DRY_RUN=1 bash scripts/hpc/submit_amination_dsub.sh
```

可调：`N_SHARDS=20 JOB_CPU=32 JOB_MEM_MB=65536 ACCOUNT=...`

## 3. 备选：Slurm / nohup

```bash
mkdir -p logs
sbatch scripts/hpc/run_amination_array_slurm.sh   # 0-19
# 或单节点:
# sbatch scripts/hpc/run_amination_slurm.sh
# 或登录节点小心试跑:
# WORKERS=8 bash scripts/hpc/run_amination_nohup.sh
```

一律 `--skip-existing`，可断点续跑。

## 4. 进度与回收

```bash
ls results/external_edbo_amination_min_s0/*.json 2>/dev/null | wc -l   # 目标 2560
```

回传后本地：

```bash
python scripts/summarize_amination_min_s0.py \
  --root results/external_edbo_amination_min_s0 \
  --out-prefix edbo_amination_min_s0
```

写入口径分支见汇总 md；**勿用 pilot 的 8 JSON 升级跨家族主张**。

## 5. 烟雾检查（提交前）

```bash
python scripts/run_transfer_grid.py \
  --config configs/transfer_grid_edbo_amination_min_s0.yaml \
  --dry-run | head
# 应看到 Total jobs: 2560
```
