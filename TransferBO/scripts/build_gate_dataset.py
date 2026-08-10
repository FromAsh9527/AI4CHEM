#!/usr/bin/env python
"""Build TransferGate training table from W3 grid + plate features.

Example:
  python scripts/build_gate_dataset.py \\
      --grid results/transfer_grid/grid_results.csv \\
      --out results/gate/train.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from run_experiment import _feature_strings  # noqa: E402
from transferbo.data import get_plate, load_plates  # noqa: E402
from transferbo.gate.features import FEATURE_NAMES, GateFeatureInputs, compute_gate_features  # noqa: E402
from transferbo.gate.train import build_label_table  # noqa: E402
from transferbo.utils import ensure_dir, load_config  # noqa: E402
from transferbo.utils.protocol import load_protocol  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--grid", type=Path, default=ROOT / "results/transfer_grid/grid_results.csv")
    ap.add_argument("--config", type=Path, default=ROOT / "configs/default.yaml")
    ap.add_argument("--protocol", type=Path, default=ROOT / "configs/protocol.yaml")
    ap.add_argument("--out", type=Path, default=ROOT / "results/gate/train.csv")
    ap.add_argument("--min-gain", type=float, default=0.02)
    ap.add_argument(
        "--include-heldout-labels",
        action="store_true",
        help="Dangerous: include held-out target rows as labels (default: exclude).",
    )
    args = ap.parse_args()

    cfg = load_config(args.config)
    protocol = load_protocol(args.protocol)
    held = protocol.get("held_out", {}).get("target_plate", "plate_4")
    exclude = [] if args.include_heldout_labels else [held]

    grid = pd.read_csv(args.grid)
    labels = build_label_table(grid, min_gain=args.min_gain, exclude_targets=exclude)
    if labels.empty:
        raise SystemExit("No label rows built — check grid_results.csv")

    df = load_plates(cfg["data"]["processed_path"])
    rows = []
    for _, lab in labels.iterrows():
        src = lab["source_plate"]
        tgt = lab["target_plate"]
        rep = lab["representation"]
        source_df = get_plate(df, src)
        target_df = get_plate(df, tgt)
        src_s = _feature_strings(source_df, rep)
        tgt_s = _feature_strings(target_df, rep)
        from transferbo.representations import build_representation

        kwargs = dict((cfg.get("representation", {}) or {}).get(rep, {}) or {})
        r = build_representation(rep, **kwargs)
        r.fit(src_s + tgt_s)
        X_s = r.transform(src_s)
        X_t = r.transform(tgt_s)

        feat = compute_gate_features(
            GateFeatureInputs(
                X_source=X_s,
                y_source=source_df["response"].to_numpy(dtype=float),
                X_target=X_t,
                representation=rep,
                source_fraction=float(cfg.get("transfer", {}).get("source_fraction", 1.0)),
                seed=0,
            )
        )
        row = {**lab.to_dict(), **feat}
        rows.append(row)

    out = pd.DataFrame(rows)
    # column order: ids, labels, features
    front = [
        "source_plate",
        "target_plate",
        "representation",
        "y_mode",
        "y_cls",
        "y_delta_vs_cold",
        "y_gain_label_vs_cold",
        "y_best_frac",
        "cold_frac_mean",
        "delta_diversity",
        "delta_label",
        "delta_multitask",
    ]
    cols = [c for c in front if c in out.columns] + [c for c in FEATURE_NAMES if c in out.columns]
    cols += [c for c in out.columns if c not in cols]
    out = out[cols]
    ensure_dir(args.out.parent)
    out.to_csv(args.out, index=False)
    print(f"Wrote {len(out)} rows -> {args.out}")
    print("y_mode counts:")
    print(out["y_mode"].value_counts().to_string())


if __name__ == "__main__":
    main()
