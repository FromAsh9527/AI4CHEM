# -*- coding: utf-8 -*-
"""
独立脚本：SMILES → Morgan 指纹

用法::

    python generators/morgan/generate.py examples/molecules.csv -o output/morgan.csv --n-bits 128
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from generators.morgan.core import compute  # noqa: E402
from io_utils import load_molecule_table, validate_descriptor_frame, write_descriptor_csv  # noqa: E402


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="生成 Morgan 指纹描述符")
    p.add_argument("input", type=Path)
    p.add_argument("-o", "--output", type=Path, required=True)
    p.add_argument("--id-col", default=None)
    p.add_argument("--smiles-col", default=None)
    p.add_argument("--radius", type=int, default=2)
    p.add_argument("--n-bits", type=int, default=128)
    p.add_argument("--use-counts", action="store_true")
    args = p.parse_args(argv)

    mols = load_molecule_table(args.input, id_col=args.id_col, smiles_col=args.smiles_col)
    desc, failed = compute(
        mols, radius=args.radius, n_bits=args.n_bits, use_counts=args.use_counts
    )
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
