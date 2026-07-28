# -*- coding: utf-8 -*-
"""将描述符 CSV 导入 EDBO 工作区（调用 handoff）。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from handoff import import_descriptor  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description="导入描述符到 EDBO 工作区")
    p.add_argument("src", type=Path)
    p.add_argument("--workspace", type=Path, required=True)
    p.add_argument("--factor", required=True)
    p.add_argument("--force", action="store_true")
    p.add_argument("--skip-validate", action="store_true")
    args = p.parse_args()
    try:
        dest = import_descriptor(
            args.src,
            args.workspace,
            args.factor,
            force=args.force,
            skip_validate=args.skip_validate,
        )
    except Exception as e:
        print(f"失败: {e}", file=sys.stderr)
        raise SystemExit(1)
    print(f"已导入: {dest}")


if __name__ == "__main__":
    main()
