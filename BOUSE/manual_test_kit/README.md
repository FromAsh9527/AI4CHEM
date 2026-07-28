# 手动测试物料包（Suzuki）

数据来源：`edbo/edbo-master/experiments/data/suzuki/`

**与 Deoxy 物料的关键区别**：这里的 `04_oracle/experiment_index.csv` 覆盖
**全部 3696 个搜索域点**。因此：界面推荐出什么条件，都能查到真实产率回填，
**不要求**推荐结果碰巧等于某几轮论文条件。

---

## 目录

| 文件夹 | 用途 |
|--------|------|
| `01_molecules/` | SMILES → 描述符界面生成 |
| `02_raw_dft/` | 原始 DFT → 清洗 |
| `03_ready_descriptors/` | 已洗好，直接导入 EDBO |
| `04_oracle/` | 全量真值表 + 可选种子历史 |
| `05_reference_workspace/` | 项目提示 |

因子 key：`electrophile` / `nucleophile` / `ligand` / `base` / `solvent`  
域大小：4 × 3 × 11 × 7 × 4 = **3696**

---

## 推荐手动流程（严格闭环模拟）

### 0. 一键准备项目（推荐）

```bash
cd edbo
python scripts/build_suzuki_workspace.py --seed-n 0
# 或带 10 条种子历史再开 BO：
# python scripts/build_suzuki_workspace.py --seed-n 10 --seed 0
```

然后双击 `start_bouse.bat`，EDBO 打开项目 **`suzuki_demo`**。

### 1. 界面操作

1. 步骤2：确认 5 个化学因子描述符已就绪（构建脚本已写好）
2. 步骤3：
   - 无历史 → **无模型选点**
   - 有历史 → **贝叶斯优化**
3. 步骤4（查表回填，不做实验）：在 `edbo` 目录执行

```bash
python scripts/oracle_backfill.py --project suzuki_demo
```

会读取本轮推荐，从 `oracle.csv` 填 `yield`，写入 `history.csv`。

4. 回到步骤3 再推荐 → 再 `oracle_backfill` → 循环

### 2. 纯手动（不用脚本）

1. 新建项目，因子 key 与上表一致  
2. 导入 `03_ready_descriptors/descriptor_*.csv`  
3. 可选：步骤4 先上传 `04_oracle/seed_history_10.csv`  
4. 推荐后，用推荐里的 SMILES 组合在 `04_oracle/experiment_index.csv` 中筛选对应 `yield`，做成回填 CSV 上传

---

## 自动化自检

```bash
cd edbo
python scripts/build_suzuki_workspace.py --seed-n 0
python scripts/run_suzuki_test_flow.py
```
