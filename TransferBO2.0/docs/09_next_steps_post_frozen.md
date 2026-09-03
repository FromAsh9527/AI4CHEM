# 执行单

| 文档 | 角色 |
|---|---|
| `docs/15_step1_step2_lock.md` | **Step1+Step2 锁档（已生效）** |
| `docs/16_work_report_step1_step2.md` | **工作汇报（详细）** |
| `results/step1_step2_validation/report.md` | 校验报告（须全 PASS） |
| `FROZEN_CLAIMS.md` | Step1 数字锁 |
| `docs/14_strategy_draft.md` | Step3 策略草稿 |
| `docs/17_step3_experiment_plan.md` | **Step3 实验方案（P0–P5，预注册）** |
| `docs/12_plan_after_step1.md` | 规划全文 |

## 已完成

- P0 Step1 收尾  
- P1 M1/M2 机制  
- P2 策略草稿  
- **锁档 + 机器校验（24/24 PASS，2026-08-22）**
- **P0 shared-init 审计（420/420 jobs，2026-08-22）** → `results/suzuki_p0_shared_init/`
- **P1+P2 离线清单稳定性（2026-08-22）** → `results/p1p2_source_robustness/`

## 下一步（Step3 验证）

| 优先级 | 工作 | 状态 |
|---|---|---|
| ~~P0~~ | Suzuki shared-init 审计 | **完成** |
| ~~P1+P2 离线~~ | 源规模 + Jaccard/init 曲线 | **完成** |
| P1 BO（可选） | subset LOSO 胺化 675 + Suzuki 360 | 脚本就绪 |
| P3/P4 | 湿实验或外部 holdout | 方案 |
| P5 | `recommend_init` CLI | 方案 |

## 后置（先不做）

pair 全量、板校正、contextual GP、sim_weighted 调参、MTGP 主线。

## 再生校验

```bash
python scripts/validate_step1_step2.py
# 可选单独再生：
python scripts/analyze_step1_effects.py
python scripts/analyze_step2_m1_init_vs_bo.py
python scripts/analyze_step2_m2_pool_vs_nearest.py
```
