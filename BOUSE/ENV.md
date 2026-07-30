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

## xTB（半经验量化描述符）

描述符 `xtb` 后端需要 xtb 可执行文件（Windows 官方版已置于仓库外 `third_party/xtb/xtb-6.7.1/bin/xtb.exe`，与 `edbo-master` 等并列）。查找顺序：`--xtb` 参数 → 环境变量 `XTB_EXE` → PATH → `third_party/**/xtb.exe`。

- 换新机器：从 [grimme-lab/xtb releases](https://github.com/grimme-lab/xtb/releases) 下载 `xtb-*-windows-x86_64.zip` 解压到 `third_party/xtb/`，无需安装。
- 计算在 `edbo` 环境内由 Python 调起，无需把 xtb 装进 conda。
