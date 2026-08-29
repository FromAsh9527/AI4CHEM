# 开题报告 docx 版本说明

## 当前版本

| 文件 | 说明 |
|---|---|
| `开题报告_新_无导向Pd烯基化区域选择性预测_修订版v5.docx` | **当前有效版**：综述 1.1–1.3 采用传统「年份 + 课题组 + 报道」表述 |
| `开题报告_新_无导向Pd烯基化区域选择性预测_修订版v5.md` | 与 docx 同步的 Markdown 源 |
| `生成脚本/_build_proposal_olefination_v5.py` | 一键重生 docx + md |

## v5 相对 v4 的主要变化

- **1.2 化学进展**：按时间线改写为「1967 年 Moritani 与 Fujiwara[1] 首次报道…」「2010 年 Yu 课题组[6] 在 Science 上报道…」「2022 年 Lete 课题组[12] 发表综述…」等传统综述句式。
- **1.3 ML/划界**：「2017 年 Jensen 课题组提出 RegioSQM…」「2023 年 Ackermann 与 Li 课题组报道电催化烯基化并建立 ML 模型…」等，保留 SoBo / MT-GNN 划界与自动化平台段落。
- 参考文献按正文首次出现顺序编号 [1]–[25]（v4 为 34 条，合并精简；若需与 v4 完全对齐可再补条目）。

## 重新生成

```bash
cd HTEBO/01_开题与汇报/生成脚本
python3 _build_proposal_olefination_v5.py
```

## 待填项

- 封面姓名、学号、导师
- 图 1–3、图 2（ML）终稿 ChemDraw 重绘
