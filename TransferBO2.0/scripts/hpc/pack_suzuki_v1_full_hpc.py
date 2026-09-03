#!/usr/bin/env python
"""Pack suzuki_v1 full LOSO tarball for HPC (LF shells, no pycache).

  python scripts/hpc/pack_suzuki_v1_full_hpc.py
"""

from __future__ import annotations

import argparse
import io
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

INCLUDE = [
    "configs/suzuki_exp_v1_full.yaml",
    "configs/suzuki_exp_v1_pilot.yaml",
    "src",
    "scripts/run_loso.py",
    "scripts/summarize_results.py",
    "scripts/preflight_suzuki_v1.py",
    "scripts/ingest_suzuki.py",
    "scripts/hpc",
    "docs/07_experiment_suzuki_v1.md",
    "pyproject.toml",
    "requirements.txt",
    "data/db/schema.sql",
    "data/db/transferbo2_suzuki.db",
    "data/processed/suzuki_long.csv",
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
    ap.add_argument("--out", type=Path, default=ROOT / "transferbo2_suzuki_v1_full_hpc.tgz")
    args = ap.parse_args()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    if out.exists():
        out.unlink()
    with tarfile.open(out, "w:gz") as tar:
        for rel in INCLUDE:
            add_path(tar, rel)
    mb = out.stat().st_size / (1024 * 1024)
    with tarfile.open(out, "r:gz") as tar:
        f = tar.extractfile("scripts/hpc/submit_suzuki_v1_full_dsub.sh")
        assert f is not None and b"\r" not in f.read()
    print(f"[OK] {out}  ({mb:.1f} MB)")
    print("upload to HPC home, then:")
    print("  mkdir -p ~/TransferBO2.0 && cd ~/TransferBO2.0")
    print("  tar -xzf ~/transferbo2_suzuki_v1_full_hpc.tgz")
    print("  # if overlaying existing tree: sed -i 's/\\r$//' scripts/hpc/*.sh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
