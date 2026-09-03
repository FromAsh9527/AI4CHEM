#!/usr/bin/env python
"""Preflight checks before amination_v1 experiment."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import yaml

from transferbo2.benchmarks.protocols import _desc_map, run_loso_once
from transferbo2.data.database import DEFAULT_DB, connect, experiments_frame
from transferbo2.strategies.base import StrategyConfig, available_strategies


REQUIRED_STRATS = [
    "random",
    "cold_start",
    "topk_warm",
    "nearest_topk_warm",
    "sim_weighted",
    "safe_gate",
]


def main() -> int:
    cfg_path = Path("configs/amination_exp_v1_pilot.yaml")
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    db = Path(cfg.get("db", DEFAULT_DB))
    ok = True

    print("=== Preflight amination_v1 ===")
    if not db.exists():
        print(f"[FAIL] DB missing: {db}")
        print("  -> python scripts/ingest_amination.py")
        return 1
    print(f"[OK] DB {db}")

    with connect(db) as conn:
        df = experiments_frame(conn)
        desc = _desc_map(conn)

    n_sub = df["substrate_id"].nunique()
    n_cond = df["condition_id"].nunique()
    print(f"[OK] rows={len(df)} substrates={n_sub} conditions={n_cond}")
    if n_sub < 5 or n_cond < 100:
        print("[FAIL] unexpected scale")
        ok = False

    if len(desc) < n_sub:
        print(f"[FAIL] descriptors {len(desc)} < substrates {n_sub}")
        ok = False
    else:
        print(f"[OK] hashed_smiles descriptors for {len(desc)} substrates")

    avail = set(available_strategies())
    missing = [s for s in REQUIRED_STRATS if s not in avail]
    if missing:
        print(f"[FAIL] missing strategies: {missing}")
        ok = False
    else:
        print(f"[OK] strategies: {REQUIRED_STRATS}")

    targets = cfg.get("target_substrates") or []
    for t in targets:
        if t not in set(df["substrate_id"]):
            print(f"[FAIL] target {t} not in DB")
            ok = False
    print(f"[OK] pilot targets: {targets}")

    # Tiny dry-run: cold_start on sub_s4, budget=8
    print("[..] dry-run cold_start sub_s4 budget=8 ...")
    sc = StrategyConfig(
        n_init=3,
        budget=8,
        seed=0,
        use_plate_correction=False,
        max_warm_points=40,
        warm_strength=0.5,
    )
    rec = run_loso_once(df, desc, target_substrate="sub_s4", strategy_name="cold_start", config=sc)
    auc = rec["stats"]["auc"]
    best = rec["stats"]["final_best"]
    print(f"[OK] dry-run AUC={auc:.1f} best={best:.2f}")
    if not np.isfinite(auc) or best < 0:
        print("[FAIL] dry-run produced invalid stats")
        ok = False

    print("[..] dry-run sim_weighted sub_s4 budget=8 ...")
    rec2 = run_loso_once(df, desc, target_substrate="sub_s4", strategy_name="sim_weighted", config=sc)
    print(
        f"[OK] sim_weighted AUC={rec2['stats']['auc']:.1f} "
        f"best={rec2['stats']['final_best']:.2f} "
        f"meta_n_warm={rec2['meta'].get('n_warm')}"
    )

    if ok:
        print("\nPREFLIGHT PASSED")
        print("Next: python scripts/run_loso.py --config configs/amination_exp_v1_pilot.yaml")
        return 0
    print("\nPREFLIGHT FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
