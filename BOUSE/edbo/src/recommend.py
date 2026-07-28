# -*- coding: utf-8 -*-
"""推荐入口：无模型 / 贝叶斯（edbo.BO）。"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT / "edbo-master") not in sys.path:
    sys.path.insert(0, str(_ROOT / "edbo-master"))

from edbo.bro import BO  # noqa: E402

from domain_builder import build_domain, history_to_results, row_key, sanitize_for_gp
from factors import FactorSpec, factor_keys
from init_design import no_model_recommend


def subsample_for_bo(
    meta: pd.DataFrame,
    domain_num: pd.DataFrame,
    factors: list[FactorSpec],
    history: pd.DataFrame,
    cap: int,
    seed: int = 0,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """ExactGP 在超大候选集上会爆内存：保留历史点 + 随机补齐至 cap。"""
    n = len(meta)
    if cap is None or cap <= 0 or n <= cap:
        return meta, domain_num, {"domain_cap": n, "subsampled": False}

    hist_keys = {row_key(r, factors) for _, r in history.iterrows()}
    must = [int(i) for i in meta.index if row_key(meta.loc[i], factors) in hist_keys]
    must_set = set(must)
    rest = [int(i) for i in meta.index if int(i) not in must_set]
    rng = np.random.default_rng(seed)
    n_extra = max(0, int(cap) - len(must))
    if n_extra > 0 and rest:
        pick = rng.choice(rest, size=min(n_extra, len(rest)), replace=False)
        chosen = sorted(set(must).union(int(x) for x in pick))
    else:
        chosen = sorted(must)

    meta2 = meta.loc[chosen].reset_index(drop=True)
    domain2 = domain_num.loc[chosen].reset_index(drop=True)
    return meta2, domain2, {
        "domain_cap": int(cap),
        "subsampled": True,
        "full_domain_size": n,
        "bo_domain_size": len(meta2),
        "n_forced_history": len(must),
    }


def recommend_nomodel(
    ws: Path,
    factors: list[FactorSpec],
    history: pd.DataFrame,
    batch_size: int,
    method: str = "lhs",
    seed: int = 0,
) -> tuple[pd.DataFrame, dict]:
    meta, _domain_num, info = build_domain(ws, factors)
    keys = factor_keys(factors)
    rec = no_model_recommend(
        meta,
        keys,
        method=method,
        batch_size=batch_size,
        seed=seed,
        history=history,
        factors=factors,
    )
    info = dict(info)
    info["mode"] = "nomodel"
    info["nomodel_method"] = method
    return rec, info


def recommend_bo(
    ws: Path,
    factors: list[FactorSpec],
    history: pd.DataFrame,
    target_col: str,
    batch_size: int,
    acquisition_function: str = "EI",
    training_iters: int = 100,
    noise_constraint: float = 0.01,
    n_restarts: int = 2,
    domain_cap: int = 2500,
    seed: int = 0,
) -> tuple[pd.DataFrame, dict]:
    if history is None or history.empty:
        raise ValueError("贝叶斯推荐需要至少 1 条历史结果")

    meta, domain_num, info = build_domain(ws, factors)
    meta, domain_num, sub_info = subsample_for_bo(
        meta, domain_num, factors, history, cap=domain_cap, seed=seed
    )
    results = history_to_results(history, meta, domain_num, factors, target_col)
    domain_s, results_s, _ = sanitize_for_gp(domain_num, results, target_col)

    batch_size = max(1, min(int(batch_size), len(domain_s)))
    bo = BO(
        domain=domain_s,
        results=results_s,
        acquisition_function=acquisition_function,
        init_method="rand",
        target=target_col,
        batch_size=batch_size,
        duplicate_experiments=False,
        fast_comp=True,
        noise_constraint=float(noise_constraint),
    )
    bo.run(n_restarts=n_restarts, learning_rate=0.1, training_iters=int(training_iters))
    prop_idx = bo.proposed_experiments.index
    rec = meta.loc[prop_idx].copy().reset_index(drop=True)
    rec.insert(0, "rank", range(1, len(rec) + 1))

    info = dict(info)
    info.update(sub_info)
    info["mode"] = "bo"
    info["acquisition_function"] = acquisition_function
    info["n_history"] = len(history)
    return rec, info
