# 超算：Step1b Phase A Morgan 全量（胺化 + Suzuki）

协议：`docs/11_step1b_representation.md`  
配置：`configs/*_rep_A_morgan_sub_hpc.yaml`（**5 seeds**，对齐 Step1 全量）  
打包：`python scripts/hpc/pack_rep_A_morgan_hpc.py` → `transferbo2_rep_A_morgan_hpc.tgz`

## 规模

| 库 | jobs | 表示 |
|---|---:|---|
| 胺化 | **450** = 15×6×5 | 条件 OHE + 底物 `morgan_r2` + Tanimoto |
| Suzuki | **360** = 12×6×5 | 同上（跨化学对照轨） |

运行时 **不需要 RDKit / GPU**（指纹已在本机写入 DB）。  
**不做** 条件 DFT（Phase B 暂缓）。

本机曾用 3 seeds 试跑过；HPC 本包补齐到 5 seeds。若上传已有 seed0–2 JSON，`--skip-existing` 会跳过。

## 1. 本机打包

```bash
python scripts/hpc/pack_rep_A_morgan_hpc.py
```

蓝图心算【文件管理】上传 `transferbo2_rep_A_morgan_hpc.tgz`。

## 2. 超算

见快捷条：`scripts/hpc/START_REP_A_MORGAN.txt`

```bash
bash scripts/hpc/submit_amination_rep_A_dsub.sh
bash scripts/hpc/submit_suzuki_rep_A_dsub.sh
# DRY_RUN=1 ... 试提交
```

可调：`N_SHARDS=5 JOB_CPU=16 JOB_MEM_MB=32768 ACCOUNT=...`

## 3. 回收

```bash
python scripts/run_loso.py --config configs/amination_rep_A_morgan_sub_hpc.yaml --rebuild-only
python scripts/run_loso.py --config configs/suzuki_rep_A_morgan_sub_hpc.yaml --rebuild-only
tar -czf ~/rep_A_morgan_results.tgz \
  results/amination_rep_A_morgan_sub_full \
  results/suzuki_rep_A_morgan_sub_full
```

本机分析：

```bash
python scripts/analyze_step1b_rep_A.py \
  --summary-csv results/amination_rep_A_morgan_sub_full/loso_summary.csv \
  --out results/step1b_rep_A
python scripts/analyze_step1b_rep_A.py \
  --summary-csv results/suzuki_rep_A_morgan_sub_full/loso_summary.csv \
  --hashed-csv results/suzuki_v1_full/loso_summary.csv \
  --out results/step1b_rep_A_suzuki --name suzuki_morgan_A
```
