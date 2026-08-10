"""Bayesian optimisation primitives: surrogate, acquisition, loop."""

from .acquisition import expected_improvement, upper_confidence_bound, select_next
from .gp_model import SurrogateGP
from .loop import BOLoopResult, run_bo_loop

__all__ = [
    "SurrogateGP",
    "expected_improvement",
    "upper_confidence_bound",
    "select_next",
    "BOLoopResult",
    "run_bo_loop",
]
