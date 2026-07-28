# -*- coding: utf-8 -*-
"""
Suzuki 严格闭环冒烟：建工作区 → 无模型推荐 → oracle 回填 → BO 推荐 → 再回填。

用法::

    cd edbo
    python scripts/run_suzuki_test_flow.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from recommend import recommend_bo, recommend_nomodel  # noqa: E402
from workspace import (  # noqa: E402
    get_factors,
    load_config,
    load_history,
    project_dir,
    save_recommendations,
)


def run(cmd: list[str]) -> None:
    print(">", " ".join(cmd))
    subprocess.check_call(cmd, cwd=str(ROOT))


def main() -> None:
    py = sys.executable
    name = "suzuki_demo"
    run([py, "scripts/build_suzuki_workspace.py", "--name", name, "--seed-n", "0", "--max-features", "15"])

    ws = project_dir(ROOT, name)
    cfg = load_config(ws)
    factors = get_factors(cfg)
    target = cfg.get("target_column", "yield")
    hist = load_history(ws, target, [f.key for f in factors])

    print("\n[1] nomodel recommend")
    rec, info = recommend_nomodel(ws, factors, hist, batch_size=5, method="lhs", seed=0)
    save_recommendations(ws, rec)
    print(info)
    print(rec)

    print("\n[2] oracle backfill")
    run([py, "scripts/oracle_backfill.py", "--project", name])

    hist = load_history(ws, target, [f.key for f in factors])
    print("history after fill:", len(hist))

    print("\n[3] BO recommend")
    rec2, info2 = recommend_bo(
        ws,
        factors,
        hist,
        target_col=target,
        batch_size=5,
        acquisition_function=cfg.get("acquisition_function", "EI"),
        training_iters=int(cfg.get("training_iters", 100)),
        noise_constraint=float(cfg.get("noise_constraint", 0.01)),
        domain_cap=int(cfg.get("domain_cap", 4000)),
    )
    save_recommendations(ws, rec2)
    print(info2)
    print(rec2)

    print("\n[4] oracle backfill again")
    run([py, "scripts/oracle_backfill.py", "--project", name])
    hist = load_history(ws, target, [f.key for f in factors])
    print("history final:", len(hist))
    print("max yield so far:", float(hist[target].max()))
    print("SUZUKI FLOW OK")


if __name__ == "__main__":
    main()
