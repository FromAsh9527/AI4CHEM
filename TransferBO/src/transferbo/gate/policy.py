"""Gate decision policy: prediction → (mode, strength)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Mapping, Optional


MODE_TO_STRATEGY = {
    "off": "cold_start",
    "cold_start": "cold_start",
    "diversity_warm": "diversity_warm",
    "label_warm": "label_warm",
    "multitask": "multitask",
}

STRATEGY_TO_MODE = {
    "cold_start": "off",
    "diversity_warm": "diversity_warm",
    "label_warm": "label_warm",
    "multitask": "multitask",
}


@dataclass
class GateDecision:
    mode: str  # off | diversity_warm | label_warm | multitask
    strategy: str
    strength: float
    score: float
    probs: dict
    reason: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def decide_from_prediction(
    *,
    mode: str,
    probs: Mapping[str, float],
    source_fraction: float = 1.0,
    neg_threshold: float = 0.45,
    force_off_if_diversity_prob_high: bool = False,
) -> GateDecision:
    """Map classifier output to an executable strategy.

    Uses predicted mode (argmax). Diversity warm-start is only honored when its
    probability is clearly high; W3 showed it was systematically harmful here.
    ``neg_threshold`` retained for API compatibility / future calibrated off gate.
    """
    probs = {str(k): float(v) for k, v in probs.items()}
    mode = str(mode)
    if mode in ("cold_start", "off"):
        mode = "off"

    # Prefer explicit argmax from probs when available
    if probs:
        top_mode = max(probs.items(), key=lambda kv: kv[1])[0]
        if top_mode in ("cold_start", "off"):
            mode = "off"
        elif top_mode in MODE_TO_STRATEGY:
            mode = top_mode

    p_div = probs.get("diversity_warm", 0.0)
    p_off = probs.get("off", probs.get("cold_start", 0.0))
    score = float(max(probs.values()) if probs else 0.0)
    reason = "argmax"

    # Optional calibrated off: only if off clearly dominates (not soft ties)
    if mode != "off" and p_off >= max(neg_threshold, score + 0.05):
        mode = "off"
        reason = f"off_dominates(p_off={p_off:.2f})"

    if mode == "diversity_warm" and p_div < 0.60:
        mode = "off"
        reason = f"diversity_low_conf→off(p_div={p_div:.2f})"
    elif force_off_if_diversity_prob_high and p_div >= 0.5:
        mode = "off"
        reason = "safety_block_diversity"

    strategy = MODE_TO_STRATEGY.get(mode, "cold_start")
    strength = 0.0 if strategy == "cold_start" else float(np_clip(source_fraction, 0.0, 1.0))
    return GateDecision(
        mode=mode if mode != "cold_start" else "off",
        strategy=strategy,
        strength=strength,
        score=score,
        probs=probs,
        reason=reason,
    )


def np_clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(x)))


def label_mode_from_strategy(strategy: str) -> str:
    return STRATEGY_TO_MODE.get(strategy, strategy)
