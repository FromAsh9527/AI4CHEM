# HTEBO 本地 ↔ Git 同步说明

## 云 Agent 环境限制

Cursor 云虚拟机**无法直接访问**百度网盘上的 `AI4CHEM/HTEBO` 本地副本。同步需你在本机完成「复制 + pull/push」或运行下方脚本。

## 推荐流程

### A. 把本地 v4 合并进仓库 v5

1. 将本地文件复制到仓库：
   ```
   HTEBO/01_开题与汇报/开题报告_新_无导向Pd烯基化区域选择性预测_修订版v4.md
   ```
   （有 md 优先；仅有 docx 也可）

2. 在仓库根目录：
   ```bash
   git pull origin cursor/safe-transfer-s5-plan
   cd HTEBO/01_开题与汇报/生成脚本
   python3 sync_from_v4.py
   ```

3. 若生成 `_v4_chapters_2_to_5_patch.md`，对照 v5 第 2–5 章是否需要手工合并进 `_build_proposal_olefination_v5.py`。

4. 提交并推送：
   ```bash
   git add HTEBO/
   git commit -m "HTEBO: 同步本地 v4 补丁并更新 v5"
   git push origin <你的分支>
   ```

### B. 仅使用仓库 v5（无本地 v4）

```bash
cd HTEBO/01_开题与汇报/生成脚本
python3 _build_proposal_olefination_v5.py
```

### C. 从仓库拉回本地网盘

```bash
cd <你的 AI4CHEM 克隆目录>
git pull
# 将 HTEBO/01_开题与汇报/*v5* 复制回网盘对应目录
```

## 版本对照

| 项目 | v4（本地） | v5（仓库） |
|------|------------|------------|
| 综述体例 | 条目式为主 | 1.2–1.3 传统课题组报道句式 |
| 参考文献 | 34 条 [1]–[34] | 目标对齐 34 条（生成脚本内校验） |
| 平台描述 | 2.1.6 等 | 2.1.6 + 3.1 + 工作计划 |

## 待你本地填写

- 封面姓名、学号、导师
- 图 1–3、图 2（ML）ChemDraw 终稿 → `06_图表与展示/figures/`
