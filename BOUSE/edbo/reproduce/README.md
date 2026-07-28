# 纯复现 EDBO

对齐官方示例，不经过 `src/` 应用封装。

## 论文与官方源

- 论文：Shields et al., *Bayesian Reaction Optimization as A Tool for Chemical Synthesis*
- 上游：`third_party/edbo-master/`（仓库外，AI-Pharmacy 同级）
- 本脚本对照：`../data/deoxyfluorination_example/optimization.ipynb`

## 跑什么

`run_deoxyfluorination.py`：

1. 用官方 DFT 描述符构建 **312,500** 点反应空间  
2. `init_sample(seed=8)`，与 `results/init.csv` 条件比对  
3. 载入官方实测 yield → `run()`，与下一轮官方条件比对  

输出写到 `output/deoxyfluorination/`（提案 CSV、收敛图、`summary.json`）。

## 怎么跑

在 **`BOUSE/edbo/` 目录**：

```bash
conda activate chem_ml
python reproduce/run_deoxyfluorination.py              # 默认：init + 3 轮推荐
python reproduce/run_deoxyfluorination.py --rounds 1  # 更快冒烟
python reproduce/run_deoxyfluorination.py --all-rounds # 跑满官方全部轮次
```

## 判定标准

| 检查项 | 期望 |
|--------|------|
| `domain size` | `312500` |
| `init` vs `results/init.csv` | 条件集合完全一致（seed=8） |
| 后续轮次提案 | 与官方尽量重合；torch/gpytorch 版本不同时可能不完全一致 |

## 其他官方示例（未脚本化，均在 third_party/edbo-master/ 中）

- `examples/mitsunobu_optimization/`
- `examples/DOE/`
- `experiments/edbo_demo_and_simulations.ipynb`
