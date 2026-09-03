"""Concrete transfer / baseline strategies."""

from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from transferbo2.bo.loop import run_bo_loop
from transferbo2.descriptors.features import substrate_similarity_map
from transferbo2.plate.effects import anchor_plate_offsets, apply_plate_offsets
from transferbo2.strategies.base import (
    BaseStrategy,
    StrategyConfig,
    StrategyResult,
    register,
    sample_init,
)


def _response_col(df: pd.DataFrame, use_corr: bool) -> str:
    if use_corr and "yield_corr" in df.columns:
        return "yield_corr"
    return "yield"


def _maybe_correct(hist_df: pd.DataFrame, use: bool) -> pd.DataFrame:
    if not use:
        return hist_df
    if hist_df["is_anchor"].sum() < 2:
        return hist_df
    off = anchor_plate_offsets(hist_df)
    return apply_plate_offsets(hist_df, off)


def _subsample_hist(df: pd.DataFrame, max_n: int, rng: np.random.Generator) -> pd.DataFrame:
    if max_n <= 0 or len(df) <= max_n:
        return df
    idx = rng.choice(len(df), size=max_n, replace=False)
    return df.iloc[idx]


@register
class RandomSearch(BaseStrategy):
    name = "random"

    def run(self, *, X_target, y_target, condition_ids_target, hist_df, X_hist, desc_by_id, target_substrate, config):
        rng = np.random.default_rng(config.seed)
        order = rng.permutation(len(y_target))[: config.budget]
        values = [float(y_target[i]) for i in order]
        from transferbo2.bo.loop import BOLoopResult

        bsf, cur = [], -np.inf
        for v in values:
            cur = max(cur, v)
            bsf.append(cur)
        return StrategyResult(self.name, BOLoopResult(list(map(int, order)), values, bsf))


@register
class ColdStart(BaseStrategy):
    name = "cold_start"

    def run(self, *, X_target, y_target, condition_ids_target, hist_df, X_hist, desc_by_id, target_substrate, config):
        rng = np.random.default_rng(config.seed)
        init = sample_init(len(y_target), config.n_init, rng)
        bo = run_bo_loop(
            X_target,
            y_target,
            init,
            budget=config.budget,
            acquisition=config.acquisition,
            seed=config.seed,
            normalize_y=config.normalize_y,
        )
        return StrategyResult(self.name, bo)


@register
class TopKWarm(BaseStrategy):
    name = "topk_warm"

    def run(self, *, X_target, y_target, condition_ids_target, hist_df, X_hist, desc_by_id, target_substrate, config):
        rng = np.random.default_rng(config.seed)
        hist = _maybe_correct(hist_df, config.use_plate_correction)
        col = _response_col(hist, config.use_plate_correction)
        # mean yield per condition across history
        rank = hist.groupby("condition_id")[col].mean().sort_values(ascending=False)
        id_to_idx = {cid: i for i, cid in enumerate(condition_ids_target)}
        init = []
        for cid in rank.index:
            if cid in id_to_idx:
                init.append(id_to_idx[cid])
            if len(init) >= config.topk:
                break
        # fill remaining init randomly if needed
        if len(init) < config.n_init:
            extra = sample_init(len(y_target), config.n_init, rng)
            for e in extra:
                if e not in init:
                    init.append(int(e))
                if len(init) >= config.n_init:
                    break
        bo = run_bo_loop(
            X_target,
            y_target,
            np.asarray(init[: config.n_init], dtype=int),
            budget=config.budget,
            acquisition=config.acquisition,
            seed=config.seed,
            normalize_y=config.normalize_y,
        )
        return StrategyResult(self.name, bo, meta={"init_from_topk": True})


@register
class NearestTopKWarm(BaseStrategy):
    name = "nearest_topk_warm"

    def run(self, *, X_target, y_target, condition_ids_target, hist_df, X_hist, desc_by_id, target_substrate, config):
        rng = np.random.default_rng(config.seed)
        hist = _maybe_correct(hist_df, config.use_plate_correction)
        sources = [s for s in hist["substrate_id"].unique() if s != target_substrate]
        sims = substrate_similarity_map(desc_by_id, target_substrate, sources, lengthscale=config.lengthscale_sub)
        if not sims:
            return ColdStart().run(
                X_target=X_target,
                y_target=y_target,
                condition_ids_target=condition_ids_target,
                hist_df=hist_df,
                X_hist=X_hist,
                desc_by_id=desc_by_id,
                target_substrate=target_substrate,
                config=config,
            )
        nearest = max(sims, key=sims.get)
        col = _response_col(hist, config.use_plate_correction)
        sub = hist[hist["substrate_id"] == nearest]
        rank = sub.groupby("condition_id")[col].mean().sort_values(ascending=False)
        id_to_idx = {cid: i for i, cid in enumerate(condition_ids_target)}
        init = [id_to_idx[c] for c in rank.index if c in id_to_idx][: config.n_init]
        if len(init) < config.n_init:
            init = list(init) + list(sample_init(len(y_target), config.n_init, rng))
            # unique preserve order
            seen = set()
            uniq = []
            for i in init:
                if int(i) not in seen:
                    seen.add(int(i))
                    uniq.append(int(i))
            init = uniq[: config.n_init]
        bo = run_bo_loop(
            X_target,
            y_target,
            np.asarray(init, dtype=int),
            budget=config.budget,
            acquisition=config.acquisition,
            seed=config.seed,
            normalize_y=config.normalize_y,
        )
        return StrategyResult(self.name, bo, meta={"nearest": nearest, "sim": sims[nearest]})


