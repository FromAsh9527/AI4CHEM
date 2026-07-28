# -*- coding: utf-8 -*-
"""Headless UI-flow smoke: create project → scope → init run → backfill → BO run."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from backfill import apply_backfill, pending_suggestions
from runner import generate_scope, run_round, scope_summary
from workspace import (
    DEFAULT_CONFIG,
    create_project,
    load_config,
    load_reaction,
    project_dir,
    suggested_mask,
)

NAME = "ui_smoke"


def main() -> int:
    ws = project_dir(ROOT, NAME)
    if ws.exists():
        shutil.rmtree(ws)

    create_project(
        ROOT,
        NAME,
        {
            **DEFAULT_CONFIG,
            "objectives": ["yield", "cost"],
            "objective_mode": ["max", "min"],
            "batch": 2,
            "seed": 0,
            "init_sampling_method": "cvt",
            "acquisition_function": "NoisyEHVI",
            "components": {
                "solvent": ["THF", "DMSO"],
                "T": [0, 25],
                "concentration": [0.1, 0.5],
            },
        },
    )
    cfg = load_config(ws)
    generate_scope(ws, cfg["components"], cfg)
    cfg = load_config(ws)

    df0 = run_round(ws, cfg)
    n_sug = int(suggested_mask(df0).sum())
    assert n_sug == 2, f"expected 2 suggestions, got {n_sug}"

    pending = pending_suggestions(ws, cfg)
    assert len(pending) == 2
    # fake measurements
    edits = pending.copy()
    edits["yield"] = [80.0, 55.0]
    edits["cost"] = [10.0, 4.0]
    n = apply_backfill(ws, edits, cfg)
    assert n == 2, n

    info = scope_summary(ws, cfg)
    assert info["n_observed"] == 2, info

    df1 = run_round(ws, cfg)
    n_sug2 = int(suggested_mask(df1).sum())
    assert n_sug2 == 2, f"BO suggested {n_sug2}"
    # observed rows should be priority -1
    obs = load_reaction(ws, cfg)
    assert (obs.loc[obs["yield"].astype(str) != "PENDING", "priority"] == -1).all()

    print(f"UI_SMOKE OK rows={len(obs)} suggested={n_sug2} observed={info['n_observed']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
