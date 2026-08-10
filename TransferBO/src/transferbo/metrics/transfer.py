"""Transfer-gain heatmap helpers (source → target)."""

from __future__ import annotations

from typing import Mapping

import numpy as np
import pandas as pd


def speedup_vs_baseline(
    queries_method: np.ndarray,
    queries_baseline: np.ndarray,
) -> float:
    """Relative speedup: baseline_median / method_median ( >1 means faster )."""
    m = np.nanmedian(queries_method)
    b = np.nanmedian(queries_baseline)
    if not np.isfinite(m) or m <= 0:
        return float("nan")
    return float(b / m)


def transfer_gain_matrix(
    records: list[dict],
    *,
    value_key: str = "queries_to_top5",
    baseline_strategy: str = "cold_start",
) -> pd.DataFrame:
    """Build source×target gain matrix vs cold-start on the same target.

    Each record should contain:
      source_plate, target_plate, strategy, representation, and `value_key`
      (e.g. median queries to top-5%).
    Gain = baseline_value / method_value  (higher = better / fewer queries).
    """
    df = pd.DataFrame(records)
    if df.empty:
        return pd.DataFrame()

    needed = {"source_plate", "target_plate", "strategy", value_key}
    missing = needed - set(df.columns)
    if missing:
        raise ValueError(f"records missing columns: {missing}")

    baselines = (
        df[df["strategy"] == baseline_strategy]
        .groupby("target_plate")[value_key]
        .median()
    )

    rows = []
    for _, r in df.iterrows():
        b = baselines.get(r["target_plate"], np.nan)
        v = r[value_key]
        gain = (b / v) if (np.isfinite(b) and np.isfinite(v) and v > 0) else np.nan
        rows.append(
            {
                "source_plate": r["source_plate"],
                "target_plate": r["target_plate"],
                "strategy": r["strategy"],
                "representation": r.get("representation"),
                "value": v,
                "baseline": b,
                "gain": gain,
            }
        )
    return pd.DataFrame(rows)


def pivot_gain(
    gain_df: pd.DataFrame,
    *,
    strategy: str,
    representation: str,
) -> pd.DataFrame:
    sub = gain_df[
        (gain_df["strategy"] == strategy) & (gain_df["representation"] == representation)
    ]
    if sub.empty:
        return pd.DataFrame()
    return sub.pivot_table(
        index="source_plate", columns="target_plate", values="gain", aggfunc="mean"
    )