@register
class Pooled(BaseStrategy):
    name = "pooled"

    def run(self, *, X_target, y_target, condition_ids_target, hist_df, X_hist, desc_by_id, target_substrate, config):
        rng = np.random.default_rng(config.seed)
        hist = _maybe_correct(hist_df, config.use_plate_correction)
        hist = _subsample_hist(hist, config.max_warm_points, rng)
        col = _response_col(hist, config.use_plate_correction)
        # map hist rows to X_hist — X_hist must align with hist_df original order;
        # rebuild by condition feature table alignment: use provided X_hist rows matching hist index if same length
        if len(X_hist) != len(hist_df):
            # fall back: warm only by matching condition features already built for full hist_df then subsample indices
            raise ValueError("X_hist must align with hist_df rows")
        # After correction/subsample, take corresponding rows from original alignment via experiment_id
        # Simpler approach: subsample indices from original hist_df
        hist_full = _maybe_correct(hist_df, config.use_plate_correction)
        idx = np.arange(len(hist_full))
        if config.max_warm_points > 0 and len(idx) > config.max_warm_points:
            idx = rng.choice(idx, size=config.max_warm_points, replace=False)
        warm_X = X_hist[idx]
        warm_y = hist_full.iloc[idx][col].to_numpy(dtype=float)
        init = sample_init(len(y_target), config.n_init, rng)
        bo = run_bo_loop(
            X_target,
            y_target,
            init,
            budget=config.budget,
            acquisition=config.acquisition,
            seed=config.seed,
            warm_X=warm_X,
            warm_y=warm_y,
            normalize_y=config.normalize_y,
        )
        return StrategyResult(self.name, bo, meta={"n_warm": int(len(warm_y))})


@register
class SimWeighted(BaseStrategy):
    name = "sim_weighted"

    def run(self, *, X_target, y_target, condition_ids_target, hist_df, X_hist, desc_by_id, target_substrate, config):
        rng = np.random.default_rng(config.seed)
        hist_full = _maybe_correct(hist_df, config.use_plate_correction)
        col = _response_col(hist_full, config.use_plate_correction)
        sources = [s for s in hist_full["substrate_id"].unique() if s != target_substrate]
        sims = substrate_similarity_map(desc_by_id, target_substrate, sources, lengthscale=config.lengthscale_sub)
        w_row = hist_full["substrate_id"].map(lambda s: sims.get(s, 0.0)).to_numpy(dtype=float)
        idx = np.arange(len(hist_full))
        if config.max_warm_points > 0 and len(idx) > config.max_warm_points:
            # prefer high-similarity rows
            prob = w_row + 1e-6
            prob = prob / prob.sum()
            idx = rng.choice(idx, size=config.max_warm_points, replace=False, p=prob)
        warm_X = X_hist[idx]
        warm_y = hist_full.iloc[idx][col].to_numpy(dtype=float)
        warm_w = w_row[idx]
        init = sample_init(len(y_target), config.n_init, rng)
        bo = run_bo_loop(
            X_target,
            y_target,
            init,
            budget=config.budget,
            acquisition=config.acquisition,
            seed=config.seed,
            warm_X=warm_X,
            warm_y=warm_y,
            warm_w=warm_w,
            normalize_y=config.normalize_y,
        )
        return StrategyResult(self.name, bo, meta={"sims": sims, "n_warm": int(len(warm_y))})


@register
class Contextual(BaseStrategy):
    name = "contextual"

    def run(self, *, X_target, y_target, condition_ids_target, hist_df, X_hist, desc_by_id, target_substrate, config):
        """Append substrate descriptors to condition features for hist and target."""
        rng = np.random.default_rng(config.seed)
        hist_full = _maybe_correct(hist_df, config.use_plate_correction)
        col = _response_col(hist_full, config.use_plate_correction)
        dim = len(next(iter(desc_by_id.values()))) if desc_by_id else 1
        zero = np.zeros(dim)

        def aug(X, sids):
            phis = np.vstack([desc_by_id.get(s, zero) for s in sids])
            return np.hstack([X, phis])

        Xh = aug(X_hist, hist_full["substrate_id"].tolist())
        Xt = aug(X_target, [target_substrate] * len(X_target))
        idx = np.arange(len(hist_full))
        if config.max_warm_points > 0 and len(idx) > config.max_warm_points:
            idx = rng.choice(idx, size=config.max_warm_points, replace=False)
        init = sample_init(len(y_target), config.n_init, rng)
        bo = run_bo_loop(
            Xt,
            y_target,
            init,
            budget=config.budget,
            acquisition=config.acquisition,
            seed=config.seed,
            warm_X=Xh[idx],
            warm_y=hist_full.iloc[idx][col].to_numpy(dtype=float),
            normalize_y=config.normalize_y,
        )
        return StrategyResult(self.name, bo, meta={"n_warm": int(len(idx))})


