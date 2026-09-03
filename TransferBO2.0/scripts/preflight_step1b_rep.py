#!/usr/bin/env python
"""Preflight for Step1b representation axis (Phase A / optional B)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import yaml

from transferbo2.benchmarks.protocols import _desc_map, run_loso_once
from transferbo2.data.database import connect, experiments_frame
from transferbo2.descriptors.features import load_condition_dft_csv, substrate_similarity_map
from transferbo2.strategies.base import StrategyConfig


def _check_db(cfg: dict, label: str) -> bool:
    ok = True
    db = Path(cfg["db"])
    print(f"\n=== {label}: {db} ===")
    if not db.exists():
        print(f"[FAIL] DB missing: {db}")
        return False

    sub_name = str(cfg.get("substrate_descriptor", "morgan_r2"))
    with connect(db) as conn:
        df = experiments_frame(conn)
        desc = _desc_map(conn, name=sub_name)
        hashed = _desc_map(conn, name="hashed_smiles_v1")

    n_sub = int(df["substrate_id"].nunique())
    print(f"[OK] rows={len(df)} substrates={n_sub} conditions={df['condition_id'].nunique()}")

    if len(hashed) < n_sub:
        print(f"[FAIL] hashed_smiles_v1 {len(hashed)} < {n_sub}")
        ok = False
    else:
        print(f"[OK] hashed_smiles_v1 kept ({len(hashed)})")

    if len(desc) < n_sub:
        print(f"[FAIL] {sub_name} {len(desc)} < {n_sub} — run scripts/build_morgan_descriptors.py")
        ok = False
    else:
        dim = next(iter(desc.values())).shape[0]
        print(f"[OK] {sub_name} for {len(desc)} substrates (dim={dim})")

    # Tanimoto sanity on pilot targets
    targets = cfg.get("target_substrates") or sorted(df["substrate_id"].unique())[:3]
    metric = str(cfg.get("similarity_metric", "tanimoto"))
    if desc and targets:
        t0 = targets[0]
        sources = [s for s in desc if s != t0][:5]
        sims = substrate_similarity_map(desc, t0, sources, metric=metric)
        print(f"[OK] {metric} sample vs {t0}: { {k: round(v, 3) for k, v in list(sims.items())[:3]} }")

    # DFT coverage if requested
    if str(cfg.get("condition_features", "ohe")).lower() == "dft":
        dft_path = cfg.get("dft_csv")
        if not dft_path or not Path(dft_path).exists():
            print(f"[FAIL] dft_csv missing: {dft_path}")
            ok = False
        else:
            dft = load_condition_dft_csv(dft_path)
            cids = set(df["condition_id"].astype(str))
            hit = len(cids & set(dft["condition_id"].astype(str)))
            print(f"[OK] DFT overlap {hit}/{len(cids)} conditions ({Path(dft_path).name})")
            if hit < len(cids):
                print(f"[FAIL] DFT missing {len(cids) - hit} conditions")
                ok = False

    # Tiny dry-run: nearest (uses sim) + topk (must ignore phi)
    if desc and targets:
        sc = StrategyConfig(
            n_init=3,
            budget=6,
            seed=0,
            use_plate_correction=False,
            max_warm_points=40,
            similarity_metric=metric,
        )
        t = targets[0]
        print(f"[..] dry-run nearest_topk_warm {t} ...")
        rec = run_loso_once(
            df,
            desc,
            target_substrate=t,
            strategy_name="nearest_topk_warm",
            config=sc,
            condition_features=str(cfg.get("condition_features", "ohe")),
            dft_matrix=load_condition_dft_csv(cfg["dft_csv"])
            if cfg.get("condition_features") == "dft" and cfg.get("dft_csv")
            else None,
        )
        print(
            f"[OK] nearest AUC={rec['stats']['auc']:.1f} "
            f"nearest={rec['meta'].get('nearest')} sim={rec['meta'].get('sim')}"
        )
        if not np.isfinite(rec["stats"]["auc"]):
            ok = False

    return ok


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    configs = [
        root / "configs" / "amination_rep_A_morgan_sub_pilot.yaml",
        root / "configs" / "suzuki_rep_A_morgan_sub_pilot.yaml",
    ]
    ok = True
    print("=== Preflight Step1b representation ===")
    for path in configs:
        if not path.exists():
            print(f"[FAIL] missing config {path}")
            ok = False
            continue
        cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not _check_db(cfg, path.stem):
            ok = False

    if ok:
        print("\nPREFLIGHT PASSED")
        print("Next: python scripts/run_loso.py --config configs/amination_rep_A_morgan_sub_pilot.yaml")
        return 0
    print("\nPREFLIGHT FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
