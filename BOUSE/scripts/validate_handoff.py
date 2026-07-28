# -*- coding: utf-8 -*-
"""校验描述符 CSV / EDBO 工作区（调用 handoff）。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from handoff import check_descriptor_file, check_workspace_descriptors  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description="校验 BOUSE 描述符交接契约")
    p.add_argument("path", type=Path, nargs="?", help="单个描述符 CSV")
    p.add_argument("--workspace", type=Path, default=None, help="EDBO 工作区目录")
    args = p.parse_args()
    if args.workspace is None and args.path is None:
        p.error("请提供 CSV 路径或 --workspace")

    all_errors: list[str] = []
    if args.path is not None:
        all_errors.extend(check_descriptor_file(args.path))
    if args.workspace is not None:
        ws = args.workspace if args.workspace.is_absolute() else (Path.cwd() / args.workspace).resolve()
        all_errors.extend(check_workspace_descriptors(ws))

    if all_errors:
        print("校验失败:")
        for e in all_errors:
            print(f"  - {e}")
        raise SystemExit(1)
    print("校验通过")
    if args.path:
        print(f"  file: {args.path}")
    if args.workspace:
        print(f"  workspace: {args.workspace}")


if __name__ == "__main__":
    main()
