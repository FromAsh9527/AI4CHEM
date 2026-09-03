# HTEBO

高通量实验与贝叶斯优化（HTE + BO）相关开题、文献与图表材料。

## 目录结构（与本地网盘对齐）

```
HTEBO/
├── 01_开题与汇报/          ← 开题报告 docx/md 与生成脚本
├── 02_文献/papers/         ← PDF 不进 Git（见 .gitignore）
├── 06_图表与展示/figures/  ← 图件；终稿 ChemDraw 重绘
└── SYNC.md                 ← 本地 ↔ Git 同步说明
```

## 当前开题版本

| 版本 | 文件 | 说明 |
|------|------|------|
| **v5（仓库主版本）** | `01_开题与汇报/开题报告_*修订版v5.docx` | 综述 1.2–1.3 为传统「年份+课题组+报道」体例 |
| v4（本地） | 同上目录 `*修订版v4.*` | 网盘原件；复制到仓库后可运行同步脚本 |

## 一键同步（**在本机**执行，配合本地 Agent）

```bash
# 在本地 AI4CHEM 仓库根目录：
cd HTEBO/01_开题与汇报/生成脚本
pip install python-docx   # 若未安装
python3 sync_from_v4.py   # 有 v4 则导出补丁 + 可选重生 v5
```

仅重生 v5（无 v4、或只用脚本模板时）：

```bash
python3 _build_proposal_olefination_v5.py
```

## Git 与网盘

- **进 Git**：开题 `docx/md`、生成脚本、版本说明、本 README
- **留网盘**：文献 PDF、Gaussian 中间文件、大图原稿（与仓库根 `.gitignore` 一致）
