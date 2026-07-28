# -*- coding: utf-8 -*-
"""
统一 CLI（各类型也有独立脚本 generators/*/generate.py）

用法::

    python cli.py list
    python cli.py from-smiles examples/molecules.csv --backend rdkit_2d -o output/x.csv
    python cli.py from-smiles examples/molecules.csv --backend morgan --n-bits 64 -o output/fp.csv
    python cli.py clean path/to/dft.csv --id-col solvent_SMILES -o output/c.csv
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from generators import GENERATORS  # noqa: E402
from generators.clean.core import clean_descriptor_table  # noqa: E402
from generators.maccs.core import compute as compute_maccs  # noqa: E402
from generators.morgan.core import compute as compute_morgan  # noqa: E402
from generators.rdkit_2d.core import compute as compute_rdkit  # noqa: E402
from io_utils import (  # noqa: E402
    load_molecule_table,
    read_table,
    validate_descriptor_frame,
    write_descriptor_csv,
)


def cmd_list(_: argparse.Namespace) -> None:
    print("描述符生成器（各在独立目录）:")
    for k, v in GENERATORS.items():
        print(f"  - {k}: {v}  → generators/{k}/generate.py")


def cmd_from_smiles(args: argparse.Namespace) -> None:
    mols = load_molecule_table(args.input, id_col=args.id_col, smiles_col=args.smiles_col)
    print(f"载入分子: {len(mols)}")
    if args.backend == "rdkit_2d":
        desc, failed = compute_rdkit(mols)
    elif args.backend == "morgan":
        desc, failed = compute_morgan(
            mols, radius=args.radius, n_bits=args.n_bits, use_counts=args.use_counts
        )
    elif args.backend == "maccs":
        desc, failed = compute_maccs(mols)
    elif args.backend == "mordred":
        from generators.mordred.core import compute as compute_mordred

        desc, failed = compute_mordred(mols, ignore_3D=not bool(args.with_3d))
    else:
        raise SystemExit(f"未知 backend: {args.backend}")
    if desc.empty:
        raise SystemExit("没有成功生成描述符")
    validate_descriptor_frame(desc)
    out = Path(args.output) if args.output else ROOT / "output" / f"{Path(args.input).stem}_{args.backend}.csv"
    write_descriptor_csv(desc, out)
    print(f"写出: {out}  ({len(desc)} × {desc.shape[1]-1})")
    if not failed.empty:
        fp = out.with_name(out.stem + "_failed.csv")
        failed.to_csv(fp, index=False)
        print(f"失败 {len(failed)} → {fp}")


def cmd_clean(args: argparse.Namespace) -> None:
    cleaned, info = clean_descriptor_table(
        args.input,
        id_col=args.id_col,
        max_features=args.max_features,
        drop_na_rows=args.drop_na_rows,
    )
    if cleaned.empty:
        raise SystemExit("清洗后为空")
    validate_descriptor_frame(cleaned)
    out = Path(args.output) if args.output else ROOT / "output" / f"{Path(args.input).stem}_clean.csv"
    write_descriptor_csv(cleaned, out)
    print(f"写出: {out}")
    print(json.dumps(info, ensure_ascii=False, indent=2))


def cmd_validate(args: argparse.Namespace) -> None:
    df = read_table(args.input)
    validate_descriptor_frame(df)
    n_feat = df.shape[1] - 1
    print(f"校验通过: {args.input}  ({len(df)} 行 × {n_feat} 特征)")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="BOUSE 描述符生成")
    sub = p.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="列出生成器")
    p_list.set_defaults(func=cmd_list)

    p_smi = sub.add_parser("from-smiles", help="SMILES → 描述符")
    p_smi.add_argument("input", type=Path)
    p_smi.add_argument("-o", "--output", type=Path, default=None)
    p_smi.add_argument(
        "--backend",
        choices=["rdkit_2d", "morgan", "maccs", "mordred"],
        default="rdkit_2d",
    )
    p_smi.add_argument("--id-col", default=None)
    p_smi.add_argument("--smiles-col", default=None)
    p_smi.add_argument("--radius", type=int, default=2)
    p_smi.add_argument("--n-bits", type=int, default=128)
    p_smi.add_argument("--use-counts", action="store_true")
    p_smi.add_argument(
        "--with-3d",
        action="store_true",
        help="mordred: 包含需 3D 的描述符（默认只算 2D）",
    )
    p_smi.set_defaults(func=cmd_from_smiles)

    p_clean = sub.add_parser("clean", help="清洗已有表")
    p_clean.add_argument("input", type=Path)
    p_clean.add_argument("-o", "--output", type=Path, default=None)
    p_clean.add_argument("--id-col", default=None)
    p_clean.add_argument("--max-features", type=int, default=None)
    p_clean.add_argument("--drop-na-rows", action="store_true")
    p_clean.set_defaults(func=cmd_clean)

    p_val = sub.add_parser("validate", help="校验描述符 CSV 是否符合交接契约")
    p_val.add_argument("input", type=Path)
    p_val.set_defaults(func=cmd_validate)
    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
