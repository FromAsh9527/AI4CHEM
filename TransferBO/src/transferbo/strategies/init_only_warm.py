"""S5 / W9: source labels guide target initialization only (no persistent pooling)."""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from transferbo.bo.loop import run_bo_loop
from transferbo.data.oracle import PlateOracle
from transferbo.representations.base import Representation
from transferbo.strategies.base import (
    BaseStrategy,
    StrategyConfig,
    StrategyResult,
    sample_init_indices,
)


def _align_key(df: pd.DataFrame) -> pd.Series:
    if "candidate_key" in df.columns:
        return df["candidate_key"].astype(str)
    if "smiles" in df.columns:
        return df["smiles"].astype(str)
    raise ValueError("init_only_warm needs candidate_key or smiles to align source→target")


def source_guided_init_indices(
    source_df: pd.DataFrame,
    target_df: pd.DataFrame,
    *,
    n_init: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Map top source conditions onto the shared target library; fill remainder randomly."""
    src_key = _align_key(source_df)
    tgt_key = _align_key(target_df)
    tgt_lookup = {k: i for i, k in enumerate(tgt_key.tolist())}

    order = np.argsort(-source_df["response"].to_numpy(dtype=float), kind="mergesort")
    picked: list[int] = []
    seen: set[int] = set()
    for j in order:
        key = src_key.iloc[int(j)]
        ti = tgt_lookup.get(key)
        if ti is None or ti in seen:
            continue
        picked.append(int(ti))
        seen.add(int(ti))
        if len(picked) >= n_init:
            break

    n = len(target_df)
    if len(picked) < n_init:
        remaining = np.array([i for i in range(n) if i not in seen], dtype=int)
        need = n_init - len(picked)
        if len(remaining) > 0:
            extra = rng.choice(remaining, size=min(need, len(remaining)), replace=False)
            picked.extend(int(x) for x in extra)
    return np.asarray(picked[:n_init], dtype=int)


class InitOnlyWarmStartStrategy(BaseStrategy):
    """Use source rankings only to choose target init indices; then cold BO."""

    name = "init_only_warm"

    def run(
        self,
        *,
        target_oracle: PlateOracle,
        X_target: np.ndarray,
        config: StrategyConfig,
        source_df: Optional[pd.DataFrame] = None,
        X_source: Optional[np.ndarray] = None,
        representation: Optional[Representation] = None,
    ) -> StrategyResult:
        if source_df is None:
            raise ValueError("init_only_warm requires source_df")

        # Separate stream from cold_start so S5 is a distinct init policy,
        # while remaining reproducible given seed.
        init_rng = np.random.default_rng(config.seed + 2_000_003)
        target_df = target_oracle.plate

        init_idx = source_guided_init_indices(
            source_df,
            target_df,
            n_init=config.n_init,
            rng=init_rng,
        )
        if len(init_idx) < config.n_init:
            # pathological: fall back to random fill
            fill = sample_init_indices(target_oracle.n, config.n_init, init_rng)
            init_idx = np.unique(np.concatenate([init_idx, fill]))[: config.n_init]

        bo = run_bo_loop(
            target_oracle,
            X_target,
            init_indices=init_idx,
            budget=config.budget,
            acquisition=config.acquisition,
            batch_size=config.batch_size,
            ucb_beta=config.ucb_beta,
            backend=config.backend,
            normalize_y=config.normalize_y,
            seed=config.seed,
            # deliberately no warm labels
        )
        return StrategyResult(
            name=self.name,
            bo=bo,
            meta={
                "init_indices": init_idx.tolist(),
                "used_source_labels": False,
                "init_from_source_ranking": True,
                "n_source_used": 0,
            },
        )
