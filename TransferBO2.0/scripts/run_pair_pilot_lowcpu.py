#!/usr/bin/env python
"""Low-CPU pair pilot runner (amination or suzuki via --config)."""

from __future__ import annotations

import argparse
import os
import sys
import warnings
from datetime import datetime
from pathlib import Path

for k in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[k] = "1"
os.environ.setdefault("PYTHONWARNINGS", "ignore")

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "src"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, required=True)
    args = ap.parse_args()
    warnings.filterwarnings("ignore")
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.kernel32.SetPriorityClass(
                ctypes.windll.kernel32.GetCurrentProcess(), 0x00004000
            )
        except Exception:
            pass

    import yaml

    from transferbo2.benchmarks.protocols import run_pair_grid

    cfg = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    sk = {
        "acquisition": cfg.get("acquisition", "ei"),
        "topk": int(cfg.get("topk", 5)),
        "max_warm_points": int(cfg.get("max_warm_points", 120)),
        "gate_spearman_min": float(cfg.get("gate_spearman_min", 0.2)),
        "use_plate_correction": bool(cfg.get("use_plate_correction", False)),
        "warm_strength": float(cfg.get("warm_strength", 0.5)),
        "lengthscale_sub": float(cfg.get("lengthscale_sub", 1.0)),
        "gate_sim_min": float(cfg.get("gate_sim_min", 0.15)),
    }
    print(f"[{datetime.now().isoformat(timespec='seconds')}] START pair pilot {args.config}")
    summary = run_pair_grid(
        cfg.get("db"),
        target_substrates=cfg.get("target_substrates"),
        source_substrates=cfg.get("source_substrates"),
        seeds=cfg.get("seeds") or [0, 1, 2],
        baseline_strategies=cfg.get("baseline_strategies") or ["random", "cold_start"],
        transfer_strategies=cfg.get("transfer_strategies")
        or ["topk_warm", "nearest_topk_warm", "sim_weighted", "safe_gate"],
        n_init=int(cfg.get("n_init", 5)),
        budget=int(cfg.get("budget", 20)),
        out_dir=cfg.get("out_dir"),
        strategy_kwargs=sk,
        skip_existing=True,
        workers=1,
        dry_run=False,
    )
    if not summary.empty:
        print(summary.groupby("strategy")[["auc", "final_best"]].mean())
    print(f"[{datetime.now().isoformat(timespec='seconds')}] DONE")


if __name__ == "__main__":
    main()
