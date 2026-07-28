# -*- coding: utf-8 -*-
"""无 UI 冒烟：建项目 → 无模型推荐 → 假回填 → BO 推荐。"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from backfill import merge_results
from recommend import recommend_bo, recommend_nomodel
from templates import apply_template
from workspace import (
    create_project,
    descriptor_path,
    get_factors,
    load_history,
    project_dir,
    save_history,
    save_recommendations,
)


def main():
    name = "_smoke_demo"
    ws = project_dir(ROOT, name)
    if ws.exists():
        import shutil

        shutil.rmtree(ws)

    cfg = apply_template("condition_optimization")
    # 缩小数值网格，加快冒烟
    for f in cfg["factors"]:
        if f["key"] == "temperature":
            f["values"] = [0.0, 25.0]
        if f["key"] == "base_eq":
            f["values"] = [1.0, 2.0]
        if f["key"] == "concentration":
            f["values"] = [0.3, 0.6]

    pid = create_project(ROOT, name, cfg)
    ws = project_dir(ROOT, pid)
    print("project:", pid)

    # 迷你描述符
    pd.DataFrame(
        {
            "molecule_id": ["SolA", "SolB"],
            "feat1": [0.1, 0.9],
            "feat2": [1.0, 0.2],
        }
    ).to_csv(descriptor_path(ws, "solvent"), index=False)
    pd.DataFrame(
        {
            "molecule_id": ["BaseX", "BaseY"],
            "feat1": [0.3, 0.7],
            "feat2": [0.5, 0.4],
        }
    ).to_csv(descriptor_path(ws, "base"), index=False)

    factors = get_factors(cfg)
    hist = load_history(ws, "yield", [f.key for f in factors])
    rec, info = recommend_nomodel(ws, factors, hist, batch_size=3, method="lhs", seed=1)
    save_recommendations(ws, rec)
    print("nomodel:", len(rec), "domain", info["domain_size"])
    print(rec)

    fake = rec.drop(columns=["rank"]).copy()
    fake["yield"] = [10.0, 20.0, 15.0][: len(fake)]
    merged = merge_results(hist, fake, factors, "yield", replace=False)
    save_history(ws, merged)
    print("history:", len(merged))

    rec2, info2 = recommend_bo(
        ws,
        factors,
        merged,
        target_col="yield",
        batch_size=2,
        training_iters=30,
        noise_constraint=0.01,
    )
    save_recommendations(ws, rec2)
    print("bo:", len(rec2), info2["mode"])
    print(rec2)
    print("SMOKE OK")


if __name__ == "__main__":
    main()
