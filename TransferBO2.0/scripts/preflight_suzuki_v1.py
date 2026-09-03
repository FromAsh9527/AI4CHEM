#!/usr/bin/env python
"""Preflight checks before suzuki_v1 experiment."""

from __future__ import annotations

from pathlib import Path

import yaml

from transferbo2.benchmarks.protocols import _desc_map, run_loso_once
from transferbo2.data.database import connect, experiments_frame
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
    cfg_path = Path("configs/suzuki_exp_v1_pilot.yaml")
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    db = Path(cfg.get("db", "data/db/transferbo2_suzuki.db"))
    ok = True

    print("=== Preflight suzuki_v1 ===")
    if not db.exists():
        print(f"[FAIL] DB missing: {db}")
        print("  -> python scripts/ingest_suzuki.py")
        return 1
    print(f"[OK] DB {db}")

    with connect(db) as conn:
        df = experiments_frame(conn)
        desc = _desc_map(conn)

    n_sub = df["substrate_id"].nunique()
    n_cond = df["condition_id"].nunique()
    print(f"[OK] rows={len(df)} substrates={n_sub} conditions={n_cond}")
    if n_sub != 12 or n_cond != 308:
        print(f"[WARN] expected 12×308, got {n_sub}×{n_cond}")
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

    print("[..] dry-run cold_start suz_t1 budget=8 ...")
    sc = StrategyConfig(
        n_init=3,
        budget=8,
        seed=0,
        use_plate_correction=False,
        max_warm_points=40,
        warm_strength=0.5,
    )
    rec = run_loso_once(
        df, desc, target_substrate="suz_t1", strategy_name="cold_start", config=sc
    )
    fb = rec["stats"]["final_best"]
    print(f"[OK] cold dry-run final_best={fb:.2f} auc={rec['stats']['auc']:.1f}")
    if not (fb == fb):  # NaN
        print("[FAIL] NaN final_best")
        ok = False

    print("[..] dry-run topk_warm suz_t1 budget=8 ...")
    rec2 = run_loso_once(
        df, desc, target_substrate="suz_t1", strategy_name="topk_warm", config=sc
    )
    print(
        f"[OK] topk dry-run final_best={rec2['stats']['final_best']:.2f} "
        f"auc={rec2['stats']['auc']:.1f}"
    )

    if ok:
        print("=== PREFLIGHT PASSED ===")
        return 0
    print("=== PREFLIGHT FAILED ===")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
