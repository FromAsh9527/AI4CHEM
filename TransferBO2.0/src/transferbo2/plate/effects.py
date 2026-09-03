"""Plate / batch effect utilities."""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd


def anchor_plate_offsets(df: pd.DataFrame, response_col: str = "yield") -> pd.DataFrame:
    """Estimate per-plate additive offsets from shared anchor conditions.

    offset_p = mean_j (y_{p,j} - mean_p'(y_{p',j})) over anchor conditions j.
    """
    anchors = df[df["is_anchor"] == 1].copy()
    if anchors.empty:
        return pd.DataFrame(columns=["plate_id", "offset", "n_anchors"])
    # mean across plates for each condition
    cond_mean = anchors.groupby("condition_id")[response_col].mean().rename("cond_mean")
    a = anchors.join(cond_mean, on="condition_id")
    a["delta"] = a[response_col] - a["cond_mean"]
    out = a.groupby("plate_id").agg(offset=("delta", "mean"), n_anchors=("delta", "count")).reset_index()
    return out


def apply_plate_offsets(df: pd.DataFrame, offsets: pd.DataFrame, response_col: str = "yield") -> pd.DataFrame:
    out = df.copy()
    m = offsets.set_index("plate_id")["offset"]
    out["yield_corr"] = out[response_col] - out["plate_id"].map(m).fillna(0.0)
    return out


def plate_condition_spearman(df: pd.DataFrame, response_col: str = "yield") -> pd.DataFrame:
    """Pairwise Spearman correlation of condition rankings across plates (shared conditions)."""
    from scipy.stats import spearmanr

    plates = sorted(df["plate_id"].unique())
    rows = []
    for i, p1 in enumerate(plates):
        for p2 in plates[i + 1 :]:
            a = df[df["plate_id"] == p1][["condition_id", response_col]].drop_duplicates("condition_id")
            b = df[df["plate_id"] == p2][["condition_id", response_col]].drop_duplicates("condition_id")
            m = a.merge(b, on="condition_id", suffixes=("_1", "_2"))
            if len(m) < 3:
                rho, pval = np.nan, np.nan
            else:
                rho, pval = spearmanr(m[f"{response_col}_1"], m[f"{response_col}_2"])
            rows.append({"plate_a": p1, "plate_b": p2, "n_shared": len(m), "spearman": rho, "pval": pval})
    return pd.DataFrame(rows)


def variance_components(df: pd.DataFrame, response_col: str = "yield") -> dict:
    """Rough ANOVA-style variance shares for substrate / plate / residual."""
    y = df[response_col].to_numpy(dtype=float)
    mu = y.mean()
    ss_tot = float(np.sum((y - mu) ** 2)) + 1e-12
    sub_means = df.groupby("substrate_id")[response_col].transform("mean").to_numpy()
    plate_means = df.groupby("plate_id")[response_col].transform("mean").to_numpy()
    ss_sub = float(np.sum((sub_means - mu) ** 2))
    ss_plate = float(np.sum((plate_means - mu) ** 2))
    resid = y - sub_means - (plate_means - mu)
    ss_res = float(np.sum((resid - resid.mean()) ** 2))
    return {
        "ss_total": ss_tot,
        "frac_substrate": ss_sub / ss_tot,
        "frac_plate": ss_plate / ss_tot,
        "frac_residual_proxy": ss_res / ss_tot,
        "n": int(len(df)),
    }
