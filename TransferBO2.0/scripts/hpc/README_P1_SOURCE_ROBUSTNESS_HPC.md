# 超算提交：P1 source-subset BO LOSO（TransferBO2.0 Step3）

协议：`docs/17_step3_experiment_plan.md` §4.3（BO 轨）  
打包：`python scripts/hpc/pack_p1_source_robustness_hpc.py` → `transferbo2_p1_source_robustness_hpc.tgz`  
操作条：`scripts/hpc/START_P1_SOURCE_ROBUSTNESS.txt`

| 轨道 | 配置 | n_s | jobs | 输出 |
|---|---|---|---:|---|
| 胺化 | `configs/amination_p1_source_robustness_hpc.yaml` | 1, 3, all | 675 | `results/p1p2_source_robustness/amination/` |
| Suzuki | `configs/suzuki_p1_source_robustness_hpc.yaml` | 3, all | 360 | `results/p1p2_source_robustness/suzuki/` |

策略：`topk_warm` / `cold_start` / `random` · 5 seeds · subset_replicate=0

## 本机

```bash
python scripts/hpc/pack_p1_source_robustness_hpc.py
```

上传 `transferbo2_p1_source_robustness_hpc.tgz` 到超算家目录。

## 超算（一次性提交两轨）

```bash
mkdir -p ~/TransferBO2.0 && cd ~/TransferBO2.0
tar -xzf ~/transferbo2_p1_source_robustness_hpc.tgz
sed -i 's/\r$//' scripts/hpc/*.sh

source $HOME/miniconda3/etc/profile.d/conda.sh && conda activate base
export PYTHONPATH=$PWD/src${PYTHONPATH:+:$PYTHONPATH}

python scripts/run_source_subset_loso.py --config configs/amination_p1_source_robustness_hpc.yaml --dry-run   # 675
python scripts/run_source_subset_loso.py --config configs/suzuki_p1_source_robustness_hpc.yaml --dry-run     # 360

DRY_RUN=1 bash scripts/hpc/submit_p1_all_dsub.sh
bash scripts/hpc/submit_p1_all_dsub.sh
```

或分开：`submit_p1_amination_dsub.sh` / `submit_p1_suzuki_dsub.sh`

默认 5 shard × 2 库 = **10 个 dsub 作业**（按 seed 分片，每 shard 16 CPU）。

## 进度

```bash
find results/p1p2_source_robustness/amination -name '*__seed*.json' | wc -l   # 675
find results/p1p2_source_robustness/suzuki -name '*__seed*.json' | wc -l     # 360
```

## 收工回传

```bash
tar -czf ~/p1_source_robustness_bo_results.tgz \
  results/p1p2_source_robustness/amination \
  results/p1p2_source_robustness/suzuki
```

离线清单分析（已有 CSV 时）与本机合并：

```bash
python scripts/analyze_p1p2_list_stability.py --library both
```
