# -*- coding: utf-8 -*-
"""
独立脚本：清洗已有描述符表

用法::

    python generators/clean/generate.py dft.csv -o output/clean.csv --id-col solvent_SMILES --max-features 20
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from generators.clean.core import clean_descriptor_table  # noqa: E402
from io_utils import validate_descriptor_frame, write_descriptor_csv  # noqa: E402


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="清洗已有描述符表")
    p.add_argument("input", type=Path)
    p.add_argument("-o", "--output", type=Path, required=True)
    p.add_argument("--id-col", default=None)
    p.add_argument("--max-features", type=int, default=None)
    p.add_argument("--drop-na-rows", action="store_true")
    args = p.parse_args(argv)

    cleaned, info = clean_descriptor_table(
        args.input,
        id_col=args.id_col,
        max_features=args.max_features,
        drop_na_rows=args.drop_na_rows,
    )
    if cleaned.empty:
        raise SystemExit("清洗后为空")
    validate_descriptor_frame(cleaned)
    write_descriptor_csv(cleaned, args.output)
    print(f"写出 {args.output}")
    print(json.dumps(info, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
