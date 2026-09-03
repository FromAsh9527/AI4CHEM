# 超算提交：suzuki_v1 full LOSO（TransferBO2.0）

协议：`docs/07_experiment_suzuki_v1.md`  
配置：`configs/suzuki_exp_v1_full.yaml`  
输出：`results/suzuki_v1_full/` — **360** JSON（12×6×5）

与胺化同表示（OHE + hashed SMILES）与同 6 策略；独立 DB `transferbo2_suzuki.db`。

## 打包

```bash
python scripts/ingest_suzuki.py   # 若尚未入库
python scripts/hpc/pack_suzuki_v1_full_hpc.py
```

上传 `transferbo2_suzuki_v1_full_hpc.tgz` → 家目录。

## 超算

```bash
mkdir -p ~/TransferBO2.0 && cd ~/TransferBO2.0
tar -xzf ~/transferbo2_suzuki_v1_full_hpc.tgz
sed -i 's/\r$//' scripts/hpc/*.sh   # 保险

source $HOME/miniconda3/etc/profile.d/conda.sh && conda activate base
export PYTHONPATH=$PWD/src${PYTHONPATH:+:$PYTHONPATH}

python scripts/run_loso.py --config configs/suzuki_exp_v1_full.yaml --dry-run
# Total jobs: 360

bash scripts/hpc/submit_suzuki_v1_full_dsub.sh
```

进度：`find results/suzuki_v1_full -name '*.json' ! -name 'loso_records.json' | wc -l` → 360

回传：`tar -czf ~/suzuki_v1_full_results.tgz results/suzuki_v1_full`
