"""Shared strategy interfaces and runner."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from transferbo.bo.loop import BOLoopResult, run_bo_loop
from transferbo.data.oracle import PlateOracle
from transferbo.representations.base import Representation


@dataclass
class StrategyConfig:
    n_init: int = 20
    budget: int = 100
    acquisition: str = "ei"
    batch_size: int = 1
    ucb_beta: float = 2.0
    backend: str = "sklearn"
    normalize_y: bool = True
    seed: int = 0
    source_fraction: float = 1.0
    init_mode: str = "random"  # random | diversity
    max_warm_points: int = 150  # subsample source labels for tractable GP


@dataclass
class StrategyResult:
    name: str
    bo: BOLoopResult
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"name": self.name, "bo": self.bo.to_dict(), "meta": self.meta}


class BaseStrategy(ABC):
    name: str = "base"

    @abstractmethod
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
        ...


def sample_init_indices(n: int, n_init: int, rng: np.random.Generator) -> np.ndarray:
    n_init = min(n_init, n)
    return rng.choice(n, size=n_init, replace=False)


def select_source_indices(
    n_src: int,
    *,
    source_fraction: float,
    max_warm_points: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Subsample source plate indices for tractable warm-start GPs."""
    n_keep = max(1, int(np.floor(n_src * float(source_fraction))))
    n_keep = min(n_keep, n_src)
    if max_warm_points is not None and max_warm_points > 0:
        n_keep = min(n_keep, int(max_warm_points))
    return rng.choice(n_src, size=n_keep, replace=False)


def diversity_init_indices(
    X_target: np.ndarray,
    n_init: int,
    rng: np.random.Generator,
    *,
    X_ref: Optional[np.ndarray] = None,
) -> np.ndarray:
    """Farthest-point sampling; optionally seeded by source-plate coverage."""
    n = X_target.shape[0]
    n_init = min(n_init, n)
    if n_init <= 0:
        return np.array([], dtype=int)

    # Start from a random target point, or the target point closest to a random source point
    if X_ref is not None and len(X_ref) > 0:
        src = X_ref[rng.integers(0, len(X_ref))]
        d0 = np.linalg.norm(X_target - src, axis=1)
        first = int(np.argmin(d0))
    else:
        first = int(rng.integers(0, n))

    selected = [first]
    min_dist = np.linalg.norm(X_target - X_target[first], axis=1)
    for _ in range(1, n_init):
        nxt = int(np.argmax(min_dist))
        selected.append(nxt)
        dist_new = np.linalg.norm(X_target - X_target[nxt], axis=1)
        min_dist = np.minimum(min_dist, dist_new)
    return np.asarray(selected, dtype=int)


def run_strategy(strategy: BaseStrategy, **kwargs) -> StrategyResult:
    return strategy.run(**kwargs)
