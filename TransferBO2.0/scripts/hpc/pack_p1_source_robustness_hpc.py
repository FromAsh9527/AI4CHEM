#!/usr/bin/env python
"""Pack P1 source-subset BO LOSO for HPC (amination + Suzuki).

  python scripts/hpc/pack_p1_source_robustness_hpc.py
"""

from __future__ import annotations

import argparse
import io
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

INCLUDE = [
    "configs/amination_p1_source_robustness_hpc.yaml",
    "configs/suzuki_p1_source_robustness_hpc.yaml",
    "src",
    "scripts/run_source_subset_loso.py",
    "scripts/analyze_p1p2_list_stability.py",
    "scripts/hpc",
    "docs/17_step3_experiment_plan.md",
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
    ap.add_argument(
        "--out",
        type=Path,
        default=ROOT / "transferbo2_p1_source_robustness_hpc.tgz",
    )
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
            "scripts/hpc/submit_p1_amination_dsub.sh",
            "scripts/hpc/submit_p1_suzuki_dsub.sh",
            "scripts/hpc/submit_p1_all_dsub.sh",
        ):
            f = tar.extractfile(name)
            assert f is not None and b"\r" not in f.read(), name
    print(f"[OK] {out}  ({mb:.1f} MB)")
    print("upload to HPC home, then:")
    print("  mkdir -p ~/TransferBO2.0 && cd ~/TransferBO2.0")
    print("  tar -xzf ~/transferbo2_p1_source_robustness_hpc.tgz")
    print("  sed -i 's/\\r$//' scripts/hpc/*.sh")
    print("  bash scripts/hpc/submit_p1_all_dsub.sh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