@register
class PlateAware(BaseStrategy):
    name = "plate_aware"

    def run(self, *, X_target, y_target, condition_ids_target, hist_df, X_hist, desc_by_id, target_substrate, config):
        """Contextual features + plate id one-hot as additive covariates; always correct anchors."""
        cfg = StrategyConfig(**{**config.__dict__, "use_plate_correction": True})
        rng = np.random.default_rng(cfg.seed)
        hist_full = _maybe_correct(hist_df, True)
        col = _response_col(hist_full, True)
        plates = sorted(hist_full["plate_id"].unique())
        plate_index = {p: i for i, p in enumerate(plates)}
        dim = len(next(iter(desc_by_id.values()))) if desc_by_id else 1
        zero = np.zeros(dim)

        def aug(X, sids, pids):
            phis = np.vstack([desc_by_id.get(s, zero) for s in sids])
            oh = np.zeros((len(sids), len(plates)))
            for i, p in enumerate(pids):
                if p in plate_index:
                    oh[i, plate_index[p]] = 1.0
            return np.hstack([X, phis, oh])

        Xh = aug(X_hist, hist_full["substrate_id"].tolist(), hist_full["plate_id"].tolist())
        # target plate unknown / new: zero plate one-hot
        Xt = aug(X_target, [target_substrate] * len(X_target), [None] * len(X_target))
        idx = np.arange(len(hist_full))
        if cfg.max_warm_points > 0 and len(idx) > cfg.max_warm_points:
            idx = rng.choice(idx, size=cfg.max_warm_points, replace=False)
        init = sample_init(len(y_target), cfg.n_init, rng)
        bo = run_bo_loop(
            Xt,
            y_target,
            init,
            budget=cfg.budget,
            acquisition=cfg.acquisition,
            seed=cfg.seed,
            warm_X=Xh[idx],
            warm_y=hist_full.iloc[idx][col].to_numpy(dtype=float),
            normalize_y=cfg.normalize_y,
        )
        return StrategyResult(self.name, bo, meta={"n_warm": int(len(idx)), "n_plates": len(plates)})


@register
class SafeGate(BaseStrategy):
    name = "safe_gate"

    def run(self, *, X_target, y_target, condition_ids_target, hist_df, X_hist, desc_by_id, target_substrate, config):
        """Gate sources by Spearman agreement on init conditions; else fall back to cold_start."""
        rng = np.random.default_rng(config.seed)
        init = sample_init(len(y_target), config.n_init, rng)
        # evaluate gating using init observations
        id_to_y = {cid: float(y) for cid, y in zip(condition_ids_target[init], y_target[init])}
        hist_full = _maybe_correct(hist_df, True)
        col = _response_col(hist_full, True)
        sources = [s for s in hist_full["substrate_id"].unique() if s != target_substrate]
        allowed = []
        gate_stats = {}
        for s in sources:
            sub = hist_full[hist_full["substrate_id"] == s]
            pred = sub.groupby("condition_id")[col].mean()
            xs, ys = [], []
            for cid, yt in id_to_y.items():
                if cid in pred.index:
                    xs.append(yt)
                    ys.append(float(pred.loc[cid]))
            if len(xs) >= 3:
                rho, _ = spearmanr(xs, ys)
                rho = float(rho) if rho == rho else -1.0
            else:
                rho = -1.0
            gate_stats[s] = rho
            if rho >= config.gate_spearman_min:
                allowed.append(s)

        if not allowed:
            cold = ColdStart().run(
                X_target=X_target,
                y_target=y_target,
                condition_ids_target=condition_ids_target,
                hist_df=hist_df,
                X_hist=X_hist,
                desc_by_id=desc_by_id,
                target_substrate=target_substrate,
                config=config,
            )
            cold.meta = {**cold.meta, "gated": False, "gate_stats": gate_stats}
            cold.name = self.name
            return cold

        mask = hist_df["substrate_id"].isin(allowed).to_numpy()
        res = SimWeighted().run(
            X_target=X_target,
            y_target=y_target,
            condition_ids_target=condition_ids_target,
            hist_df=hist_df.loc[mask].reset_index(drop=True),
            X_hist=X_hist[mask],
            desc_by_id=desc_by_id,
            target_substrate=target_substrate,
            config=config,
        )
        res.name = self.name
        res.meta = {**res.meta, "gated": True, "allowed": allowed, "gate_stats": gate_stats}
        return res
