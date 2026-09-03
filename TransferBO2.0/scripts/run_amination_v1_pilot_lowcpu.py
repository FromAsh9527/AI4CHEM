#!/usr/bin/env python
"""Low-CPU runner for amination_v1 pilot.

- Single-thread BLAS/OpenMP
- Below-normal process priority (Windows)
- Warnings filtered; UTF-8 progress log
"""

from __future__ import annotations

import os
import sys
import warnings
from datetime import datetime
from pathlib import Path

for k in (
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "BLIS_NUM_THREADS",
):
    os.environ[k] = "1"

os.environ.setdefault("PYTHONWARNINGS", "ignore")

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "src"))

LOG = ROOT / "results" / "amination_v1_pilot" / "run.log"
LOG.parent.mkdir(parents=True, exist_ok=True)


class _Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for s in self.streams:
            s.write(data)
            s.flush()

    def flush(self):
        for s in self.streams:
            s.flush()


def _set_low_priority() -> None:
    try:
        import psutil  # type: ignore

        p = psutil.Process()
        if hasattr(psutil, "BELOW_NORMAL_PRIORITY_CLASS"):
            p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        else:
            p.nice(10)
        print(f"priority set via psutil: {p.nice()}")
        return
    except Exception:
        pass
    if sys.platform == "win32":
        try:
            import ctypes

            # BELOW_NORMAL_PRIORITY_CLASS = 0x00004000
            ctypes.windll.kernel32.SetPriorityClass(
                ctypes.windll.kernel32.GetCurrentProcess(), 0x00004000
            )
            print("priority set: BELOW_NORMAL (win32)")
        except Exception as exc:
            print(f"priority unset ({exc})")


def main() -> None:
    warnings.filterwarnings("ignore", category=UserWarning)
    warnings.filterwarnings("ignore", message=".*ConvergenceWarning.*")
    warnings.filterwarnings("ignore", module="sklearn.gaussian_process")

    _set_low_priority()

    log_f = LOG.open("w", encoding="utf-8", buffering=1)
    sys.stdout = _Tee(sys.__stdout__, log_f)  # type: ignore
    sys.stderr = _Tee(sys.__stderr__, log_f)  # type: ignore

    from transferbo2.benchmarks.protocols import run_loso_grid
    from transferbo2.data.database import DEFAULT_DB
    import yaml

    cfg_path = ROOT / "configs" / "amination_exp_v1_pilot.yaml"
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    sk = {
        "acquisition": cfg.get("acquisition", "ei"),
        "topk": int(cfg.get("topk", 5)),
        "max_warm_points": int(cfg.get("max_warm_points", 120)),
        "gate_spearman_min": float(cfg.get("gate_spearman_min", 0.2)),
        "use_plate_correction": bool(cfg.get("use_plate_correction", False)),
        "warm_strength": float(cfg.get("warm_strength", 0.5)),
        "lengthscale_sub": float(cfg.get("lengthscale_sub", 1.0)),
    }

    n_jobs = (
        len(cfg.get("target_substrates") or [])
        * len(cfg.get("strategies") or [])
        * len(cfg.get("seeds") or [])
    )
    print(f"[{datetime.now().isoformat(timespec='seconds')}] START amination_v1_pilot")
    print(f"threads=1  priority=below_normal  planned_runs={n_jobs}")
    print(f"config={cfg_path}")
    print(f"out_dir={cfg.get('out_dir')}")

    # Progress wrapper: monkey-patch by iterating ourselves for visibility
    from transferbo2.benchmarks.protocols import run_loso_once, _desc_map
    from transferbo2.data.database import connect, experiments_frame
    from transferbo2.strategies.base import StrategyConfig
    import json
    import pandas as pd

    db = cfg.get("db", DEFAULT_DB)
    with connect(db) as conn:
        df = experiments_frame(conn)
        desc = _desc_map(conn)

    targets = cfg.get("target_substrates") or sorted(df["substrate_id"].unique())
    strategies = cfg.get("strategies")
    seeds = cfg.get("seeds") or [0]
    n_init = int(cfg.get("n_init", 5))
    budget = int(cfg.get("budget", 20))
    out_dir = Path(cfg.get("out_dir", "results/amination_v1_pilot"))
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    records = []
    done = 0
    total = len(targets) * len(strategies) * len(seeds)
    for sid in targets:
        for name in strategies:
            for seed in seeds:
                done += 1
                print(
                    f"[{datetime.now().isoformat(timespec='seconds')}] "
                    f"({done}/{total}) {name}  target={sid}  seed={seed}",
                    flush=True,
                )
                sc = StrategyConfig(n_init=n_init, budget=budget, seed=int(seed), **sk)
                rec = run_loso_once(
                    df, desc, target_substrate=sid, strategy_name=name, config=sc
                )
                records.append(rec)
                rows.append(
                    {
                        "strategy": name,
                        "target_substrate": sid,
                        "seed": seed,
                        "auc": rec["stats"]["auc"],
                        "final_best": rec["stats"]["final_best"],
                        "hit10_top5pct": rec["stats"]["hit10_top5pct"],
                        "T_0.95": rec["stats"].get("T_0.95"),
                    }
                )
                # incremental save
                pd.DataFrame(rows).to_csv(out_dir / "loso_summary.csv", index=False)
                (out_dir / "loso_records.json").write_text(
                    json.dumps(records, indent=2), encoding="utf-8"
                )

    summary = pd.DataFrame(rows)
    print(summary.groupby("strategy")[["auc", "final_best", "hit10_top5pct"]].mean())
    print(f"[{datetime.now().isoformat(timespec='seconds')}] DONE -> {out_dir}")


if __name__ == "__main__":
    main()
