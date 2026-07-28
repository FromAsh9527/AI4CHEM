# BOUSE 交接契约

`descriptors/` 产出描述符；各 BO 策略（当前为 `edbo/`）消费。双方只通过约定文件交接，不共享 UI。

## 描述符 CSV

| 项 | 约定 |
|----|------|
| 文件名（进工作区时） | `descriptor_<factor_key>.csv` |
| 必需列 | `molecule_id`（字符串，唯一） |
| 特征列 | `molecule_id` 以外全部为数值 |
| 禁止 | 特征列含非数值；空特征表 |
| 编码 | UTF-8 CSV，首行为表头 |

`factor_key` 必须与 EDBO 项目 `config.json` 里对应因子的 `key` 一致（如 `base`、`solvent`）。  
仅 `kind=chemical` 且 `encoding=descriptor` 的因子需要该文件；数值因子用 `values` / linspace，不需要描述符表。

## 分子输入（descriptors 侧）

| 项 | 约定 |
|----|------|
| SMILES 列 | `smiles` / `SMILES` / `Smiles` / `canonical_smiles`（可指定） |
| ID | 有则用 `molecule_id`（或指定列）；无则用 SMILES 字符串作 id |

生成失败的分子可另存 `*_failed.csv`，不进入 EDBO。

## EDBO 工作区

路径：`edbo/workspaces/<project_id>/`

| 文件 | 用途 |
|------|------|
| `config.json` | 因子、目标列、batch、采集函数等 |
| `descriptor_<key>.csv` | `encoding=descriptor` 的化学因子 |
| `levels_<key>.csv` | 可选；`encoding=ohe` 时的水平列表 |
| `history.csv` | 已做实验（因子列 + 目标列，如 `yield`） |
| `last_recommendations.csv` | 最近一轮建议 |

历史表中的化学因子值必须能匹配描述符表的 `molecule_id`（字符串精确匹配；数值因子另有规范化，见 `domain_builder.canonical_level`）。

## 校验

```bash
# 单文件
python scripts/validate_handoff.py path/to/descriptor_solvent.csv

# 对照某个 EDBO 项目里的全部 descriptor_*.csv
python scripts/validate_handoff.py --workspace edbo/workspaces/suzuki_demo
```

或在 descriptors 目录：

```bash
python cli.py validate output/descriptor_solvent.csv
```

## 导入

```bash
python scripts/import_descriptor.py output/xxx.csv --workspace edbo/workspaces/<项目> --factor solvent
```
