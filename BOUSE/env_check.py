# -*- coding: utf-8 -*-
"""运行时校验：经典 EDBO / EDBO+ 必须使用各自 conda 环境。"""
from __future__ import annotations

import sys
from pathlib import Path


def conda_env_name(python_exe: str | None = None) -> str | None:
    """从 python 路径推断 conda 环境名，例如 .../envs/edbo/python.exe → edbo。"""
    p = Path(python_exe or sys.executable).resolve()
    parts = [x.lower() for x in p.parts]
    if "envs" in parts:
        i = parts.index("envs")
        if i + 1 < len(parts):
            return p.parts[i + 1]
    return None


def check_classic_edbo(*, require_bro: bool = True) -> tuple[bool, str]:
    """经典 EDBO UI：期望 conda env `edbo`。描述符界面可设 require_bro=False。"""
    env = conda_env_name()
    exe = sys.executable
    lines = [
        f"Python: {exe}",
        f"推断 conda 环境: {env or '(未知)'}",
    ]
    if env and env.lower() == "edbo_plus":
        lines.append(
            "错误：当前是 edbo_plus 环境。经典 EDBO / 描述符请用：conda activate edbo"
        )
        return False, "\n".join(lines)
    if env and env.lower() != "edbo":
        lines.append(
            f"警告：期望环境名 edbo，当前为 {env}。两套 EDBO 包名相同，混用会互相覆盖。"
        )

    if require_bro:
        try:
            import edbo  # noqa: F401
            from edbo.bro import BO  # noqa: F401
        except Exception as e:
            lines.append(f"错误：无法导入经典 EDBO（edbo.bro）：{e}")
            lines.append("请：conda activate edbo，并确保已安装经典 EDBO（非 EDBO+）。")
            return False, "\n".join(lines)

        try:
            import edbo.plus  # noqa: F401

            lines.append(
                "警告：当前环境同时存在 edbo.plus（EDBO+）。"
                "经典 EDBO 与 EDBO+ 不应共环境；请分开 edbo / edbo_plus。"
            )
        except Exception:
            pass
        lines.append("校验通过：经典 EDBO（conda: edbo）")
    else:
        lines.append("校验通过：描述符界面（conda: edbo）")
    return True, "\n".join(lines)


def check_edbo_plus() -> tuple[bool, str]:
    """EDBO+ UI：期望 conda env `edbo_plus`，且能 import edbo.plus。"""
    env = conda_env_name()
    exe = sys.executable
    lines = [
        f"Python: {exe}",
        f"推断 conda 环境: {env or '(未知)'}",
    ]
    if env and env.lower() == "edbo":
        lines.append(
            "错误：当前是经典 edbo 环境。EDBO+ 请用：conda activate edbo_plus"
        )
        return False, "\n".join(lines)
    if env and env.lower() != "edbo_plus":
        lines.append(
            f"警告：期望环境名 edbo_plus，当前为 {env}。两套包名都是 edbo，切勿混装。"
        )

    try:
        from edbo.plus.optimizer_botorch import EDBOplus  # noqa: F401
    except Exception as e:
        lines.append(f"错误：无法导入 EDBO+（edbo.plus）：{e}")
        lines.append(
            "请：conda activate edbo_plus，并 pip install -e <AI-Pharmacy>/third_party/edboplus-master --no-deps"
        )
        return False, "\n".join(lines)

    # 经典 bro 不应作为主入口；若存在也警告
    try:
        from edbo.bro import BO  # noqa: F401

        lines.append(
            "警告：当前环境同时存在经典 edbo.bro。"
            "请确认未把两套源码装进同一环境。"
        )
    except Exception:
        pass

    lines.append("校验通过：EDBO+（conda: edbo_plus）")
    return True, "\n".join(lines)
