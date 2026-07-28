Suzuki 闭环测试工作区
====================
来源: edbo-master/experiments/data/suzuki
搜索域: 4×3×11×7×4 = 3696（与 oracle 一一对应）
历史: 0 条
描述符: top-15 / chem

用法:
  1. streamlit run app.py → 打开项目 suzuki_demo
  2. 步骤3 推荐（无历史用无模型；有历史用 BO）
  3. 查表回填（不用做实验）:
       python scripts/oracle_backfill.py --project suzuki_demo
     会根据 last_recommendations.csv 从 oracle.csv 填 yield，并写入历史

或在物料包中手动操作，见 ../../manual_test_kit/README.md
