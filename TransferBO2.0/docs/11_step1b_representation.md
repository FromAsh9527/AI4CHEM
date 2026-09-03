# Step 1b — 表示轴稳健性（化学信息表示）

冻结关系：不删除 Step1 OHE 结论；本步回答「换化学表示后效应是否仍成立」。  
**状态（2026-08-21）：已收口** — 不再换表示；见 §11 与 `docs/12_plan_after_step1.md`。  
总框架：`docs/00_research_framework.md`  
Step1 主锁：`docs/10_step1_transfer_effects.md` / `FROZEN_CLAIMS.md`

---

## 1. 为什么先做表示轴

当前近邻 / 加权 / 门控依赖的底物相似是 **hashed SMILES**，几乎无化学信息。  
在未换表示前谈「化学机制」或「相似底物该不该迁」会虚。

**一次只动表示**；库与策略集先保持与 Step1 全量一致。

---

## 2. 两阶段（推荐顺序）

### Phase A — 只换底物表示（优先跑）

| 轴 | 设定 |
|---|---|
| 条件 \(x\) | **仍 OHE**（与 Step1 同） |
| 底物 \(\phi(s)\) | **Morgan r=2, 2048 bit**（`morgan_r2`） |
| 相似度量 | **Tanimoto**（不用 RBF） |
| 受影响策略 | `nearest_topk_warm`, `sim_weighted`, `safe_gate`, `topk_safe_gate` |
| 不受影响 | `random`, `cold_start`, `topk_warm`（不看 \(\phi(s)\)） |

科学问题：化学相似是否改变「近邻 vs 全局 topk」「加权是否变有用」。

### Phase B — 再换条件表示

| 轴 | 设定 |
|---|---|
| 条件 \(x\) | `morgan_r2`（组分 bit 或）或 **`dft`**（已有 EDBO condition DFT，与 `condition_id` 对齐） |
| 底物 | Phase A 的 `morgan_r2` 或仍 hashed（对照） |
| 受影响 | 所有用 GP 的策略（含 cold） |

一次只开一个条件表示；DFT 与 Morgan 分配置，勿混报。

---

## 3. 材料

| 项 | 路径 |
|---|---|
| 构建底物 Morgan | `python scripts/build_morgan_descriptors.py` |
| 预检 | `python scripts/preflight_step1b_rep.py` |
| Phase A 试点 | `configs/amination_rep_A_morgan_sub_pilot.yaml` |
| Phase A 全量 | `configs/amination_rep_A_morgan_sub_full.yaml` |
| Phase B DFT 试点 | `configs/amination_rep_B_dft_cond_pilot.yaml` |
| Suzuki 对应 | `configs/suzuki_rep_A_*` / `suzuki_rep_B_*` |

依赖：RDKit（本机已有则可直接建库）。

---

## 4. 统计口径（继承 Step1）

- 推断单位 = **target**（先平均 seed）  
- 主报 vs cold / vs random  
- 再生：`python scripts/analyze_step1_effects.py`（改 `--summary-csv` 或扩展脚本指向新 out_dir）

Phase A 解读焦点：

- nearest / sim 的 Δ 是否相对 OHE+hashed **显著变化**  
- topk_warm 应与 Step1 **数值一致**（健全性检查）

---

## 5. 运行顺序

```bash
# 0) 写入 morgan_r2 到胺化/Suzuki DB（保留 hashed_smiles_v1）
python scripts/build_morgan_descriptors.py

# 1) 预检
python scripts/preflight_step1b_rep.py

# 2) Phase A 试点（胺化）
python scripts/run_loso.py --config configs/amination_rep_A_morgan_sub_pilot.yaml --skip-existing --workers 1

# 3) 试点 Go 后再全量 / Suzuki A / Phase B
```

---

## 6. Go / No-Go（Phase A 试点）

Go 全量 A：

1. 无崩溃；`topk_warm` 与 Step1 同 seed 靶上 AUC **一致**（容差数值噪声）  
2. nearest / sim 至少跑出可读的靶级符号  
3. 描述符覆盖全部底物

No-Go：Morgan 入库失败、或 topk 与 Step1 无故不一致（接线 bug）。

---

## 7. 胺化 Phase A 全量结果

