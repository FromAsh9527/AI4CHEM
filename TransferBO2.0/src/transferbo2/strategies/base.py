"""Strategy interfaces and registry."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Optional, Type

import numpy as np
import pandas as pd

from transferbo2.bo.loop import BOLoopResult


@dataclass
class StrategyConfig:
    n_init: int = 5
    budget: int = 20
    acquisition: str = "ei"
    seed: int = 0
    topk: int = 5
    max_warm_points: int = 120
    lengthscale_sub: float = 1.0
    gate_spearman_min: float = 0.2
    use_plate_correction: bool = True
    normalize_y: bool = True


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
        X_target: np.ndarray,
        y_target: np.ndarray,
        condition_ids_target: np.ndarray,
        hist_df: pd.DataFrame,
        X_hist: np.ndarray,
        desc_by_id: Dict[str, np.ndarray],
        target_substrate: str,
        config: StrategyConfig,
    ) -> StrategyResult:
        ...


def sample_init(n: int, n_init: int, rng: np.random.Generator) -> np.ndarray:
    n_init = min(n_init, n)
    return rng.choice(n, size=n_init, replace=False)


_REGISTRY: Dict[str, Type[BaseStrategy]] = {}


def register(cls: Type[BaseStrategy]) -> Type[BaseStrategy]:
    _REGISTRY[cls.name] = cls
    return cls


def get_strategy(name: str) -> BaseStrategy:
    if name not in _REGISTRY:
        # lazy import
        import transferbo2.strategies  # noqa: F401

    if name not in _REGISTRY:
        raise KeyError(f"Unknown strategy {name}. Available: {sorted(_REGISTRY)}")
    return _REGISTRY[name]()


def available_strategies() -> list[str]:
    import transferbo2.strategies  # noqa: F401

    return sorted(_REGISTRY)
