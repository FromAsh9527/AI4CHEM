# 2. 方法矩阵与代码映射

| 方法 | 历史数据 | 底物差异 | 板效应 | 策略 ID | 模块 |
|---|---:|---:|---:|---|---|
| Random search | 否 | 否 | 否 | `random` | `strategies/random_search.py` |
| Cold-start BO | 否 | 否 | 否 | `cold_start` | `strategies/cold_start.py` |
| Global Top-k warm start | 部分 | 间接 | 否 | `topk_warm` | `strategies/topk_warm.py` |
| Nearest-substrate Top-k | 部分 | 是 | 否 | `nearest_topk_warm` | `strategies/nearest_topk_warm.py` |
| Pooled surrogate + BO | 是 | 部分 | 通常否 | `pooled` | `strategies/pooled.py` |
| Similarity-weighted transfer | 是 | 是 | 可选 | `sim_weighted` | `strategies/sim_weighted.py` |
| Contextual GP BO | 是 | 是 | 可扩展 | `contextual` | `strategies/contextual.py` |
| Plate-aware contextual GP | 是 | 是 | 是 | `plate_aware` | `strategies/plate_aware.py` |
| Safe transfer gate | 是 | 是 | 是 | `safe_gate` | `strategies/safe_gate.py` |

## 推荐落地模型（简版）

\[
y = f_{\mathrm{chem}}(x,\phi(s)) + b_p + \epsilon
\]

完整版：

\[
k_{\mathrm{total}} = k_{\mathrm{cond}}\,k_{\mathrm{sub}} + k_{\mathrm{plate}} + k_{\mathrm{well}}
\]

## 权重与门控

\[
w_i = w_{\mathrm{sub}}(s_i,s_t)\,w_{\mathrm{plate}}(p_i)\,w_{\mathrm{quality}}(i)
\]

门控：用目标底物少量初始化点，对源底物计算 Spearman \(\rho_h\) 或 MAE \(E_h\)，仅当 \(\rho_h>\tau_\rho\)（或 \(E_h<\tau_E\)）时允许高权重迁移。
