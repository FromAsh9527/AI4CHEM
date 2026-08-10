"""Core retrospective BO loop on a discrete candidate pool."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from transferbo.bo.acquisition import select_next
from transferbo.bo.gp_model import SurrogateGP
from transferbo.data.oracle import PlateOracle


def percentile_ranks(y: np.ndarray) -> np.ndarray:
    """Average ranks mapped to (0, 1): rank/(n+1). Ties get average rank."""
    y = np.asarray(y, dtype=np.float64)
    n = len(y)
    if n == 0:
        return y
    order = np.argsort(y, kind="mergesort")
    ranks = np.empty(n, dtype=np.float64)
    i = 0
    while i < n:
        j = i
        while j + 1 < n and y[order[j + 1]] == y[order[i]]:
            j += 1
        # 1-based ranks i+1 .. j+1 → average
        avg = 0.5 * ((i + 1) + (j + 1))
        ranks[order[i : j + 1]] = avg
        i = j + 1
    return ranks / (n + 1.0)


@dataclass
class BOLoopResult:
    queried_indices: list[int] = field(default_factory=list)
    responses: list[float] = field(default_factory=list)
    best_so_far: list[float] = field(default_factory=list)
    n_init: int = 0

    def to_dict(self) -> dict:
        return {
            "queried_indices": self.queried_indices,
            "responses": self.responses,
            "best_so_far": self.best_so_far,
            "n_init": self.n_init,
        }


def run_bo_loop(
    oracle: PlateOracle,
    X: np.ndarray,
    *,
    init_indices: np.ndarray,
    budget: int,
    acquisition: str = "ei",
    batch_size: int = 1,
    ucb_beta: float = 2.0,
    backend: str = "sklearn",
    normalize_y: bool = True,
    seed: int = 0,
    warm_X: Optional[np.ndarray] = None,
    warm_y: Optional[np.ndarray] = None,
    target_pool_mode: str = "raw",
    warm_weight: float = 1.0,
    base_noise: float = 1e-4,
) -> BOLoopResult:
    """Run discrete BO until `budget` target-plate queries are used.

    `budget` counts only target-plate queries (init + acquisitions).
    Optional `warm_X`/`warm_y` are source-plate observations and do not
    count toward the budget.

    `target_pool_mode`:
      - ``raw``: fit GP on raw target yields (+ warm_y as provided).
      - ``rank``: fit GP on percentile ranks of observed target yields;
        ``warm_y`` must already be in the same rank space (A2).

    `warm_weight` (A3): down-weight source points via larger diagonal noise
    ``alpha_source = base_noise / warm_weight`` (target keeps ``base_noise``).
    ``warm_weight=1`` recovers equal-noise pooling (A1).

    Metrics (`best_so_far`, `responses`) always stay in raw yield space.
    """
    X = np.asarray(X, dtype=np.float64)
    init_indices = np.asarray(init_indices, dtype=int)
    pool_mode = (target_pool_mode or "raw").lower()
    if pool_mode not in {"raw", "rank"}:
        raise ValueError(f"Unknown target_pool_mode: {target_pool_mode!r}")
    w_src = float(warm_weight)
    if w_src <= 0:
        raise ValueError(f"warm_weight must be > 0, got {warm_weight}")
    result = BOLoopResult(n_init=len(init_indices))

    y_init = oracle.query(init_indices)
    result.queried_indices = list(map(int, init_indices))
    result.responses = list(map(float, y_init))

    running_best = -np.inf
    result.best_so_far = []
    for y in result.responses:
        running_best = max(running_best, y)
        result.best_so_far.append(running_best)

    warm_y_fit = None
    if warm_X is not None and warm_y is not None and len(warm_y) > 0:
        warm_y_fit = np.asarray(warm_y, dtype=np.float64)

    while len(result.queried_indices) < budget:
        remaining = budget - len(result.queried_indices)
        bs = min(batch_size, remaining)
        unrevealed = oracle.unrevealed_indices()
        if len(unrevealed) == 0:
            break

        train_X = X[np.asarray(result.queried_indices, dtype=int)]
        train_y_raw = np.asarray(result.responses, dtype=np.float64)
        n_tgt = len(train_y_raw)
        if pool_mode == "rank":
            train_y = percentile_ranks(train_y_raw)
            best_f = float(np.max(train_y))
        else:
            train_y = train_y_raw
            best_f = float(np.max(train_y_raw))
        alpha: float | np.ndarray = float(base_noise)
        if warm_X is not None and warm_y_fit is not None and len(warm_y_fit) > 0:
            n_warm = len(warm_y_fit)
            train_X = np.vstack([np.asarray(warm_X, dtype=np.float64), train_X])
            train_y = np.concatenate([warm_y_fit, train_y])
            alpha_src = float(base_noise) / w_src
            alpha = np.concatenate(
                [
                    np.full(n_warm, alpha_src, dtype=np.float64),
                    np.full(n_tgt, float(base_noise), dtype=np.float64),
                ]
            )

        gp = SurrogateGP(backend=backend, normalize_y=normalize_y, random_state=seed)
        gp.fit(train_X, train_y, alpha=alpha)
        pred = gp.predict(X[unrevealed])
        chosen = select_next(
            pred.mean,
            pred.std,
            unrevealed,
            best_f=best_f,
            acquisition=acquisition,
            batch_size=bs,
            ucb_beta=ucb_beta,
        )
        y_new = oracle.query(chosen)
        for idx, y in zip(chosen, y_new):
            result.queried_indices.append(int(idx))
            result.responses.append(float(y))
            running_best = max(running_best, float(y))
            result.best_so_far.append(running_best)

    return result
