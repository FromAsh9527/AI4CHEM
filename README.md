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

## 说明

- `TransferBO/`（跨反应板迁移 BO 纯计算模拟）目前仅本地保留，未纳入 Git 跟踪。
- 大型中间文件（Gaussian 输出、文献 PDF、模型权重等）已被 `.gitignore` 排除，保留在本地/网盘。
