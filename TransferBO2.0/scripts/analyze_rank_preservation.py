"""Rank-preservation hypothesis verification (offline, 4 libraries).

Hypothesis (2026-08-23):
    What transfers across substrates/batches is the RANKING of conditions
    (which conditions are relatively better), not the absolute yield values.
    Predictions:
      P1: library-level rank preservation (mean pairwise Spearman across
          substrates) correlates with topk transfer gain (Delta AUC vs cold);
      P2: target-level rank preservation predicts that target's transfer gain;
      P3: top-of-ranking is more preserved than the whole ranking
          (top-5 stability > overall Spearman) -> justifies k=5;
      P4: "value location" (init vs continuation) is explained by
          rank preservation (history contribution) x response-surface
          learnability (BO contribution; proxy = cold post_lift from M1).

Usage:
    python scripts/analyze_rank_preservation.py
Output:
    results/rank_preservation/{per_library.csv, target_level.csv, summary.md}
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "rank_preservation"

LIBRARIES = {
    "amination": {"db": ROOT / "data" / "db" / "transferbo2.db",
                  "json": ROOT / "results" / "amination_v1_full"},
    "suzuki": {"db": ROOT / "data" / "db" / "transferbo2_suzuki.db",
               "json": ROOT / "results" / "suzuki_v1_full_rt" / "suzuki_v1_full"},
    "borylation": {"db": ROOT / "data" / "db" / "transferbo2_borylation.db",
                   "json": ROOT / "results" / "p4_borylation" / "loso"},
    "hitea": {"db": ROOT / "data" / "db" / "transferbo2_hitea.db",
              "json": ROOT / "results" / "p4_hitea" / "loso"},
}


def load_matrix(db_path: Path, min_support: int = 3) -> pd.DataFrame:
    conn = sqlite3.connect(str(db_path))
    df = pd.read_sql("SELECT substrate_id, condition_id, yield FROM experiments", conn)
    conn.close()
    df = df.groupby(["substrate_id", "condition_id"], as_index=False)["yield"].mean()
    piv = df.pivot(index="condition_id", columns="substrate_id", values="yield")
    # keep conditions measured on >= min_support substrates (shared space)
    piv = piv[piv.notna().sum(axis=1) >= min_support]
    return piv


def pairwise_rank_corr(mat: pd.DataFrame) -> tuple[float, np.ndarray]:
    """Mean pairwise Spearman over substrate columns (shared conditions)."""
    vals = []
    cols = mat.columns
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            sub = mat[[cols[i], cols[j]]].dropna()
            if len(sub) >= 5:
                r = spearmanr(sub.iloc[:, 0], sub.iloc[:, 1]).correlation
                if np.isfinite(r):
                    vals.append(r)
    vals = np.asarray(vals)
    return float(vals.mean()), vals


def target_rank_corr(mat: pd.DataFrame) -> pd.Series:
    """Mean Spearman of each substrate column vs all others."""
    out = {}
    for col in mat.columns:
        vals = []
        for other in mat.columns:
            if other == col:
                continue
            sub = mat[[col, other]].dropna()
            if len(sub) >= 5:
                r = spearmanr(sub.iloc[:, 0], sub.iloc[:, 1]).correlation
                if np.isfinite(r):
                    vals.append(r)
        out[col] = float(np.mean(vals))
    return pd.Series(out)


def top5_stability(mat: pd.DataFrame) -> pd.Series:
    """Per substrate: how much of the pooled top-5 (others) sits in its own top-10."""
    out = {}
    for col in mat.columns:
        others = mat.drop(columns=[col])
        pooled = others.mean(axis=1).sort_values(ascending=False).index[:5]
        own = mat[col].sort_values(ascending=False).index
        rank_of_pooled = [np.where(own == c)[0][0] + 1 for c in pooled if c in own.values]
        out[col] = float(np.mean(rank_of_pooled)) if rank_of_pooled else np.nan
    return pd.Series(out)


def loso_deltas(json_dir: Path) -> pd.DataFrame:
    """Target-level AUC deltas: topk - cold, and cold post_lift (M1 proxy)."""
    rows = {}
    for p in sorted(Path(json_dir).glob("*.json")):
        if p.name.startswith("loso"):
            continue
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if "bo" not in rec:
            continue
        strat = rec["strategy"]
        tgt = rec["target_substrate"]
        bsf = np.asarray(rec["bo"].get("best_so_far") or [], dtype=float)
        if len(bsf) < 20:
            continue
        auc = float(np.sum(bsf))
        carried = float(np.sum(bsf[:5]) + 15 * bsf[4])
        post_lift = auc - carried
        rows.setdefault(tgt, {})
        rows[tgt][strat] = {"auc": rows[tgt].get(strat, {}).get("auc", 0.0) + auc / 5.0}
        if strat == "cold_start":
            rows[tgt].setdefault("cold_post_lift", 0.0)
            rows[tgt]["cold_post_lift"] += post_lift / 5.0
    out = []
    for tgt, d in rows.items():
        out.append({
            "target": tgt,
            "delta_auc_topk_cold": d.get("topk_warm", {}).get("auc", np.nan) - d.get("cold_start", {}).get("auc", np.nan),
            "auc_cold": d.get("cold_start", {}).get("auc", np.nan),
            "cold_post_lift": d.get("cold_post_lift", np.nan),
        })
    return pd.DataFrame(out)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    lib_rows = []
    tgt_rows = []
    for lib, cfg in LIBRARIES.items():
        mat = load_matrix(cfg["db"])
        corr_mean, corr_all = pairwise_rank_corr(mat)
        tgt_corr = target_rank_corr(mat)
        top5 = top5_stability(mat)
        deltas = loso_deltas(cfg["json"])
        merged = deltas.merge(tgt_corr.rename("rank_corr"), left_on="target", right_index=True, how="left")
        merged = merged.merge(top5.rename("pooled_top5_mean_rank"), left_on="target", right_index=True, how="left")
        merged["library"] = lib
        merged["rel_gain"] = merged["delta_auc_topk_cold"] / merged["auc_cold"]
        tgt_rows.append(merged)
        lib_rows.append({
            "library": lib,
            "n_substrates": mat.shape[1],
            "n_conditions": mat.shape[0],
            "mean_pairwise_spearman": corr_mean,
            "median_pairwise_spearman": float(np.median(corr_all)),
            "q25_pairwise_spearman": float(np.quantile(corr_all, 0.25)),
            "q75_pairwise_spearman": float(np.quantile(corr_all, 0.75)),
            "mean_target_rank_corr": float(tgt_corr.mean()),
            "mean_pooled_top5_rank": float(top5.mean()),
            "mean_delta_auc": float(merged["delta_auc_topk_cold"].mean()),
            "mean_rel_gain": float(merged["rel_gain"].mean()),
            "mean_cold_post_lift": float(merged["cold_post_lift"].mean()),
        })

    libs = pd.DataFrame(lib_rows)
    tgts = pd.concat(tgt_rows, ignore_index=True)
    libs.to_csv(OUT / "per_library.csv", index=False)
    tgts.to_csv(OUT / "target_level.csv", index=False)

    lines = ["# Rank-preservation hypothesis — verification (offline)", "",
             "Hypothesis: what transfers is the RANKING of conditions, not absolute yields.",
             "P1: library rank-preservation ~ transfer gain; P2: target-level; "
             "P3: top-5 more stable than overall; P4: value location = rank-preservation x learnability.",
             ""]
    lines.append("## Library level")
    lines.append("")
    lines.append("| library | tasks | conds | mean pairwise ρ | median ρ | mean target ρ | pooled-top5 mean rank | ΔAUC | rel gain | cold post_lift |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for _, r in libs.iterrows():
        lines.append(f"| {r['library']} | {r['n_substrates']:.0f} | {r['n_conditions']:.0f} "
                     f"| {r['mean_pairwise_spearman']:.3f} | {r['median_pairwise_spearman']:.3f} "
                     f"| {r['mean_target_rank_corr']:.3f} | {r['mean_pooled_top5_rank']:.1f} "
                     f"| {r['mean_delta_auc']:+.1f} | {r['mean_rel_gain']:+.1%} | {r['mean_cold_post_lift']:+.1f} |")
    lines.append("")
    lines.append("## Target-level correlation (P2)")
    lines.append("")
    for lib in tgts["library"].unique():
        sub = tgts[tgts["library"] == lib].dropna(subset=["rank_corr", "delta_auc_topk_cold"])
        if len(sub) >= 5:
            r, p = spearmanr(sub["rank_corr"], sub["delta_auc_topk_cold"])
            lines.append(f"- {lib}: Spearman(rank_corr, ΔAUC) = **{r:+.3f}** (p={p:.3f}, n={len(sub)})")
    lines.append("")
    # pooled top-5 rank vs overall corr (P3)
    lines.append("## Top vs overall (P3): pooled top-5 mean rank vs overall ρ")
    lines.append("")
    for lib in tgts["library"].unique():
        sub = tgts[tgts["library"] == lib]
        lines.append(f"- {lib}: pooled top-5 mean rank = {sub['pooled_top5_mean_rank'].mean():.1f} "
                     f"(rank 1 = best; if top-5 stable, this is small)")
    lines.append("")
    # cross-library correlation (P1)
    d = libs.dropna(subset=["mean_pairwise_spearman", "mean_rel_gain"])
    if len(d) >= 3:
        r1, p1 = spearmanr(d["mean_pairwise_spearman"], d["mean_rel_gain"])
        lines.append(f"## Cross-library (P1, n={len(d)}): Spearman(mean ρ, rel gain) = **{r1:+.3f}** (p={p1:.3f})")
        r2, p2 = spearmanr(d["mean_pairwise_spearman"], d["mean_delta_auc"])
        lines.append(f"Cross-library (P1): Spearman(mean ρ, ΔAUC) = **{r2:+.3f}** (p={p2:.3f})")
        r3, p3 = spearmanr(d["mean_pairwise_spearman"], d["mean_cold_post_lift"])
        lines.append(f"Cross-library (P4): Spearman(mean ρ, cold post_lift) = **{r3:+.3f}** (p={p3:.3f})")
    lines.append("")
    (OUT / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"\n[OK] wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
