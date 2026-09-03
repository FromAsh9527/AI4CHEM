#!/usr/bin/env python
"""Low-CPU launcher for amination topk ablation."""
from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path

for k in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[k] = "1"
os.environ.setdefault("PYTHONWARNINGS", "ignore")

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "src"))

if sys.platform == "win32":
    try:
        import ctypes

        ctypes.windll.kernel32.SetPriorityClass(
            ctypes.windll.kernel32.GetCurrentProcess(), 0x00004000
        )
    except Exception:
        pass

sys.argv = [
    "run_amination_topk_ablation.py",
    "--skip-existing",
    "--workers",
    "1",
]
runpy.run_path(str(ROOT / "scripts" / "run_amination_topk_ablation.py"), run_name="__main__")
