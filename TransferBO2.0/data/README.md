# 实验研究数据库说明

## 位置

| 路径 | 内容 |
|---|---|
| `db/schema.sql` | SQLite DDL（反应/底物/板/条件/实验/描述符/文献） |
| `db/transferbo2.db` | 本地库（gitignore；由脚本生成） |
| `processed/` | 清洗长表 CSV |
| `raw/` | 原始下载 |
| `literature/` | 文献书目与笔记 |

## 初始化

```bash
python scripts/init_db.py --demo
```

## 导入自有/公开数据

长表至少含：`reaction_id, substrate_id, plate_id, condition_id, yield`

```bash
python scripts/import_csv_to_db.py --csv data/processed/your_long.csv --replace
```

## 与 TransferBO 数据的桥接

可将 `../TransferBO/data/processed/` 中的表扩展为含 `substrate_id` 的长表后导入。
CHAOS 四板数据天然有 `plate_id`，适合 LOPO；底物维度需另接 BH/Suzuki 等反应库。
