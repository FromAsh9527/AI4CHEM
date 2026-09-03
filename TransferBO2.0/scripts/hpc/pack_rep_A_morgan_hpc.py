#!/usr/bin/env python
"""Pack Step1b Phase A Morgan full LOSO for both libraries (HPC).

Includes DBs with morgan_r2 already written (runtime does NOT need RDKit).

  python scripts/hpc/pack_rep_A_morgan_hpc.py
"""

from __future__ import annotations

import argparse
import io
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

INCLUDE = [
    "configs/amination_rep_A_morgan_sub_hpc.yaml",
    "configs/amination_rep_A_morgan_sub_full.yaml",
    "configs/amination_rep_A_morgan_sub_pilot.yaml",
    "configs/suzuki_rep_A_morgan_sub_hpc.yaml",
    "configs/suzuki_rep_A_morgan_sub_full.yaml",
    "configs/suzuki_rep_A_morgan_sub_pilot.yaml",
    "src",
    "scripts/run_loso.py",
    "scripts/analyze_step1b_rep_A.py",
    "scripts/analyze_step1_effects.py",
    "scripts/summarize_results.py",
    "scripts/build_morgan_descriptors.py",
    "scripts/preflight_step1b_rep.py",
    "scripts/hpc",
    "docs/11_step1b_representation.md",
    "docs/00_research_framework.md",
    "pyproject.toml",
    "requirements.txt",
    "data/db/schema.sql",
    "data/db/transferbo2.db",
    "data/db/transferbo2_suzuki.db",
]

SKIP_DIR_NAMES = {"__pycache__", ".git", "dsub_jobs"}
SKIP_SUFFIXES = {".pyc", ".pyo"}
MTIME = int(time.time()) - 120


def _should_skip(path: Path) -> bool:
    if any(part in SKIP_DIR_NAMES for part in path.parts):
        return True
    if path.suffix in SKIP_SUFFIXES:
        return True
    return False


def _add_file(tar: tarfile.TarFile, path: Path, arcname: str) -> None:
    data = path.read_bytes()
    if path.suffix == ".sh" or path.name.endswith(".sh"):
        data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    info = tarfile.TarInfo(name=arcname.replace("\\", "/"))
    info.size = len(data)
    info.mtime = MTIME
    info.mode = 0o755 if path.suffix == ".sh" else 0o644
    tar.addfile(info, io.BytesIO(data))


def add_path(tar: tarfile.TarFile, rel: str) -> None:
    path = ROOT / rel
    if not path.exists():
        raise FileNotFoundError(path)
    if path.is_file():
        if not _should_skip(path):
            _add_file(tar, path, rel)
        return
    for child in sorted(path.rglob("*")):
        if not child.is_file() or _should_skip(child):
            continue
        arc = child.relative_to(ROOT).as_posix()
        _add_file(tar, child, arc)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / "transferbo2_rep_A_morgan_hpc.tgz")
    args = ap.parse_args()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    if out.exists():
        out.unlink()
    with tarfile.open(out, "w:gz") as tar:
        for rel in INCLUDE:
            add_path(tar, rel)
    mb = out.stat().st_size / (1024 * 1024)
    with tarfile.open(out, "r:gz") as tar:
        for name in (
            "scripts/hpc/submit_amination_rep_A_dsub.sh",
            "scripts/hpc/submit_suzuki_rep_A_dsub.sh",
        ):
            f = tar.extractfile(name)
            assert f is not None
            raw = f.read()
            if b"\r" in raw:
                raise SystemExit(f"CRLF still present in {name}")
        names = tar.getnames()
        if any("__pycache__" in n for n in names):
            raise SystemExit("pycache leaked into tarball")
        for need in (
            "data/db/transferbo2.db",
            "data/db/transferbo2_suzuki.db",
            "configs/amination_rep_A_morgan_sub_hpc.yaml",
            "configs/suzuki_rep_A_morgan_sub_hpc.yaml",
        ):
            if need not in names:
                raise SystemExit(f"missing {need}")
    print(f"[OK] {out}  ({mb:.1f} MB)")
    print("Upload via file manager, then on HPC see scripts/hpc/START_REP_A_MORGAN.txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
