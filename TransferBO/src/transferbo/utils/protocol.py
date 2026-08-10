"""Merge experiment config with frozen protocol (held-out, seeds, fairness)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from transferbo.utils.config import deep_update, load_config

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PROTOCOL = ROOT / "configs" / "protocol.yaml"


def load_protocol(path: str | Path | None = None) -> dict[str, Any]:
    p = Path(path) if path else DEFAULT_PROTOCOL
    if not p.exists():
        return {}
    return load_config(p)


def apply_protocol(cfg: dict[str, Any], protocol: dict[str, Any] | None = None) -> dict[str, Any]:
    """Inject fairness defaults from protocol without wiping explicit overrides."""
    protocol = protocol if protocol is not None else load_protocol()
    if not protocol:
        return cfg

    out = dict(cfg)
    fair = protocol.get("fairness", {})
    if "seeds" not in out and "seeds" in fair:
        out["seeds"] = list(fair["seeds"])

    bo = dict(out.get("bo", {}))
    strat = dict(out.get("strategy", {}))
    metrics = dict(out.get("metrics", {}))

    bo.setdefault("budget", fair.get("budget_main", 100))
    bo.setdefault("acquisition", fair.get("acquisition", "ei"))
    bo.setdefault("backend", fair.get("backend_main", "sklearn"))
    strat.setdefault("n_init", fair.get("n_init_main", 20))
    strat.setdefault("batch_size", fair.get("batch_size", 1))
    metrics.setdefault("top_fracs", protocol.get("metrics", {}).get("top_fracs", [0.01, 0.05]))

    out["bo"] = bo
    out["strategy"] = strat
    out["metrics"] = metrics
    out["protocol"] = {
        "held_out_target": protocol.get("held_out", {}).get("target_plate"),
        "dev_targets": protocol.get("dev_targets", []),
        "negative_transfer_max": protocol.get("metrics", {}).get("negative_transfer_max"),
        "positive_transfer_min": protocol.get("metrics", {}).get("positive_transfer_min"),
    }
    return out


def assert_not_tuning_heldout(
    *,
    target: str,
    protocol: dict[str, Any] | None = None,
    allow_heldout_eval: bool = False,
    purpose: str = "run",
) -> None:
    """Block accidental use of held-out target during method development."""
    protocol = protocol if protocol is not None else load_protocol()
    held = str(protocol.get("held_out", {}).get("target_plate", "")).strip()
    if not held:
        return
    if str(target) != held:
        return
    if allow_heldout_eval:
        return
    raise RuntimeError(
        f"Refusing {purpose} on held-out target {held!r}. "
        "Pass --allow-heldout only for the frozen final evaluation "
        "(see configs/protocol.yaml)."
    )
