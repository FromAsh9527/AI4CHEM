#!/usr/bin/env python
"""P1 mechanism: response-landscape consistency vs transfer gain (dev fold).

Uses FULL target labels only for post-hoc explanation (NOT deployable Gate features).

Example:
  python scripts/analyze_mechanism.py
  python scripts/analyze_mechanism.py --out results/mechanism
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from run_experiment import _feature_strings  # noqa: E402
from transferbo.data import get_plate, load_plates  # noqa: E402
from transferbo.representations import build_representation  # noqa: E402
from transferbo.utils import ensure_dir, load_config  # noqa: E402


def top_overlap(y_s: np.ndarray, y_t: np.ndarray, frac: float = 0.05) -> float:
    n = len(y_s)
    k = max(1, int(np.ceil(n * frac)))
    s = set(np.argpartition(y_s, -k)[-k:].tolist())
    t = set(np.argpartition(y_t, -k)[-k:].tolist())
    return len(s & t) / k


def source_best_on_target(y_s: np.ndarray, y_t: np.ndarray) -> dict:
    i = int(np.argmax(y_s))
    rank = int((y_t > y_t[i]).sum()) + 1
    return {
        "src_best_tgt_value": float(y_t[i]),
        "src_best_tgt_frac_of_opt": float(y_t[i] / (y_t.max() + 1e-12)),
        "src_best_tgt_rank": rank,
        "src_best_tgt_rank_pct": rank / len(y_t),
    }


def knn_zero_shot_spearman(X: np.ndarray, y_s: np.ndarray, y_t: np.ndarray, knn: int = 5) -> float:
    """Predict target ranks by kNN on source labels in shared feature space."""
    pred = np.empty(len(y_t), dtype=float)
    for i in range(len(y_t)):
        d = np.linalg.norm(X - X[i], axis=1)
        d[i] = np.inf  # exclude self if same indexing
        nn = np.argpartition(d, min(knn, len(d) - 1))[:knn]
        pred[i] = float(np.mean(y_s[nn]))
    r, _ = spearmanr(pred, y_t)
    return float(r) if np.isfinite(r) else np.nan


def mmd_proxy(X_a: np.ndarray, X_b: np.ndarray, max_n: int = 120, seed: int = 0) -> float:
    rng = np.random.default_rng(seed)
    if len(X_a) > max_n:
        X_a = X_a[rng.choice(len(X_a), max_n, replace=False)]
    if len(X_b) > max_n:
        X_b = X_b[rng.choice(len(X_b), max_n, replace=False)]
    # For same-library plates X_a==X_b structurally; still report mean pairwise shift of subset
    return float(np.linalg.norm(X_a.mean(0) - X_b.mean(0)))


def pair_features(df: pd.DataFrame, src: str, tgt: str, rep_name: str, cfg: dict) -> dict:
    s = get_plate(df, src).copy()
    t = get_plate(df, tgt).copy()
    # plates share the additive library; additive_id is plate-prefixed → align on SMILES
    s = s.drop_duplicates("smiles").set_index("smiles")
    t = t.drop_duplicates("smiles").set_index("smiles")
    common = s.index.intersection(t.index)
    if len(common) < 2:
        raise ValueError(f"aligned smiles < 2 ({len(common)})")
    s = s.loc[common]
    t = t.loc[common]
    y_s = s["response"].to_numpy(float)
    y_t = t["response"].to_numpy(float)

    if rep_name == "drfp" and "reaction_smiles" in s.columns:
        strings = s["reaction_smiles"].astype(str).tolist()
    else:
        strings = list(common.astype(str))

    kwargs = dict((cfg.get("representation", {}) or {}).get(rep_name, {}) or {})
    rep = build_representation(rep_name, **kwargs)
    X = rep.fit_transform(strings)

    pear, _ = pearsonr(y_s, y_t)
    spear, _ = spearmanr(y_s, y_t)
    out = {
        "source": src,
        "target": tgt,
        "representation": rep_name,
        "n_aligned": int(len(common)),
        "pearson_y": float(pear),
        "spearman_y": float(spear),
        "top5_overlap": top_overlap(y_s, y_t, 0.05),
        "top10_overlap": top_overlap(y_s, y_t, 0.10),
        "knn_zeroshot_spearman": knn_zero_shot_spearman(X, y_s, y_t),
        "mean_feature_shift": 0.0,  # same smiles library → identical X
        **source_best_on_target(y_s, y_t),
    }
    return out


def load_deltas(grid_path: Path, rep: str) -> pd.DataFrame:
    g = pd.read_csv(grid_path)
    g = g[g["representation"] == rep]
    cold = (
        g[g["strategy"] == "cold_start"]
        .groupby(["target_plate", "seed"])["frac_of_opt"]
        .mean()
        .rename("cold")
        .reset_index()
    )
    rows = []
    for (strat, src, tgt), sub in g[g["strategy"].isin(["label_warm", "diversity_warm", "multitask"])].groupby(
        ["strategy", "source_plate", "target_plate"]
    ):
        if src == tgt:
            continue
        m = sub.merge(cold, left_on=["target_plate", "seed"], right_on=["target_plate", "seed"])
        rows.append(
            {
                "strategy": strat,
                "source": src,
                "target": tgt,
                "delta_mean": float((m["frac_of_opt"] - m["cold"]).mean()),
                "frac_mean": float(m["frac_of_opt"].mean()),
                "n_seeds": len(m),
            }
        )
    return pd.DataFrame(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, default=ROOT / "configs/default.yaml")
    ap.add_argument("--grid", type=Path, default=ROOT / "results/transfer_grid/grid_results.csv")
    ap.add_argument("--reps", nargs="+", default=["morgan", "drfp"])
    ap.add_argument("--out", type=Path, default=ROOT / "results/mechanism")
    args = ap.parse_args()

    cfg = load_config(args.config)
    df = load_plates(cfg["data"]["processed_path"])
    plates = sorted(df["plate_id"].unique())
    # mechanism on all plate pairs that appear in grid (incl heldout for post-hoc only — flag)
    held = "plate_4"
    ensure_dir(args.out)

    feat_rows = []
    for rep in args.reps:
        for src in plates:
            for tgt in plates:
                if src == tgt:
                    continue
                try:
                    feat = pair_features(df, src, tgt, rep, cfg)
                except Exception as e:
                    print(f"skip {src}->{tgt} {rep}: {e}")
                    continue
                feat["uses_heldout_target"] = tgt == held
                feat_rows.append(feat)
    feats = pd.DataFrame(feat_rows)
    if feats.empty:
        raise SystemExit("No landscape features computed — check SMILES alignment.")
    feats.to_csv(args.out / "landscape_features.csv", index=False)

    # join deltas (dev fold only for correlation to avoid peeking narrative — still compute all)
    corr_rows = []
    for rep in args.reps:
        deltas = load_deltas(args.grid, rep)
        if deltas.empty:
            continue
        sub_f = feats[feats["representation"] == rep]
        for strat in ["label_warm", "diversity_warm", "multitask"]:
            d = deltas[deltas["strategy"] == strat]
            m = d.merge(sub_f, on=["source", "target"], how="inner")
            # exclude heldout from correlation fit used in paper narrative
            m_dev = m[~m["uses_heldout_target"]]
            if len(m_dev) < 3:
                continue
            for col in [
                "pearson_y",
                "spearman_y",
                "top5_overlap",
                "top10_overlap",
                "knn_zeroshot_spearman",
                "src_best_tgt_frac_of_opt",
            ]:
                if m_dev[col].nunique() < 2:
                    r = np.nan
                else:
                    r, _ = spearmanr(m_dev[col], m_dev["delta_mean"])
                corr_rows.append(
                    {
                        "strategy": strat,
                        "representation": rep,
                        "feature": col,
                        "spearman_with_delta": float(r) if np.isfinite(r) else np.nan,
                        "n_pairs": len(m_dev),
                    }
                )
            m.to_csv(args.out / f"pair_delta_with_features__{strat}__{rep}.csv", index=False)

    corr = pd.DataFrame(corr_rows)
    corr.to_csv(args.out / "feature_delta_correlations.csv", index=False)

    # short markdown
    lines = [
        "# Mechanism scan (post-hoc)",
        "",
        "Target-label-using features are **explanatory only**.",
        "",
        "## Spearman(feature, Δ label/diversity vs cold) on development pairs",
        "",
    ]
    if not corr.empty:
        pivot = corr.pivot_table(
            index=["strategy", "feature"], columns="representation", values="spearman_with_delta"
        )
        lines.append(pivot.to_string())
    (args.out / "MECHANISM_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {args.out}")
    if not corr.empty:
        print(corr.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
