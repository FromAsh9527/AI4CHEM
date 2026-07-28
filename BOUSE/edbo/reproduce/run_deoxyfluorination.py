# -*- coding: utf-8 -*-
"""
纯复现：EDBO 论文示例 — Deoxyfluorination（官方 examples notebook）。

对照源：
  edbo-master/examples/deoxyfluorination_optimization/optimization.ipynb

流程：
  1. 用 DFT 描述符 + 数值网格构建 312,500 点反应空间
  2. seed=8 随机初始化，与官方 results/init.csv 对比条件
  3. 逐轮载入官方实测 yield，再 run()，与下一轮官方条件对比

用法（在 BOUSE/edbo/ 目录）::

    conda activate chem_ml
    python reproduce/run_deoxyfluorination.py
    python reproduce/run_deoxyfluorination.py --rounds 2   # 只跑前 2 轮推荐（更快）
"""
from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from gpytorch.priors import GammaPrior  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "edbo-master" / "examples" / "deoxyfluorination_optimization"
OUT = Path(__file__).resolve().parent / "output" / "deoxyfluorination"
sys.path.insert(0, str(ROOT / "edbo-master"))

from edbo.bro import BO_express  # noqa: E402
from edbo.utils import Data  # noqa: E402

ROUND_FILES = [
    "init",
    "round0",
    "round1",
    "round2",
    "round3",
    "round4",
    "round5",
    "round6",
    "round7",
    "round8",
]


def _condition_cols(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c != "yield"]


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    """去掉索引列噪声，只保留条件列，统一为字符串便于比对。"""
    cols = _condition_cols(df)
    out = df[cols].copy()
    for c in cols:
        out[c] = out[c].astype(str).str.strip()
    return out.reset_index(drop=True)


def _row_set(df: pd.DataFrame) -> set[tuple]:
    return {tuple(r) for r in _normalize(df).itertuples(index=False, name=None)}


def compare_conditions(proposed: pd.DataFrame, official: pd.DataFrame, label: str) -> dict:
    """集合匹配（不要求行序一致）：返回命中数 / 官方批次数。"""
    p = _row_set(proposed)
    o = _row_set(official)
    hit = len(p & o)
    report = {
        "label": label,
        "proposed_n": len(p),
        "official_n": len(o),
        "exact_set_match": p == o,
        "overlap": hit,
        "overlap_ratio": hit / max(len(o), 1),
    }
    print(
        f"  [{label}] proposed={len(p)} official={len(o)} "
        f"overlap={hit}/{len(o)} ({report['overlap_ratio']:.0%}) "
        f"exact={report['exact_set_match']}"
    )
    return report


def build_bo() -> BO_express:
    sulfonyl_fluorides = Data(pd.read_csv(EXAMPLE / "descriptors" / "sulfonyl_fluoride_boltzmann_dft.csv"))
    bases = Data(pd.read_csv(EXAMPLE / "descriptors" / "base_boltzmann_dft.csv"))
    solvents = Data(pd.read_csv(EXAMPLE / "descriptors" / "solvent_dft.csv"))
    for data in (sulfonyl_fluorides, bases, solvents):
        data.drop(
            [
                "file_name",
                "entry",
                "vibration",
                "correlation",
                "Rydberg",
                "correction",
                "atom_number",
                "E-M_angle",
                "MEAN",
                "MAXG",
                "STDEV",
            ]
        )

    components = {
        "sulfonyl_fluoride": "DFT",
        "base": "DFT",
        "solvent": "DFT",
        "substrate_concentration": [0.1, 0.2, 0.3, 0.4, 0.5],
        "sulfonyl_equiv": [1.1, 1.3, 1.5, 1.7, 1.9],
        "base_equiv": [1.1, 1.3, 1.5, 1.7, 1.9],
        "temperature": [20, 30, 40, 50, 60],
    }
    encoding = {
        "substrate_concentration": "numeric",
        "sulfonyl_equiv": "numeric",
        "base_equiv": "numeric",
        "temperature": "numeric",
    }
    dft = {
        "sulfonyl_fluoride": sulfonyl_fluorides.data,
        "base": bases.data,
        "solvent": solvents.data,
    }

    bo = BO_express(
        components,
        encoding=encoding,
        descriptor_matrices=dft,
        acquisition_function="EI",
        init_method="rand",
        batch_size=5,
        target="yield",
    )
    # 与论文 notebook 一致的先验
    bo.lengthscale_prior = [GammaPrior(2.0, 0.2), 5.0]
    bo.outputscale_prior = [GammaPrior(5.0, 0.5), 8.0]
    bo.noise_prior = [GammaPrior(1.5, 0.5), 1.0]
    return bo


