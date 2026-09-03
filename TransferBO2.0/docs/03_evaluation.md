# 3. 评价指标与 Benchmark

## 指标

| 指标 | 定义 | 用途 |
|---|---|---|
| Best-so-far | \(y_{\max}(t)=\max_{i\le t} y_i\) | 逐步最优轨迹 |
| Optimisation AUC | \(\sum_{t=1}^{B} y_{\max}(t)\) | 前期效率 |
| Simple regret | \(y^\star - y_{\max}(t)\) | 距全局最优差距 |
| Top-k hit rate | 前 \(T\) 次是否命中 Top \(p\%\) | 实用命中率 |
| Threshold attainment | \(T_\tau=\min\{t:y_{\max}(t)\ge\tau\}\) | 达标实验数 |
| Negative transfer rate | \(P(\mathrm{AUC}_{\mathrm{tr}}<\mathrm{AUC}_{\mathrm{cold}})\) | 负迁移风险 |

实现：`src/transferbo2/metrics/evaluate.py`

## Benchmark 协议

### LOSO — Leave-one-substrate-out

隐藏目标底物大部分数据；其余底物为历史；目标仅留 \(n_0\) 初始化点；离线 oracle 回放。

### LOPO — Leave-one-plate-out

训练用其他板；测试新板泛化与校正能力。

### Dual — 新底物 + 新板

最贴近真实场景；允许少量 anchor + 少量目标初始化。

实现：`src/transferbo2/benchmarks/`

## 推荐预算

- 初始化 \(n_0 \in \{3,5,8\}\)
- 总预算 \(B \in \{10,20,30,50\}\)
- 每设定 ≥20 随机种子（论文主结果建议 50–100）
