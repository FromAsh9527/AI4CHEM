# edbo_plus（多目标 BO 策略）

基于 [EDBO+](https://github.com/doyle-lab-ucla/edboplus)（Doyle Lab）的多目标贝叶斯优化。

与经典 EDBO（`../edbo/`）**必须使用独立 conda 环境**（包名都是 `edbo`）。

## 目录

| 路径 | 说明 |
|------|------|
| `app.py` | Streamlit 向导（项目→域→推荐→回填） |
| `src/` | 工作区 / 调用 `EDBOplus` / 回填 |
| `edboplus-master/` | 上游源码（editable 安装） |
| `workspaces/` | 项目数据（每项目一个 `reaction.csv`） |
| `scripts/` | 冒烟测试 |

## 环境

```bash
conda activate edbo_plus
```

关键依赖：`torch 1.10.x`、`botorch 0.5`、`gpytorch 1.5`、`numpy 1.21`、`pandas 1.3`、`idaes-pse`、**`streamlit==1.22.0`**（勿装新版 Streamlit，会把 numpy 升到 2.x）。

> 不要用 conda 装新版 RDKit 把 numpy 升到 2.x。

## 启动界面

双击仓库根目录 `start_edbo_plus.bat`，或：

```bash
conda activate edbo_plus
cd BOUSE/edbo_plus
streamlit run app.py --server.port 8503
```

打开 http://localhost:8503

### 向导逻辑（对齐官方 API）

1. **项目与目标**：多目标名 + `max`/`min`；batch / seed / 初采样 / NoisyEHVI|EHVI  
2. **定义搜索域**：因子水平 → `generate_reaction_scope`，或上传已有 CSV  
3. **推荐**：调用 `EDBOplus().run(...)`；无观测→初采样；有观测→多目标 BO  
4. **回填**：把 `priority=1` 行的 `PENDING` 写成数值，再回到步骤 3

数据单文件：`workspaces/<项目>/reaction.csv`（官方格式，含 `priority`）。

## 验证

```bash
python scripts/smoke_test.py
python scripts/ui_smoke_test.py
```

## 与 BOUSE 其他模块的关系

- 经典 EDBO UI：`../edbo/`（端口 8501，环境 `edbo`）
- 描述符 UI：`../descriptors/`（端口 8502）
- EDBO+ UI：本目录（端口 8503，环境 `edbo_plus`）
- EDBO+ 原生用 **CSV 因子列 + OHE**；描述符列可直接放进上传的 scope CSV（步骤 2）
- 官方 WebApp：https://edboplus.org
