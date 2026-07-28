# 环境分离（必读）

经典 EDBO 与 EDBO+ **包名都是 `edbo`**，装进同一 conda 环境会互相覆盖。必须分开。

| 用途 | conda 环境 | 启动 | 端口 |
|------|------------|------|------|
| 经典 EDBO 向导 | **`edbo`** | `start_edbo.bat` | 8501 |
| 描述符生成 | **`edbo`**（同上） | `start_descriptors.bat` | 8502 |
| EDBO+ 多目标向导 | **`edbo_plus`** | `start_edbo_plus.bat` | 8503 |

```bash
# 经典栈
conda activate edbo

# EDBO+（另开终端）
conda activate edbo_plus
```

一键 `start_bouse.bat` **只**启动经典 EDBO + 描述符（`edbo`）。EDBO+ 必须单独 `start_edbo_plus.bat`。

界面侧栏会显示当前应使用的环境名；用错环境时启动会报错并停止。
