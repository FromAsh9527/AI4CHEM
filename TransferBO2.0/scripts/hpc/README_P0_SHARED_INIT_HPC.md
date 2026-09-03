# 超算提交：P0 shared-init audit（TransferBO2.0 Step3）

协议：`docs/17_step3_experiment_plan.md` §3  
打包：`python scripts/hpc/pack_p0_shared_init_hpc.py` → `transferbo2_p0_shared_init_hpc.tgz`  
操作条：`scripts/hpc/START_P0_SHARED_INIT.txt`

| 轨道 | 配置 | jobs | 输出 |
|---|---|---:|---|
| 胺化 sanity | `configs/amination_p0_shared_init_sanity.yaml` | 60 | `results/amination_p0_shared_init_sanity/` |
| Suzuki 全量 | `configs/suzuki_p0_shared_init_hpc.yaml` | 360 | `results/suzuki_p0_shared_init/` |

## 本机

```bash
python scripts/hpc/pack_p0_shared_init_hpc.py
```

蓝图心算上传 `transferbo2_p0_shared_init_hpc.tgz` 到超算家目录。

## 超算（一次性提交两轨）

```bash
mkdir -p ~/TransferBO2.0 && cd ~/TransferBO2.0
tar -xzf ~/transferbo2_p0_shared_init_hpc.tgz
sed -i 's/\r$//' scripts/hpc/*.sh

source $HOME/miniconda3/etc/profile.d/conda.sh && conda activate base
export PYTHONPATH=$PWD/src${PYTHONPATH:+:$PYTHONPATH}

python scripts/run_loso.py --config configs/amination_p0_shared_init_sanity.yaml --dry-run   # 60
python scripts/run_loso.py --config configs/suzuki_p0_shared_init_hpc.yaml --dry-run         # 360

bash scripts/hpc/submit_p0_all_dsub.sh
```

或分开：`submit_p0_amination_sanity_dsub.sh` / `submit_p0_suzuki_dsub.sh`

## 进度

```bash
find results/amination_p0_shared_init_sanity -name '*.json' ! -name 'loso_records.json' | wc -l   # 60
find results/suzuki_p0_shared_init -name '*.json' ! -name 'loso_records.json' | wc -l           # 360
```

## 分析（收工后）

```bash
python scripts/analyze_p0_shared_init.py \
  --results-dir results/amination_p0_shared_init_sanity \
  --reference-dir results/amination_v1_full
python scripts/analyze_p0_shared_init.py \
  --results-dir results/suzuki_p0_shared_init \
  --reference-dir results/suzuki_v1_full
```

回传：`tar -czf ~/p0_shared_init_results.tgz results/amination_p0_shared_init_sanity results/suzuki_p0_shared_init`