- HPC 5 seeds（正式）：`results/amination_rep_A_morgan_sub_full/`（**450** jobs）  
- 分析：`results/step1b_rep_A/summary.md`  
- 健全性：`random` / `cold` / `topk` 与 hashed 同 seed **Δ=0**

靶级主结论（vs cold，5 seeds）：

| strategy | Δcold mean [95% CI] | 备注 |
|---|---|---|
| topk_warm | +160 [+108, +212] | 与 Step1 同量级 |
| nearest_topk_warm | +171 [+119, +218] | Morgan 下略高于 topk |
| sim_weighted | +16 [−6, +35] | CI 含 0，近 null |
| safe_gate | 弱正 | — |

**Go**：表示轴胺化侧可读。DFT Phase B 仍暂缓。

---

## 8. Suzuki Phase A

配置：`configs/suzuki_rep_A_morgan_sub_full.yaml`（本机 3 seeds）  
HPC 全量（5 seeds）：`configs/suzuki_rep_A_morgan_sub_hpc.yaml`  
打包：`python scripts/hpc/pack_rep_A_morgan_hpc.py` → 见 `scripts/hpc/START_REP_A_MORGAN.txt`

同协议：条件 OHE，底物 `morgan_r2` + Tanimoto。对照轨：冷启动 BO 仍不稳赢 random（Q1），**不**用 Q1 否决 topk。

### HPC 5-seed 正式（360 jobs）

分析：`results/step1b_rep_A_suzuki/summary.md`（健全性：unaffected Δ=0）

| strategy | Δcold | vs random | 备注 |
|---|---|---|---|
| topk_warm | +150 | 弱正（CI 贴 0） | 与 hashed 一致；历史策略证据仍在 |
| nearest_topk_warm | +166 | 正 | 略高于 topk（表示敏感） |
| random vs cold | +58（CI 含 0） | — | Q1 仍失败（基线 BO 备注） |
| sim_weighted | +57 vs cold | vs random ≈ 0 | 加权仍非主策略 |

Morgan **未**把 Suzuki 变成与胺化同级的稳健迁移；**未**推翻 topk vs cold 为正。

---

## 9. Phase B — Suzuki 条件 DFT 试点

配置：`configs/suzuki_rep_B_dft_cond_pilot.yaml`  
设定：条件 **DFT**（860 维）+ 底物仍 `morgan_r2` + Tanimoto。  
规模：3×6×2 = **36** jobs（已跑，~20 min）。  
分析：`results/step1b_rep_B_suzuki_dft_pilot/summary.md`

试点读数（仅 3 靶，勿当全量）：

| 观察 | 含义 |
|---|---|
| `random` 与 Phase A 同 seed 一致 | 接线 OK |
| `topk_warm` 相对同子集 OHE **更差**（约 −157 AUC） | DFT 未改善全局 topk |
| cold ≈ random（Δ 小、CI 宽） | Q1 未因 DFT 翻盘；不升全量 |
| nearest 仍最高，但 vs cold CI 含 0 | 不稳定，不宜升全量 |

**建议**：**不升** Suzuki DFT 全量；与「本地 DFT 效果不佳」一致。

---

## 10. Phase B — 底物+条件均为 Morgan（超算，已完成）

配置：
- `configs/amination_rep_B_morgan_both_hpc.yaml`（450）
- `configs/suzuki_rep_B_morgan_both_hpc.yaml`（360）

分析：`results/step1b_rep_B_morgan_both/`、`results/step1b_rep_B_morgan_both_suzuki/`

| 库 | 要点 |
|---|---|
| 胺化 | random 与 A 一致（健全）；cold 绝对 AUC −51；topk 绝对 −27 但 Δcold 仍强；nearest ≳ topk |
| Suzuki | topk Δcold CI 跨 0；cold 仍 ≯ random；nearest 仍最高 |

**结论**：条件 Morgan **不优于** OHE，不升默认。

---

## 11. 表示轴收口（2026-08-21）

| 决定 | 内容 |
|---|---|
| 条件特征默认 | **OHE** |
| 底物相似（机制/近邻） | **morgan_r2 + Tanimoto** |
| DFT 条件 | 试点否决，不升全量 |
| 条件 Morgan | 全量已跑，不升默认 |
| 下一步 | `docs/12_plan_after_step1.md` P1 机制，不再换表示 |

