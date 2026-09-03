#!/usr/bin/env python
"""Leave-one-substrate-out grid."""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from transferbo2.benchmarks.protocols import run_loso_grid
from transferbo2.data.database import DEFAULT_DB


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--config", type=Path, required=True)
    args = p.parse_args()
    cfg = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    summary = run_loso_grid(
        cfg.get("db", DEFAULT_DB),
        strategies=cfg.get("strategies")
        or [
            "random",
            "cold_start",
            "topk_warm",
            "nearest_topk_warm",
            "pooled",
            "sim_weighted",
            "contextual",
            "plate_aware",
        ],
        target_substrates=cfg.get("target_substrates"),
        seeds=cfg.get("seeds") or [0, 1, 2],
        n_init=int(cfg.get("n_init", 5)),
        budget=int(cfg.get("budget", 20)),
        out_dir=cfg.get("out_dir", "results/loso_demo"),
    )
    print(summary.groupby("strategy")[["auc", "final_best", "hit10_top5pct"]].mean())
    print(f"Wrote {cfg.get('out_dir', 'results/loso_demo')}")


if __name__ == "__main__":
    main()
