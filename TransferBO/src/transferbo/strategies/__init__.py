"""Transfer / warm-start strategies (plan §5: 4 required classes)."""

from .base import StrategyConfig, StrategyResult, run_strategy
from .cold_start import ColdDiversityStrategy, ColdStartStrategy
from .diversity_warm import DiversityWarmStartStrategy
from .init_only_warm import InitOnlyWarmStartStrategy
from .label_rank_warm import LabelRankWarmStartStrategy
from .label_taskid_warm import LabelTaskIdWarmStartStrategy
from .label_warm import LabelWarmStartStrategy
from .label_weight_warm import LabelWeightWarmStartStrategy
from .multitask import SimpleMultiTaskStrategy
from .random_search import RandomStrategy
from .transfer_gate import TransferGateStrategy

STRATEGY_REGISTRY = {
    "cold_start": ColdStartStrategy,
    "cold_diversity": ColdDiversityStrategy,
    "diversity_warm": DiversityWarmStartStrategy,
    "label_warm": LabelWarmStartStrategy,
    "label_rank_warm": LabelRankWarmStartStrategy,
    "label_taskid_warm": LabelTaskIdWarmStartStrategy,
    "init_only_warm": InitOnlyWarmStartStrategy,
    "multitask": SimpleMultiTaskStrategy,
    "random": RandomStrategy,
    "transfer_gate": TransferGateStrategy,
}


def build_strategy(name: str):
    key = name.lower().strip()
    if key.startswith("label_weight_w"):
        token = key[len("label_weight_w") :]
        try:
            w = float(token.replace("p", "."))
        except ValueError as e:
            raise ValueError(f"Cannot parse source weight from {name!r}") from e
        return LabelWeightWarmStartStrategy(source_weight=w)
    if key not in STRATEGY_REGISTRY:
        raise ValueError(f"Unknown strategy {name!r}. Choose from {list(STRATEGY_REGISTRY)}")
    return STRATEGY_REGISTRY[key]()


__all__ = [
    "StrategyConfig",
    "StrategyResult",
    "run_strategy",
    "build_strategy",
    "ColdStartStrategy",
    "ColdDiversityStrategy",
    "DiversityWarmStartStrategy",
    "LabelWarmStartStrategy",
    "LabelRankWarmStartStrategy",
    "LabelWeightWarmStartStrategy",
    "LabelTaskIdWarmStartStrategy",
    "InitOnlyWarmStartStrategy",
    "SimpleMultiTaskStrategy",
    "RandomStrategy",
    "TransferGateStrategy",
    "STRATEGY_REGISTRY",
]
