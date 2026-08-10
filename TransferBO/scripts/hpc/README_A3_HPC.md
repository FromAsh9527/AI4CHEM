# 超算提交 A3（EDBO Suzuki source-weighted）

本地已暂停。进度：**497 / 6720** JSON 在 `results/external_edbo_suzuki_a3/`。

## 1. 打包上传（在仓库 `TransferBO/` 下）

至少需要：

```text
configs/transfer_grid_edbo_suzuki_a3.yaml
configs/protocol.yaml          # 若 run_transfer_grid 会读
src/
scripts/run_transfer_grid.py
scripts/run_experiment.py
scripts/hpc/                   # 本目录提交脚本
pyproject.toml / requirements.txt
data/processed/edbo_suzuki_plates.csv
data/descriptors/edbo_suzuki_condition_dft.csv
results/external_edbo_suzuki_a3/   # 已有 JSON，用于 --skip-existing 续跑
```

示例（在 Linux/WSL 或 Git Bash）：

```bash
cd TransferBO
tar -czf transferbo_a3_hpc.tgz \
  configs/transfer_grid_edbo_suzuki_a3.yaml configs/protocol.yaml \
  src scripts/run_transfer_grid.py scripts/run_experiment.py scripts/hpc \
  pyproject.toml requirements.txt \
  data/processed/edbo_suzuki_plates.csv \
  data/descriptors/edbo_suzuki_condition_dft.csv \
  results/external_edbo_suzuki_a3
# scp transferbo_a3_hpc.tgz user@hpc:~/
```

## 2. 超算环境

```bash
conda create -n transferbo python=3.10 -y
conda activate transferbo
pip install -r requirements.txt
# 若用 editable：
# pip install -e .
```

A3 主路径只要 **sklearn + numpy/pandas**（Morgan/DFT）；**不需要 GPU**，也不需要 RDKit 以外的重依赖（Morgan 需要 RDKit，见 `requirements.txt`）。

## 3. 两种跑法

### A. 单节点大并行（简单）

编辑 `scripts/hpc/run_a3_slurm.sh` 里的分区/账本/核数，然后：

```bash
mkdir -p logs
sbatch scripts/hpc/run_a3_slurm.sh
```

### B. 数组作业按 seed 分片（推荐，好排队）

```bash
mkdir -p logs
sbatch scripts/hpc/run_a3_array_slurm.sh   # 0-19 共 20 个 seed 分片
```

每片：`python scripts/hpc/run_a3_shard.py --shard-id $ID --n-shards 20 --workers 8`

## 4. 续跑与回收

- 一律加 `--skip-existing`（脚本里已加）。
- 算完打包 `results/external_edbo_suzuki_a3/` 回传本地，再跑 `scripts/summarize_edbo_a2.py` 同风格的 A3 汇总（或告诉我生成 `summarize_edbo_a3.py`）。

## 5. 规模提醒

| 项 | 数 |
|---|---|
| 总 job | 6720 = 3 权重 × 2 表示 × 1120 |
| 已完成（本地） | ~497 |
| 剩余 | ~6223 |

若中心是 **PBS/LSF** 而不是 Slurm，把 `#SBATCH` 改成对应头即可，命令行不变。