def main():
    parser = argparse.ArgumentParser(description="复现 EDBO deoxyfluorination 示例")
    parser.add_argument(
        "--rounds",
        type=int,
        default=3,
        help="在 init 之后跑多少轮 BO 推荐（官方共 9 轮 round0..round8；默认 3 轮以节省时间）",
    )
    parser.add_argument(
        "--all-rounds",
        action="store_true",
        help="跑满官方全部轮次（init + round0..round8 的推荐校验）",
    )
    args = parser.parse_args()

    if not EXAMPLE.is_dir():
        raise SystemExit(f"找不到官方示例目录: {EXAMPLE}")

    OUT.mkdir(parents=True, exist_ok=True)
    n_rec_rounds = 9 if args.all_rounds else max(0, args.rounds)

    print("=" * 60)
    print("EDBO 纯复现: Deoxyfluorination")
    print(f"示例目录: {EXAMPLE}")
    print(f"输出目录: {OUT}")
    print(f"推荐轮数: {n_rec_rounds} (init 之后)")
    print("=" * 60)

    print("\n[1/3] 构建反应空间 …")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        bo = build_bo()
    domain_n = len(bo.obj.domain)
    print(f"  domain size = {domain_n} (期望 312500)")
    if domain_n != 312_500:
        print("  警告: 搜索域大小与论文不一致")

    reports: list[dict] = []

    print("\n[2/3] 初始化 (seed=8) …")
    bo.init_sample(seed=8)
    init_path = OUT / "init_proposed.csv"
    bo.export_proposed(str(init_path))
    proposed_init = pd.read_csv(init_path, index_col=0)
    official_init = pd.read_csv(EXAMPLE / "results" / "init.csv", index_col=0)
    reports.append(compare_conditions(proposed_init, official_init, "init vs official init"))

    # 用官方实测结果驱动后续轮次（human-in-the-loop 复现）
    print("\n[3/3] 逐轮: 载入官方 results → run() → 对比下一轮条件 …")
    # 需要推荐的「输入结果文件」序列：init, round0, ... 对应提出 round0, round1, ...
    result_inputs = ROUND_FILES[: n_rec_rounds]  # init + round0.. 作为 add_results 输入
    for i, name in enumerate(result_inputs):
        src = EXAMPLE / "results" / f"{name}.csv"
        if not src.is_file():
            raise SystemExit(f"缺少官方结果: {src}")
        print(f"\n  --- add_results({name}.csv) → propose next ---")
        bo.add_results(str(src))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            bo.run()
        out_name = f"round{i}_proposed.csv"  # i=0 → round0
        out_path = OUT / out_name
        bo.export_proposed(str(out_path))
        proposed = pd.read_csv(out_path, index_col=0)

        # 官方下一轮实测条件（不含 yield）即当时提出的实验
        next_official_name = ROUND_FILES[i + 1] if i + 1 < len(ROUND_FILES) else None
        if next_official_name:
            official_next = pd.read_csv(EXAMPLE / "results" / f"{next_official_name}.csv", index_col=0)
            reports.append(
                compare_conditions(proposed, official_next, f"after {name} → vs official {next_official_name}")
            )
        else:
            print(f"  已导出 {out_name}（无后续官方对照）")

        # 收敛图
        try:
            bo.plot_convergence()
            fig = plt.gcf()
            fig.savefig(OUT / f"convergence_after_{name}.png", dpi=120, bbox_inches="tight")
            plt.close("all")
        except Exception as e:
            print(f"  (跳过收敛图: {e})")

    # 汇总历史最优（官方实测）
    hist = []
    for name in ROUND_FILES[: n_rec_rounds + 1]:
        p = EXAMPLE / "results" / f"{name}.csv"
        if p.is_file():
            hist.append(pd.read_csv(p, index_col=0))
    if hist:
        all_res = pd.concat(hist, sort=False).sort_values("yield", ascending=False)
        all_res.to_csv(OUT / "official_results_used.csv")
        print("\n官方实测 (本复现用到的轮次) Top-5 yield:")
        print(all_res.head().to_string())

    summary = {
        "domain_size": domain_n,
        "expected_domain_size": 312_500,
        "n_recommendation_rounds": n_rec_rounds,
        "comparisons": reports,
        "note": (
            "提案与官方不完全一致时常见：gpytorch/torch 版本、优化随机性与论文当时环境不同。"
            "init(seed=8) 应对齐；后续 GP 推荐可能有偏差。"
        ),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n汇总已写入: {OUT / 'summary.json'}")

    exact_init = reports[0]["exact_set_match"] if reports else False
    if exact_init:
        print("\n[OK] init(seed=8) 与官方完全一致")
    else:
        print("\n[FAIL] init 与官方不一致 — 请检查随机种子/依赖版本")
    print("完成。")


if __name__ == "__main__":
    main()
