# Step1 收口清单（2026-08-22）

本文件是 **P0 / Step1 收尾** 核对戳。不改 `FROZEN_CLAIMS.md` 2026-08-20 数字。  
**Step1+Step2 合并锁档：** `docs/15_step1_step2_lock.md`（校验已跑通）。

## 锁死（可对外引用）

| 项 | 内容 |
|---|---|
| 胺化 Q1 / Q2 | cold≫random（15/15）；主增益 = 多源 topk init k=5 |
| Suzuki Q1 | 失败（cold ≯ random，4/12）= **基线 BO 备注** |
| Suzuki topk | vs cold +149.9 [+38.8, +269.8] → **历史策略证据成立**；vs random 弱正 |
| 跨库 | 禁止胺化整包部署叙事；允许分库报告效应量 |
| 条件表示默认 | **OHE**；DFT / 条件 Morgan 不升 |
| 底物近邻 | 机制工作用 **morgan_r2 + Tanimoto**（不回写 hashed 下 Q3） |

## 文档已对齐

- `FROZEN_CLAIMS.md` 附录
- `docs/00` `09` `10` `11` `12` `14` `15`、`README.md`
- `results/ALL_RESULTS_ANALYSIS.md`
- 校验：`results/step1_step2_validation/report.md`

## 明确不做（本收口）

- 重跑 LOSO / 换表示 / DFT 全量 / pair 全量改主锁
- 用 Q1 否决 Suzuki topk
- 用 Step2 回写 Step1 数字
