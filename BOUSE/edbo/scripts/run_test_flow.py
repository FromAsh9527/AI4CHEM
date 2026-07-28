# -*- coding: utf-8 -*-
"""
基于官方 Deoxyfluorination 数据的端到端测试流程。

步骤:
  1. 若无工作区则自动构建（workspaces/deoxy_demo）
  2. 用当前 history 跑贝叶斯推荐
  3. 与官方下一轮条件对比（集合 overlap）
  4. 可选：追加官方下一轮实测，再推荐一轮

用法::

    conda activate edbo
    python scripts/run_test_flow.py
    python scripts/run_test_flow.py --rebuild --rounds 1
    python scripts/run_test_flow.py --append-next   # 推荐后把官方下一轮写入历史
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from factors import factor_keys  # noqa: E402
from recommend import recommend_bo  # noqa: E402
from workspace import (  # noqa: E402
    get_factors,
    load_config,
    load_history,
    project_dir,
    save_history,
    save_recommendations,
)

EXAMPLE_RESULTS = (
    ROOT / "data" / "deoxyfluorination_example" / "results"
)
COL_MAP = {
    "sulfonyl_fluoride_SMILES_index": "sulfonyl_fluoride",
    "base_SMILES_index": "base",
    "solvent_SMILES_index": "solvent",
    "substrate_concentration_index": "substrate_concentration",
    "sulfonyl_equiv_index": "sulfonyl_equiv",
    "base_equiv_index": "base_equiv",
    "temperature_index": "temperature",
    "yield": "yield",
}
ROUND_ORDER = ["init"] + [f"round{i}" for i in range(9)]


def _normalize(df: pd.DataFrame, factors) -> set[tuple]:
    from domain_builder import row_key

    return {row_key(r, factors) for _, r in df.iterrows()}


def _official_round(name: str) -> pd.DataFrame:
    path = EXAMPLE_RESULTS / f"{name}.csv"
    df = pd.read_csv(path, index_col=0).rename(columns=COL_MAP)
    return df


def _infer_next_official(history: pd.DataFrame, keys: list[str]) -> str | None:
    """根据当前历史覆盖了哪些官方轮次，推断下一轮对照文件名。"""
    covered = 0
    for i, name in enumerate(ROUND_ORDER):
        off = _official_round(name)
        # 累计前缀轮次条数
        prefix_n = sum(len(_official_round(ROUND_ORDER[j])) for j in range(i + 1))
        if len(history) >= prefix_n:
            # 粗判：历史条数达到该前缀
            covered = i + 1
        else:
            break
    if covered >= len(ROUND_ORDER):
        return None
    # 若历史正好是 init..round{k-1}，下一轮是 round{k} 或 init 后的 round0
    return ROUND_ORDER[covered]


def ensure_workspace(name: str, rebuild: bool, rounds: int, max_features: int) -> Path:
    ws = project_dir(ROOT, name)
    need = rebuild or not (ws / "config.json").is_file()
    if need:
        cmd = [
            sys.executable,
            str(ROOT / "scripts" / "build_deoxy_workspace.py"),
            "--name",
            name,
            "--rounds",
            str(rounds),
            "--max-features",
            str(max_features),
        ]
        print("构建工作区:", " ".join(cmd))
        subprocess.check_call(cmd, cwd=str(ROOT))
    return ws


def main():
    parser = argparse.ArgumentParser(description="Deoxyfluorination 测试流程")
    parser.add_argument("--name", default="deoxy_demo")
    parser.add_argument("--rebuild", action="store_true", help="强制重建工作区")
    parser.add_argument(
        "--rounds",
        type=int,
        default=0,
        help="重建时并入的官方 round 数（默认仅 init）",
    )
    parser.add_argument("--max-features", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=5)
    parser.add_argument("--training-iters", type=int, default=80)
    parser.add_argument(
        "--append-next",
        action="store_true",
        help="对比后将官方下一轮实测追加进 history，并再跑一次推荐",
    )
    args = parser.parse_args()

    ws = ensure_workspace(args.name, args.rebuild, args.rounds, args.max_features)
    cfg = load_config(ws)
    factors = get_factors(cfg)
    keys = factor_keys(factors)
    target = cfg.get("target_column", "yield")
    hist = load_history(ws, target, keys)
    print("=" * 60)
    print(f"项目: {args.name}")
    print(f"历史: {len(hist)} 条 | 因子: {keys}")
    print("=" * 60)

    print("\n[1] 贝叶斯推荐 …")
    rec, info = recommend_bo(
        ws,
        factors,
        hist,
        target_col=target,
        batch_size=int(args.batch_size),
        acquisition_function=cfg.get("acquisition_function", "EI"),
        training_iters=int(args.training_iters),
        noise_constraint=float(cfg.get("noise_constraint", 0.01)),
        domain_cap=int(cfg.get("domain_cap", 2500)),
    )
    save_recommendations(ws, rec)
    print(f"  domain={info['domain_size']:,} features={info['n_features']} proposed={len(rec)}")
    print(rec.to_string(index=False))

    next_name = _infer_next_official(hist, keys)
    report = {"domain_size": info["domain_size"], "n_history": len(hist), "proposed": len(rec)}
    if next_name:
        official = _official_round(next_name)
        overlap = len(_normalize(rec, factors) & _normalize(official, factors))
        report["compare_to"] = next_name
        report["overlap"] = overlap
        report["official_n"] = len(official)
        report["overlap_ratio"] = overlap / max(len(official), 1)
        print(f"\n[2] 与官方 {next_name}.csv 对比: overlap={overlap}/{len(official)} ({report['overlap_ratio']:.0%})")
        print("  （描述符截断 / gpytorch 版本不同时，不必 100% 一致）")
    else:
        print("\n[2] 无更多官方轮次可对照")

    if args.append_next and next_name:
        print(f"\n[3] 追加官方 {next_name} 实测到 history …")
        nxt = _official_round(next_name)[keys + [target]].copy()
        for c in keys:
            if c in ("sulfonyl_fluoride", "base", "solvent"):
                nxt[c] = nxt[c].astype(str)
        merged = pd.concat([hist, nxt], ignore_index=True)
        save_history(ws, merged)
        print(f"  history → {len(merged)} 条")
        print("\n[4] 用更新后的历史再推荐 …")
        rec2, info2 = recommend_bo(
            ws,
            factors,
            merged,
            target_col=target,
            batch_size=int(args.batch_size),
            acquisition_function=cfg.get("acquisition_function", "EI"),
            training_iters=int(args.training_iters),
            noise_constraint=float(cfg.get("noise_constraint", 0.01)),
            domain_cap=int(cfg.get("domain_cap", 2500)),
        )
        save_recommendations(ws, rec2)
        print(rec2.to_string(index=False))
        report["after_append_history"] = len(merged)
        report["second_batch_n"] = len(rec2)

    out_json = ws / "test_flow_report.json"
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n报告: {out_json}")
    print("可在 Streamlit 中打开项目:", args.name)
    print("  streamlit run app.py")
    print("完成。")


if __name__ == "__main__":
    main()
