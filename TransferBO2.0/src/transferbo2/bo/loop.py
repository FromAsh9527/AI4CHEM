"""Sequential BO loop over a finite discrete condition space."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

from transferbo2.bo.gp_model import GPSurrogate, select_next


@dataclass
class BOLoopResult:
    indices: List[int]
    values: List[float]
    best_so_far: List[float]
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "indices": list(self.indices),
            "values": list(self.values),
            "best_so_far": list(self.best_so_far),
            "meta": self.meta,
        }


def run_bo_loop(
    X: np.ndarray,
    y_oracle: np.ndarray,
    init_idx: np.ndarray,
    *,
    budget: int,
    acquisition: str = "ei",
    seed: int = 0,
    warm_X: Optional[np.ndarray] = None,
    warm_y: Optional[np.ndarray] = None,
    warm_w: Optional[np.ndarray] = None,
    normalize_y: bool = True,
) -> BOLoopResult:
    """Finite-space BO. y_oracle is the full lookup table aligned with X rows."""
    n = len(y_oracle)
    budget = min(int(budget), n)
    observed = np.zeros(n, dtype=bool)
    indices: List[int] = []
    values: List[float] = []

    init_idx = np.asarray(init_idx, dtype=int)
    for i in init_idx:
        if observed[i]:
            continue
        observed[i] = True
        indices.append(int(i))
        values.append(float(y_oracle[i]))
        if len(indices) >= budget:
            break

    while len(indices) < budget:
        # build training set
        X_obs = X[np.asarray(indices)]
        y_obs = np.asarray(values, dtype=float)
        if warm_X is not None and warm_y is not None and len(warm_y) > 0:
            X_train = np.vstack([warm_X, X_obs])
            y_train = np.concatenate([np.asarray(warm_y, dtype=float), y_obs])
            if warm_w is not None:
                w = np.concatenate([np.asarray(warm_w, dtype=float), np.ones(len(y_obs))])
            else:
                w = None
        else:
            X_train, y_train, w = X_obs, y_obs, None

        gp = GPSurrogate(normalize_y=normalize_y, seed=seed).fit(X_train, y_train, sample_weight=w)
        mu, std = gp.predict(X)
        best = float(np.max(y_obs))
        nxt = select_next(mu, std, observed, acquisition=acquisition, best=best)
        observed[nxt] = True
        indices.append(nxt)
        values.append(float(y_oracle[nxt]))

    bsf = []
    cur = -np.inf
    for v in values:
        cur = max(cur, v)
        bsf.append(cur)
    return BOLoopResult(indices=indices, values=values, best_so_far=bsf)
