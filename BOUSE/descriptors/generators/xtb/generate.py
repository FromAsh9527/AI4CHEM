# -*- coding: utf-8 -*-
"""
独立脚本：SMILES → xTB 半经验量子化学描述符

用法::

    python generators/xtb/generate.py examples/molecules.csv -o output/xtb.csv
    python generators/xtb/generate.py in.csv -o out.csv --gfn 2 --opt --xtb D:\\tools\\xtb.exe

输入可选列 ``charge`` / ``uhf`` 覆盖默认（0 / RDKit 自由基数）。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from generators.xtb.core import compute, find_xtb  # noqa: E402
from io_utils import load_molecule_table, validate_descriptor_frame, write_descriptor_csv  # noqa: E402


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="生成 xTB 描述符（GFN 半经验量子化学）")
    p.add_argument("input", type=Path)
    p.add_argument("-o", "--output", type=Path, required=True)
    p.add_argument("--id-col", default=None)
    p.add_argument("--smiles-col", default=None)
    p.add_argument("--xtb", default=None, help="xtb 可执行文件路径（默认可自动查找）")
    p.add_argument("--gfn", type=int, default=2, choices=[0, 1, 2])
    p.add_argument("--opt", action="store_true", help="先做 GFN-xTB 几何优化（慢但更准）")
    p.add_argument("--timeout", type=int, default=300, help="单分子超时秒数")
    args = p.parse_args(argv)

    exe = find_xtb(args.xtb)
    print(f"xtb: {exe}")

    mols = load_molecule_table(args.input, id_col=args.id_col, smiles_col=args.smiles_col)
    print(f"载入分子: {len(mols)}")
    desc, failed = compute(mols, xtb=exe, gfn=args.gfn, opt=args.opt, timeout=args.timeout)
    if desc.empty:
        raise SystemExit("没有成功生成描述符")
    validate_descriptor_frame(desc)
    write_descriptor_csv(desc, args.output)
    print(f"写出 {args.output}  ({len(desc)} × {desc.shape[1]-1})")
    if not failed.empty:
        fp = args.output.with_name(args.output.stem + "_failed.csv")
        failed.to_csv(fp, index=False)
        print(f"失败 {len(failed)} → {fp}")


if __name__ == "__main__":
    main()
