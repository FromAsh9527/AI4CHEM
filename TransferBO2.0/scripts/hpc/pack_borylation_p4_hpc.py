#!/usr/bin/env python
"""Pack borylation P4 holdout LOSO tarball for HPC (Windows-friendly).

  python scripts/hpc/pack_borylation_p4_hpc.py
"""

from __future__ import annotations

import argparse
import io
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

INCLUDE = [
    "configs/borylation_p4_holdout_hpc.yaml",
    "configs/borylation_p4_pilot.yaml",
    "src",
    "scripts/run_loso.py",
    "scripts/ingest_borylation.py",
    "scripts/hpc",
    "docs/18_p4_hitea_holdout.md",
    "pyproject.toml",
    "requirements.txt",
    "data/db/schema.sql",
    "data/db/transferbo2_borylation.db",
    "data/processed/borylation_long.csv",
]

SKIP_DIR_NAMES = {"__pycache__", ".git", "dsub_jobs"}
SKIP_SUFFIXES = {".pyc", ".pyo"}
MTIME = int(time.time()) - 120


def _should_skip(path: Path) -> bool:
    if any(part in SKIP_DIR_NAMES for part in path.parts):
        return True
    return path.suffix in SKIP_SUFFIXES


def _add_file(tar: tarfile.TarFile, path: Path, arcname: str) -> None:
    data = path.read_bytes()
    if path.suffix == ".sh":
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
        _add_file(tar, child, child.relative_to(ROOT).as_posix())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / "transferbo2_borylation_p4_hpc.tgz")
    args = ap.parse_args()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    if out.exists():
        out.unlink()
    with tarfile.open(out, "w:gz") as tar:
        for rel in INCLUDE:
            add_path(tar, rel)
    mb = out.stat().st_size / (1024 * 1024)
    with tarfile.open(out, "r:gz") as tar:
        names = tar.getnames()
        if b"\r" in b"".join(tar.extractfile(n).read() for n in names if n.endswith(".sh")):
            raise SystemExit("CRLF still present in submit script")
        if "__pycache__" in "\n".join(names):
            raise SystemExit("pycache leaked into tarball")
        if not any(n.endswith("transferbo2_borylation.db") for n in names):
            raise SystemExit("borylation DB missing from tarball")
    print(f"[OK] {out}  ({mb:.1f} MB)")
    print("upload, then on HPC:")
    print("  cd ~/TransferBO2.0 && tar -xzf ~/transferbo2_borylation_p4_hpc.tgz")
    print("  bash scripts/hpc/submit_borylation_p4_dsub.sh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
