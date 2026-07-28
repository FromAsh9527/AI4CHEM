# -*- coding: utf-8 -*-
"""
用 Suzuki oracle 给「本轮推荐」查真实产率并写入历史。

这样测的是严格闭环：推荐什么条件 → 查表得到 yield → 回填 → 再推荐。
不依赖官方论文那几轮条件是否与本次推荐一致。

用法::

    cd edbo
    python scripts/oracle_backfill.py --project suzuki_demo
    python scripts/oracle_backfill.py --project suzuki_demo --dry-run
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from backfill import merge_results  # noqa: E402
from factors import factor_keys  # noqa: E402
from workspace import (  # noqa: E402
    get_factors,
    load_config,
    load_history,
    load_recommendations,
    project_dir,
    save_history,
)


def lookup_yields(recs: pd.DataFrame, oracle: pd.DataFrame, keys: list[str], target: str) -> pd.DataFrame:
    o = oracle.copy()
    r = recs.copy()
    for c in keys:
        o[c] = o[c].astype(str)
        r[c] = r[c].astype(str)
    merged = r[keys].merge(o[keys + [target]], on=keys, how="left")
    missing = merged[target].isna().sum()
    if missing:
        raise ValueError(
            f"有 {missing}/{len(merged)} 条推荐在 oracle 中找不到产率。"
            "请确认搜索域与 experiment_index 一致。"
        )
    return merged


def main() -> None:
    p = argparse.ArgumentParser(description="Suzuki oracle 查表回填")
    p.add_argument("--project", default="suzuki_demo")
    p.add_argument("--dry-run", action="store_true", help="只写出回填 CSV，不写 history")
    p.add_argument(
        "--out",
        type=Path,
        default=None,
        help="导出回填文件路径（默认 workspaces/<project>/oracle_filled.csv）",
    )
    args = p.parse_args()

    ws = project_dir(ROOT, args.project)
    if not ws.is_dir():
        raise SystemExit(f"项目不存在: {ws}（先跑 build_suzuki_workspace.py）")

    oracle_path = ws / "oracle.csv"
    if not oracle_path.is_file():
        raise SystemExit(f"缺少 {oracle_path}")

    cfg = load_config(ws)
    factors = get_factors(cfg)
    keys = factor_keys(factors)
    target = cfg.get("target_column", "yield")

    rec = load_recommendations(ws)
    if rec is None or rec.empty:
        raise SystemExit("没有 last_recommendations.csv，请先在步骤3生成推荐")

    oracle = pd.read_csv(oracle_path)
    filled = lookup_yields(rec, oracle, keys, target)
    out = args.out or (ws / "oracle_filled.csv")
    filled.to_csv(out, index=False)
    print(f"查表完成 → {out}")
    print(filled)

    if args.dry_run:
        print("(dry-run: 未写入 history)")
        return

    hist = load_history(ws, target, keys)
    merged = merge_results(hist, filled, factors, target, replace=False)
    save_history(ws, merged)
    print(f"已写入历史，共 {len(merged)} 条")


if __name__ == "__main__":
    main()
