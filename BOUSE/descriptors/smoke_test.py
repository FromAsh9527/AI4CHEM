# -*- coding: utf-8 -*-
"""冒烟：独立脚本 + 统一 CLI。"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EX = ROOT / "examples" / "molecules.csv"
OUT = ROOT / "output"
DFT = (
    ROOT.parent
    / "edbo"
    / "edbo-master"
    / "examples"
    / "deoxyfluorination_optimization"
    / "descriptors"
    / "solvent_dft.csv"
)


def run(cmd: list[str]) -> None:
    print(">", " ".join(cmd))
    subprocess.check_call(cmd, cwd=str(ROOT))


def main() -> None:
    py = sys.executable
    OUT.mkdir(exist_ok=True)
    run([py, "cli.py", "list"])
    run([py, "generators/rdkit_2d/generate.py", str(EX), "-o", str(OUT / "smoke_rdkit.csv")])
    run(
        [
            py,
            "generators/morgan/generate.py",
            str(EX),
            "-o",
            str(OUT / "smoke_morgan.csv"),
            "--n-bits",
            "32",
        ]
    )
    run([py, "generators/maccs/generate.py", str(EX), "-o", str(OUT / "smoke_maccs.csv")])
    run([py, "cli.py", "validate", str(OUT / "smoke_rdkit.csv")])
    # mordred 可选（NumPy 2 下旧包可能坏；生成器内有兼容补丁）
    try:
        from generators.mordred.core import _require_mordred

        _require_mordred()
        run(
            [
                py,
                "generators/mordred/generate.py",
                str(EX),
                "-o",
                str(OUT / "smoke_mordred.csv"),
                "--ignore-3d",
            ]
        )
    except Exception as e:
        print(f"skip mordred ({e})")
    if DFT.is_file():
        run(
            [
                py,
                "generators/clean/generate.py",
                str(DFT),
                "--id-col",
                "solvent_SMILES",
                "--max-features",
                "15",
                "-o",
                str(OUT / "smoke_clean.csv"),
            ]
        )
    # import app module lightly
    run([py, "-c", "import app; print('app import OK')"])
    print("SMOKE OK")


if __name__ == "__main__":
    main()
