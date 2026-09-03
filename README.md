# AI4CHEM

化学反应 AI 工作区，主体为 **BOUSE** 贝叶斯优化平台。

## BOUSE — 化学反应条件贝叶斯优化

- `edbo/`：经典单目标 EDBO（如产率最大化），Streamlit 界面，支持全网格 oracle 回填闭环模拟
- `edbo_plus/`：多目标 EDBO+（产率/选择性/成本等同时优化），Streamlit 界面，支持 Pareto 前沿与超体积（HV）指标
- `descriptors/`：分子描述符生成工具（Morgan / MACCS / RDKit 2D / Mordred / 清洗）
- `start_*.bat`：一键启动各模块

### 快速启动

```powershell
cd BOUSE
.\start_edbo.bat          # 经典单目标 EDBO
.\start_edbo_plus.bat     # 多目标 EDBO+
.\start_descriptors.bat   # 描述符生成
```

## TransferBO — 跨反应板迁移贝叶斯优化

- `TransferBO/`：跨反应板 Transfer / Warm-start BO 纯计算回顾性模拟（代码、配置、数据表已入库）
- 文稿（`docs/` 下的 docx / md / pptx）可入库；运行产物 `results/`、`exports/` 与文献 **PDF** 不进 Git

## HTEBO — 开题与实验方案

- `HTEBO/`：无导向 Pd 烯基化开题报告、投料表、配体清单（docx / md / csv）
- `HTEBO/02_文献/` 仅占位；**PDF 不上传**

## 说明

- 文献 PDF、Gaussian 中间文件、模型权重等已被 `.gitignore` 排除，保留在本地/网盘。
