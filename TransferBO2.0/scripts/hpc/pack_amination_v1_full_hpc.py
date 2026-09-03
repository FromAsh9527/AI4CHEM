#!/usr/bin/env python
"""Pack amination_v1 full LOSO tarball for HPC (Windows-friendly).

- Excludes __pycache__ / *.pyc
- Forces LF newlines for *.sh
- Normalizes mtime (avoids 'timestamp in the future' on HPC)

  python scripts/hpc/pack_amination_v1_full_hpc.py
"""

from __future__ import annotations

import argparse
import io
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

INCLUDE = [
    "configs/amination_exp_v1_full.yaml",
    "configs/amination_exp_v1_pilot.yaml",
    "src",
    "scripts/run_loso.py",
    "scripts/summarize_results.py",
    "scripts/preflight_amination_v1.py",
    "scripts/hpc",
    "docs/06_experiment_amination_v1.md",
    "pyproject.toml",
    "requirements.txt",
    "data/db/schema.sql",
    "data/db/transferbo2.db",
    "data/processed/amination_long.csv",
]

SKIP_DIR_NAMES = {"__pycache__", ".git", "dsub_jobs"}
SKIP_SUFFIXES = {".pyc", ".pyo"}
MTIME = int(time.time()) - 120  # slightly in the past vs HPC clock skew


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
    ap.add_argument("--out", type=Path, default=ROOT / "transferbo2_amination_v1_full_hpc.tgz")
    args = ap.parse_args()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    if out.exists():
        out.unlink()
    with tarfile.open(out, "w:gz") as tar:
        for rel in INCLUDE:
            add_path(tar, rel)
    mb = out.stat().st_size / (1024 * 1024)
    # sanity: submit script must be LF-only
    with tarfile.open(out, "r:gz") as tar:
        f = tar.extractfile("scripts/hpc/submit_amination_v1_full_dsub.sh")
        assert f is not None
        raw = f.read()
        if b"\r" in raw:
            raise SystemExit("CRLF still present in submit script")
        if b"__pycache__" in b"\n".join(n.encode() for n in tar.getnames()):
            raise SystemExit("pycache leaked into tarball")
    print(f"[OK] {out}  ({mb:.1f} MB)")
    print("re-upload via file manager, then on HPC:")
    print("  cd ~/TransferBO2.0 && tar -xzf ~/transferbo2_amination_v1_full_hpc.tgz")
    print("  sed -i 's/\\r$//' scripts/hpc/*.sh   # belt-and-suspenders")
    print("  bash scripts/hpc/submit_amination_v1_full_dsub.sh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
