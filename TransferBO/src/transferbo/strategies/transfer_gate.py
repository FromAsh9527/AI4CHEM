"""TransferGate strategy: decide mode, then delegate to a concrete strategy."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from transferbo.data.oracle import PlateOracle
from transferbo.gate.features import GateFeatureInputs, compute_gate_features
from transferbo.gate.model import load_gate_model
from transferbo.representations.base import Representation
from transferbo.strategies.base import BaseStrategy, StrategyConfig, StrategyResult
from transferbo.strategies.cold_start import ColdStartStrategy
from transferbo.strategies.diversity_warm import DiversityWarmStartStrategy
from transferbo.strategies.label_warm import LabelWarmStartStrategy
from transferbo.strategies.multitask import SimpleMultiTaskStrategy

_DELEGATES = {
    "cold_start": ColdStartStrategy,
    "diversity_warm": DiversityWarmStartStrategy,
    "label_warm": LabelWarmStartStrategy,
    "multitask": SimpleMultiTaskStrategy,
}


class TransferGateStrategy(BaseStrategy):
    name = "transfer_gate"

    def __init__(self, model_dir: str | Path | None = None) -> None:
        self.model_dir = Path(model_dir) if model_dir else None

    def run(
        self,
        *,
        target_oracle: PlateOracle,
        X_target: np.ndarray,
        config: StrategyConfig,
        source_df: Optional[pd.DataFrame] = None,
        X_source: Optional[np.ndarray] = None,
        representation: Optional[Representation] = None,
        gate_model_dir: str | Path | None = None,
        representation_name: str = "morgan",
        neg_threshold: float = 0.45,
    ) -> StrategyResult:
        if source_df is None or X_source is None:
            raise ValueError("transfer_gate requires source_df and X_source")

        model_path = gate_model_dir or self.model_dir
        if model_path is None:
            raise ValueError(
                "transfer_gate needs a frozen model dir "
                "(gate_model_dir=... or TransferGateStrategy(model_dir=...))"
            )
        model = load_gate_model(model_path)

        feat = compute_gate_features(
            GateFeatureInputs(
                X_source=np.asarray(X_source, dtype=np.float64),
                y_source=source_df["response"].to_numpy(dtype=float),
                X_target=np.asarray(X_target, dtype=np.float64),
                representation=representation_name,
                source_fraction=config.source_fraction,
                seed=config.seed,
            )
        )
        decision = model.decide(
            feat,
            source_fraction=config.source_fraction,
            neg_threshold=neg_threshold,
        )

        # Apply strength as source_fraction for label/multitask paths
        cfg = StrategyConfig(
            n_init=config.n_init,
            budget=config.budget,
            acquisition=config.acquisition,
            batch_size=config.batch_size,
            ucb_beta=config.ucb_beta,
            backend=config.backend,
            normalize_y=config.normalize_y,
            seed=config.seed,
            source_fraction=decision.strength if decision.strategy != "cold_start" else config.source_fraction,
            init_mode=config.init_mode,
            max_warm_points=config.max_warm_points,
        )

        delegate_cls = _DELEGATES[decision.strategy]
        inner = delegate_cls().run(
            target_oracle=target_oracle,
            X_target=X_target,
            config=cfg,
            source_df=source_df,
            X_source=X_source,
            representation=representation,
        )
        meta = dict(inner.meta)
        meta.update(
            {
                "gate_mode": decision.mode,
                "gate_strategy": decision.strategy,
                "gate_score": decision.score,
                "gate_strength": decision.strength,
                "gate_reason": decision.reason,
                "gate_probs": decision.probs,
                "gate_features": feat,
                "delegated_strategy": inner.name,
            }
        )
        return StrategyResult(name=self.name, bo=inner.bo, meta=meta)
