"""Build supervised labels for TransferGate from a finished transfer grid."""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from transferbo.gate.policy import label_mode_from_strategy

TRANSFER_STRATEGIES = ("diversity_warm", "label_warm", "multitask")
ALL_MODES = ("off", "diversity_warm", "label_warm", "multitask")


def aggregate_pair_metrics(grid: pd.DataFrame) -> pd.DataFrame:
    """Mean metrics per (source, target, strategy, representation)."""
    df = grid.copy()
    # cold_start rows often have source==target in our grid export
    g = (
        df.groupby(
            ["source_plate", "target_plate", "strategy", "representation"],
            as_index=False,
        )
        .agg(
            frac_mean=("frac_of_opt", "mean"),
            q5_median=("queries_to_top5", "median"),
            n=("frac_of_opt", "count"),
        )
    )
    return g


def cold_baseline(agg: pd.DataFrame) -> pd.DataFrame:
    cold = agg[agg["strategy"] == "cold_start"].copy()
    # Prefer same-plate cold rows; if multiple sources, take mean by target+rep
    cold = (
        cold.groupby(["target_plate", "representation"], as_index=False)
        .agg(cold_frac_mean=("frac_mean", "mean"), cold_q5_median=("q5_median", "median"))
    )
    return cold


def choose_best_mode_row(
    pair_rows: pd.DataFrame,
    cold_frac: float,
    *,
    min_gain: float = 0.02,
) -> dict:
    """Pick best mode for one (source,target,rep).

    Modes considered: off (cold), diversity_warm, label_warm, multitask.
    Prefer transfer only if mean frac beats cold by ``min_gain``.
    """
    best_strat = "off"
    best_frac = float(cold_frac)
    deltas = {}
    for strat in TRANSFER_STRATEGIES:
        sub = pair_rows[pair_rows["strategy"] == strat]
        if sub.empty:
            continue
        frac = float(sub["frac_mean"].iloc[0])
        deltas[strat] = frac - float(cold_frac)
        if frac > best_frac + 1e-12:
            best_frac = frac
            best_strat = strat

    if best_strat != "off" and (best_frac - float(cold_frac)) < min_gain:
        best_strat = "off"
        best_frac = float(cold_frac)

    # classification label vs best transfer (label_warm preferred as reference)
    label_rows = pair_rows[pair_rows["strategy"] == "label_warm"]
    if not label_rows.empty and np.isfinite(label_rows["q5_median"].iloc[0]) and np.isfinite(
        pair_rows.attrs.get("cold_q5", np.nan) if False else True
    ):
        pass

    y_gain = None
    y_cls = "neutral"
    if not label_rows.empty and np.isfinite(cold_frac):
        # use frac ratio as soft gain (higher better); map to cls
        lw = float(label_rows["frac_mean"].iloc[0])
        y_gain = lw / (float(cold_frac) + 1e-8)
        if y_gain > 1.05:
            y_cls = "pos"
        elif y_gain < 0.95:
            y_cls = "neg"
        else:
            y_cls = "neutral"

    mode = label_mode_from_strategy(best_strat) if best_strat != "off" else "off"
    return {
        "y_mode": mode,
        "y_best_frac": best_frac,
        "y_delta_vs_cold": best_frac - float(cold_frac),
        "y_gain_label_vs_cold": y_gain,
        "y_cls": y_cls,
        "delta_diversity": deltas.get("diversity_warm"),
        "delta_label": deltas.get("label_warm"),
        "delta_multitask": deltas.get("multitask"),
    }


def build_label_table(
    grid: pd.DataFrame,
    *,
    min_gain: float = 0.02,
    exclude_targets: Optional[list[str]] = None,
) -> pd.DataFrame:
    """Create one supervised row per (source, target, representation) pair."""
    exclude_targets = exclude_targets or []
    agg = aggregate_pair_metrics(grid)
    cold = cold_baseline(agg)

    # candidate pairs = transfer strategies present
    pairs = (
        agg[agg["strategy"].isin(TRANSFER_STRATEGIES)][
            ["source_plate", "target_plate", "representation"]
        ]
        .drop_duplicates()
    )
    rows = []
    for _, p in pairs.iterrows():
        src, tgt, rep = p["source_plate"], p["target_plate"], p["representation"]
        if tgt in exclude_targets:
            continue
        if src == tgt:
            continue
        pair_rows = agg[
            (agg["source_plate"] == src)
            & (agg["target_plate"] == tgt)
            & (agg["representation"] == rep)
            & (agg["strategy"].isin(TRANSFER_STRATEGIES))
        ]
        c = cold[(cold["target_plate"] == tgt) & (cold["representation"] == rep)]
        if c.empty:
            continue
        cold_frac = float(c["cold_frac_mean"].iloc[0])
        lab = choose_best_mode_row(pair_rows, cold_frac, min_gain=min_gain)
        rows.append(
            {
                "source_plate": src,
                "target_plate": tgt,
                "representation": rep,
                "cold_frac_mean": cold_frac,
                "cold_q5_median": float(c["cold_q5_median"].iloc[0])
                if np.isfinite(c["cold_q5_median"].iloc[0])
                else None,
                **lab,
            }
        )
    return pd.DataFrame(rows)
