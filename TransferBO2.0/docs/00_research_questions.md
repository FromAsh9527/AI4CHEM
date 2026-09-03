# 0. 研究问题与可检验假设

## 核心问题

在同一反应模板下，对新底物 \(s_t\) 做条件优化时，如何利用历史底物 \(s_h\) 在其他实验板上积累的数据：

\[
\mathcal{D}_{\mathrm{hist}}=\{(s_h,x_i,y_i,\mathrm{plate}_i)\}
\]

同时处理 **substrate shift** 与 **plate/batch shift**：

\[
y = f(s,x) + b_{\mathrm{plate}} + \epsilon
\]

## 四个层次

1. 历史数据能否帮助新底物优化？（cold vs warm vs transfer vs meta）
2. 哪些历史底物最有价值？（结构 / 物化 / 响应相似性）
3. 板间效应造成多大迁移风险？
4. 何时负迁移？如何识别与门控？

## 假设

### H1 — 前期效率

同一反应库中，历史底物数据可显著改善新底物 BO 的前期效率（关注前 5/10/20 次实验的 best-so-far，而非只看最终最优）。

### H2 — 相似度—收益相关

迁移增益 \(G=\mathrm{AUC}_{\mathrm{transfer}}-\mathrm{AUC}_{\mathrm{cold}}\) 与 \(\mathrm{Sim}(s_h,s_t)\) 正相关；比较 ECFP / 物化描述符 / 少量目标实验得到的响应相关性。

### H3 — 板效应建模降低负迁移

显式 plate 校正（均值归一化、anchor、分层模型）相对无校正迁移，可降低 \(P(G<0)\)。

### H4 — 选择性迁移优于全量等权

nearest-neighbor / similarity-weighted / dynamically gated 优于 all-source pooled。

## 主对照

```text
Cold-start BO
  vs Historical Top-k warm-start
  vs Substrate-aware transfer
  vs Plate-aware safe transfer
```
