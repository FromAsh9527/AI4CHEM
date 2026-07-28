# -*- coding: utf-8 -*-
"""无模型首轮/补点：random / LHS / Sobol / maximin。"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _encode_factors(meta: pd.DataFrame, factor_keys: list[str]) -> tuple[np.ndarray, list[int]]:
    codes = np.zeros((len(meta), len(factor_keys)), dtype=int)
    nlev: list[int] = []
    for j, key in enumerate(factor_keys):
        _, inv = np.unique(meta[key].astype(str), return_inverse=True)
        codes[:, j] = inv
        nlev.append(int(inv.max()) + 1)
    return codes, nlev


def _tuple_to_row_index(codes: np.ndarray) -> dict[tuple[int, ...], int]:
    m: dict[tuple[int, ...], int] = {}
    for i in range(len(codes)):
        m[tuple(int(codes[i, j]) for j in range(codes.shape[1]))] = i
    return m


def _fill_unique(picked: list[int], seen: set[int], n: int, k: int, rng: np.random.Generator) -> np.ndarray:
    while len(picked) < k:
        j = int(rng.integers(n))
        if j not in seen:
            picked.append(j)
            seen.add(j)
    return np.array(picked[:k], dtype=int)


def no_model_pick_indices(
    meta: pd.DataFrame,
    factor_keys: list[str],
    method: str,
    batch_size: int,
    rng: np.random.Generator,
    exclude: set[int] | None = None,
) -> np.ndarray:
    n = len(meta)
    exclude = exclude or set()
    available = [i for i in range(n) if i not in exclude]
    if not available:
        return np.array([], dtype=int)
    k = min(int(batch_size), len(available))
    d = len(factor_keys)

    if method == "random" or d < 1:
        return rng.choice(available, size=k, replace=False)

    codes, nlev = _encode_factors(meta, factor_keys)
    tup_to_i = _tuple_to_row_index(codes)

    if method == "maximin":
        X = np.zeros((n, d), dtype=np.float64)
        for j in range(d):
            den = max(1, nlev[j] - 1)
            X[:, j] = codes[:, j].astype(np.float64) / den
        start = int(rng.choice(available))
        picked: list[int] = [start]
        picked_set = set(picked)
        while len(picked) < k:
            best_i, best_d = -1, -1.0
            for i in available:
                if i in picked_set:
                    continue
                dist = np.min(np.linalg.norm(X[i] - X[list(picked_set)], axis=1))
                if dist > best_d:
                    best_d, best_i = dist, i
            if best_i < 0:
                break
            picked.append(best_i)
            picked_set.add(best_i)
        return _fill_unique(picked, picked_set, n, k, rng)

    # LHS / Sobol：在 [0,1]^d 采样后映射到水平索引
    if method == "sobol":
        try:
            from scipy.stats import qmc

            sampler = qmc.Sobol(d=d, scramble=True, seed=int(rng.integers(1e9)))
            # Sobol 要求 2^m；多采再筛
            m = int(np.ceil(np.log2(max(k * 4, 8))))
            unit = sampler.random_base2(m=m)
        except Exception:
            unit = rng.random((k * 4, d))
    else:
        # latin hypercube
        try:
            from scipy.stats import qmc

            sampler = qmc.LatinHypercube(d=d, seed=int(rng.integers(1e9)))
            unit = sampler.random(n=max(k * 4, k))
        except Exception:
            unit = rng.random((k * 4, d))

    picked: list[int] = []
    seen: set[int] = set()
    for u in unit:
        idxs = []
        for j in range(d):
            idxs.append(min(nlev[j] - 1, int(u[j] * nlev[j])))
        t = tuple(idxs)
        i = tup_to_i.get(t)
        if i is None or i in exclude or i in seen:
            continue
        picked.append(i)
        seen.add(i)
        if len(picked) >= k:
            break
    return _fill_unique(picked, seen | exclude, n, k, rng)


def no_model_recommend(
    meta: pd.DataFrame,
    factor_keys: list[str],
    method: str = "lhs",
    batch_size: int = 5,
    seed: int = 0,
    history: pd.DataFrame | None = None,
    factors=None,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    exclude: set[int] = set()
    if history is not None and not history.empty:
        if factors is not None:
            from domain_builder import row_key

            done = {row_key(r, factors) for _, r in history.iterrows()}
            for i in meta.index:
                if row_key(meta.loc[i], factors) in done:
                    exclude.add(int(i))
        else:
            m = meta.copy()
            for k in factor_keys:
                m[k] = m[k].astype(str)
            h = history.copy()
            for k in factor_keys:
                h[k] = h[k].astype(str)
            m["_key"] = list(zip(*[m[k] for k in factor_keys]))
            done = set(zip(*[h[k] for k in factor_keys]))
            for i, key in enumerate(m["_key"]):
                if key in done:
                    exclude.add(i)

    idx = no_model_pick_indices(meta, factor_keys, method, batch_size, rng, exclude=exclude)
    rec = meta.iloc[idx].copy().reset_index(drop=True)
    rec.insert(0, "rank", range(1, len(rec) + 1))
    return rec
