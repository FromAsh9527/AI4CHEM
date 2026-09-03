# 实验协议：一对一源→靶（TransferBO 1.0 口径，可选轨）

冻结日期：2026-08-20  
实验 ID：`amination_pair_v1` / `suzuki_pair_v1`  
状态：**已配置，默认不跑**；LOSO 全量之后按需开启。

## 1. 与 LOSO 的关系

| 轨 | 历史 | 问题 |
|---|---|---|
| LOSO（已跑/在跑） | 其余全部底物混池 | 多源积累后迁移有没有净收益 |
| **Pair（本轨）** | **仅一个源底物 \(S\)** | 单源 \(S\to T\) 是否可靠（接 1.0） |

目标产率仍不进历史；仅限制历史为单源。

## 2. Job 计数（避免基线重复）

- **baseline**（`random`, `cold_start`）：每个目标 × seed **各 1 次**（`source=none`）  
- **transfer**（`topk_warm`, `nearest_topk_warm`, `sim_weighted`, `safe_gate`）：每个有向对 \(S\to T\)（\(S\neq T\)）× seed

| 库 | baseline | transfer | **全量合计** |
|---|---:|---:|---:|
| 胺化 15 | \(15\times2\times5=150\) | \(15\times14\times4\times5=4200\) | **4350** |
| Suzuki 12 | \(12\times2\times5=120\) | \(12\times11\times4\times5=2640\) | **2760** |

试点（小网格，先冒烟）：

| 库 | 配置 | 约计 |
|---|---|---:|
| 胺化 | 3 target × 3 source × … | ~126 |
| Suzuki | 3 target × 3 source × … | ~126 |

## 3. 材料

```text
configs/amination_pair_v1_pilot.yaml
configs/amination_pair_v1_full.yaml
configs/suzuki_pair_v1_pilot.yaml
configs/suzuki_pair_v1_full.yaml
scripts/run_pair.py
scripts/hpc/START_PAIR_V1.txt
```

表示 / 预算与 LOSO 相同：OHE + hashed SMILES，n_init=5，budget=20。

## 4. 命令（以后开跑时）

```bash
# dry-run 看 job 数
python scripts/run_pair.py --config configs/amination_pair_v1_full.yaml --dry-run
python scripts/run_pair.py --config configs/suzuki_pair_v1_full.yaml --dry-run

# 本机试点
python scripts/run_pair.py --config configs/amination_pair_v1_pilot.yaml --skip-existing --workers 1

# 超算：见 scripts/hpc/START_PAIR_V1.txt
```

输出：`results/*_pair_v1_*/{strategy}__{source}__{target}__seed{k}.json` + `pair_summary.csv`

## 5. 解读口径

- 对每个 \(T\)：transfer 相对 **同 target 的 cold** 算 ΔAUC / NTR（跨 source 聚合或画 \(S\times T\) 热图）  
- 与 LOSO 对照：池化 topk 是否只是“多源平均”带来的假象  
- `nearest_topk` 在单源设定下 ≈ 该源的 topk（几乎冗余，保留为接口一致）

## 6. Go（若开跑）

试点无崩溃 + dry-run 计数与上表一致 → 再全量。
