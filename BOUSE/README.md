# BOUSE

闭环反应优化工作区：**描述符生成** ∥ **EDBO 优化器**，两侧独立界面，通过约定文件对接。

## 当前目标（三件事）

| # | 目标 | 入口 |
|---|------|------|
| 1 | EDBO 可视化操作界面 | `edbo/` → `streamlit run app.py` |
| 2 | 描述符生成可视化界面 | `descriptors/` → `streamlit run app.py` |
| 3 | 描述符 ↔ BO 对接 | UI 内导入 + `handoff.py` / `CONTRACT.md` |

## 目录

```
BOUSE/
├── CONTRACT.md          # 交接契约
├── handoff.py           # 校验 / 导入（UI 与 CLI 共用）
├── scripts/             # 命令行校验与导入、Suzuki 物料
├── edbo/                # ① EDBO 向导（conda: edbo）
├── descriptors/         # ② 描述符生成 + 对接标签页
├── edbo_plus/           # EDBO+ 多目标向导（conda: edbo_plus，端口 8503）
├── manual_test_kit/     # Suzuki 手测物料包
└── slides/              # 介绍 PPT（可选）
```

## 推荐操作流

```text
描述符界面：SMILES → 生成 CSV
    →「对接 EDBO」写入项目 descriptor_<因子>.csv
        → EDBO 向导步骤 2 确认对接
            → 步骤 3 推荐 → 步骤 4 回填 → 再推荐 …
```

也可在 EDBO 步骤 2 直接上传，或从 `descriptors/output/` 选取。

## 环境（务必分开）

| 用途 | conda | 启动 | 端口 |
|------|-------|------|------|
| 经典 EDBO | **`edbo`** | `start_edbo.bat` | 8501 |
| 描述符 | **`edbo`** | `start_descriptors.bat` | 8502 |
| EDBO+ | **`edbo_plus`** | `start_edbo_plus.bat` | 8503 |

两套优化器包名都是 `edbo`，**禁止共环境**。详见 [`ENV.md`](ENV.md)。

## 启动

**经典栈一键**：双击 `start_bouse.bat`（仅 `edbo`：8501 + 8502）  
**EDBO+**：双击 `start_edbo_plus.bat`（`edbo_plus`：8503）

也可单独启动：`start_edbo.bat` / `start_descriptors.bat` / `start_edbo_plus.bat`。

手动：

```bash
# 经典
conda activate edbo
cd BOUSE/edbo && streamlit run app.py --server.port 8501
cd BOUSE/descriptors && streamlit run app.py --server.port 8502

# EDBO+（另一终端）
conda activate edbo_plus
cd BOUSE/edbo_plus && streamlit run app.py --server.port 8503
```

## 手动测试（Suzuki，推荐）

物料来自官方 **Suzuki** 全量数据（3696 点，推荐任意条件都能查到真实产率）：

- 物料包：`manual_test_kit/`（见其中 `README.md`）
- 工作区：`edbo/workspaces/suzuki_demo`

```bash
# 生成物料 + 工作区
python scripts/prepare_suzuki_test_kit.py
cd edbo
python scripts/build_suzuki_workspace.py --seed-n 0
python scripts/run_suzuki_test_flow.py   # 自动：推荐→查表回填→再推荐

# 手测时：界面推荐后执行
python scripts/oracle_backfill.py --project suzuki_demo
```

然后 `start_bouse.bat`，打开项目 **suzuki_demo**。