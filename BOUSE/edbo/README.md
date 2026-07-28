# edbo（BO 策略）

基于 [EDBO](https://github.com/b-shields/edbo) 的反应条件优化：纯复现 + 向导式 Streamlit。

本目录是 `BOUSE/` 下的一个策略包；描述符生成见并列的 `../descriptors/`。  
交接契约见 [`../CONTRACT.md`](../CONTRACT.md)。

## 目录

| 路径 | 说明 |
|------|------|
| `data/` | 上游数据副本（suzuki 全网格、deoxyfluorination 官方示例） |
| `reproduce/` | 论文示例纯复现（Deoxyfluorination） |
| `src/` | 工作区 / 域构建 / 推荐 / 回填 |
| `app.py` | Streamlit 向导入口 |
| `workspaces/` | 项目数据（推荐 `suzuki_demo`；另有 `deoxy_demo`） |
| `scripts/` | 构建测试数据、端到端测试、冒烟 |

## 环境

```bash
conda activate edbo
```

## 推荐测试流程（Suzuki）

在本目录（`BOUSE/edbo/`）下：

```bash
python scripts/build_suzuki_workspace.py --seed-n 0
python scripts/run_suzuki_test_flow.py
streamlit run app.py
```

手测回填：`python scripts/oracle_backfill.py --project suzuki_demo`。  
物料包见 `../manual_test_kit/`。

## Deoxy 示例 / 纯复现

```bash
python scripts/build_deoxy_workspace.py --rounds 0 --max-features 15
python scripts/run_test_flow.py --rebuild
python scripts/smoke_test.py
python reproduce/run_deoxyfluorination.py --rounds 1
```

说明：Deoxy 全空间 312,500 点；BO 时默认随机下采样至 `domain_cap=2500`（保留全部历史点）。  
闭环 oracle 手测请用 **Suzuki**（推荐条件都能查到真实产率）。
