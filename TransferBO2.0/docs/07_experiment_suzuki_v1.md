# 实验协议 v1：EDBO Suzuki LOSO（与胺化同表示 / 同策略）

冻结日期：2026-08-20  
实验 ID：`suzuki_v1`

## 1. 科学问题

在 **EDBO Suzuki–Miyaura**（12 偶联对 × 308 条件）上，用与胺化 **完全相同** 的设定：

1. cold 是否优于 random？  
2. topk / nearest_topk warm-start 是否仍改善 AUC？  
3. sim_weighted / safe_gate 相对 cold 的 ΔAUC 与 NTR？  
4. 与胺化全量对比：迁移是否跨反应类型仍成立，还是胺化特有？

**叙事**：跨化学对照轨（Q1 对照；不作“翻盘旧 TransferBO Suzuki 结论”的唯一目标）。「硬负例」仅指冷启动 BO 相对随机不可靠，**不**否决历史 topk。

## 2. 材料

| 材料 | 路径 |
|---|---|
| 源表 | `../TransferBO/data/processed/edbo_suzuki_plates.csv` |
| 入库 | `python scripts/ingest_suzuki.py` |
| DB | `data/db/transferbo2_suzuki.db`（**不覆盖**胺化 DB） |
| 长表 | `data/processed/suzuki_long.csv` |
| 条件表示 | OHE(ligand × base × solvent) |
| 底物表示 | hashed SMILES on `elec\|\|nuc` |
| 试点 / 全量 | `configs/suzuki_exp_v1_pilot.yaml` / `_full.yaml` |

语义：`substrate_id = suz_t*`；`plate_id = logical_{suz_t*}`（逻辑板，非真批次）。

## 3. 方法（对齐胺化）

- LOSO；策略同 6 个：random, cold_start, topk_warm, nearest_topk_warm, sim_weighted, safe_gate  
- n_init=5, budget=20；`use_plate_correction: false`；`warm_strength=0.5`  
- Pilot：5 任务 × 6 × 3 seeds = **90**  
- Full：12 × 6 × 5 = **360**

## 4. 命令

```bash
python scripts/ingest_suzuki.py
python scripts/preflight_suzuki_v1.py

# 本机试点（低占用可参考胺化 lowcpu 包装）
python scripts/run_loso.py --config configs/suzuki_exp_v1_pilot.yaml --skip-existing --workers 1

# 超算全量
python scripts/hpc/pack_suzuki_v1_full_hpc.py
# 见 scripts/hpc/START_SUZUKI_V1_FULL.txt
```

## 5. Go / No-Go（试点）

1. 90 run 无崩溃  
2. cold 平均 AUC 明显高于 random  
3. sim_weighted 无管线级崩溃（近零 best）  
4. 至少能读出 topk 相对 cold 的符号（正/负均可）

通过后再全量；结果与 `amination_v1_full` 对照写结论。
