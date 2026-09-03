#!/usr/bin/env python
"""W6 / P1.1: task similarity vs transfer Δfrac (EDBO Suzuki).

Uses full-board responses only for post-hoc mechanism analysis (not a Gate feature).
Aligns plates on candidate_key; correlates Spearman/Kendall/top-k overlap with
pair-level mid-budget Δfrac.

Example:
  python scripts/analyze_task_similarity_transfer.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import kendalltau, spearmanr

ROOT = Path(__file__).resolve().parents[1]
STATS = ROOT / "results" / "paper_stats"
PLATES = ROOT / "data" / "processed" / "edbo_suzuki_plates.csv"
PRIMARY_BUDGETS = (30, 40, 50)
TOP_KS = (5, 10, 20)


def top_k_jaccard(y_s: np.ndarray, y_t: np.ndarray, k: int) -> float:
    k = min(k, len(y_s), len(y_t))
    if k <= 0:
        return np.nan
    s = set(np.argpartition(y_s, -k)[-k:].tolist())
    t = set(np.argpartition(y_t, -k)[-k:].tolist())
    union = s | t
    return float(len(s & t) / len(union)) if union else np.nan


def top_k_overlap_frac(y_s: np.ndarray, y_t: np.ndarray, k: int) -> float:
    """|top-k ∩| / k (asymmetric overlap relative to k)."""
    k = min(k, len(y_s), len(y_t))
    if k <= 0:
        return np.nan
    s = set(np.argpartition(y_s, -k)[-k:].tolist())
    t = set(np.argpartition(y_t, -k)[-k:].tolist())
    return float(len(s & t) / k)


def source_best_rank_on_target(y_s: np.ndarray, y_t: np.ndarray) -> float:
    i = int(np.argmax(y_s))
    return float((y_t > y_t[i]).sum() + 1)


def align_pair(wide: pd.DataFrame, src: str, tgt: str) -> tuple[np.ndarray, np.ndarray]:
    y_s = wide[src].to_numpy(dtype=float)
    y_t = wide[tgt].to_numpy(dtype=float)
    mask = np.isfinite(y_s) & np.isfinite(y_t)
    return y_s[mask], y_t[mask]


def pair_similarity(y_s: np.ndarray, y_t: np.ndarray) -> dict:
    sp, sp_p = spearmanr(y_s, y_t)
    kd, kd_p = kendalltau(y_s, y_t)
    out = {
        "n_aligned": int(len(y_s)),
        "spearman": float(sp) if np.isfinite(sp) else np.nan,
        "spearman_p": float(sp_p) if np.isfinite(sp_p) else np.nan,
        "kendall": float(kd) if np.isfinite(kd) else np.nan,
        "kendall_p": float(kd_p) if np.isfinite(kd_p) else np.nan,
        "src_best_rank_on_tgt": source_best_rank_on_target(y_s, y_t),
    }
    for k in TOP_KS:
        out[f"topk{k}_jaccard"] = top_k_jaccard(y_s, y_t, k)
        out[f"topk{k}_overlap"] = top_k_overlap_frac(y_s, y_t, k)
    return out


def load_primary_deltas(path: Path) -> pd.DataFrame:
    d = pd.read_csv(path)
    d = d[(d["metric"] == "frac") & (d["budget"].isin(PRIMARY_BUDGETS))].copy()
    g = (
        d.groupby(["rep", "source", "target"], as_index=False)["delta_mean"]
        .mean()
        .rename(columns={"delta_mean": "delta_frac_primary"})
    )
    return g


def corr_table(merged: pd.DataFrame, sim_cols: list[str]) -> pd.DataFrame:
    rows = []
    for rep, sub in merged.groupby("rep"):
        for col in sim_cols:
            a = sub["delta_frac_primary"].to_numpy(float)
            b = sub[col].to_numpy(float)
            m = np.isfinite(a) & np.isfinite(b)
            if m.sum() < 3:
                continue
            r_sp, p_sp = spearmanr(a[m], b[m])
            r_pe = float(np.corrcoef(a[m], b[m])[0, 1])
            rows.append(
                {
                    "rep": rep,
                    "similarity": col,
                    "n_pairs": int(m.sum()),
                    "spearman_vs_delta": float(r_sp) if np.isfinite(r_sp) else np.nan,
                    "spearman_p": float(p_sp) if np.isfinite(p_sp) else np.nan,
                    "pearson_vs_delta": r_pe if np.isfinite(r_pe) else np.nan,
                }
            )
    return pd.DataFrame(rows)


def quantile_strata(merged: pd.DataFrame, sim_col: str = "spearman", q: int = 3) -> pd.DataFrame:
    rows = []
    for rep, sub in merged.groupby("rep"):
        s = sub.copy()
        s["stratum"] = pd.qcut(s[sim_col], q=q, labels=[f"Q{i+1}" for i in range(q)], duplicates="drop")
        for st, g in s.groupby("stratum", observed=True):
            rows.append(
                {
                    "rep": rep,
                    "sim_col": sim_col,
                    "stratum": str(st),
                    "n": int(len(g)),
                    "sim_mean": float(g[sim_col].mean()),
                    "delta_mean": float(g["delta_frac_primary"].mean()),
                    "delta_median": float(g["delta_frac_primary"].median()),
                    "n_neg": int((g["delta_frac_primary"] < -0.02).sum()),
                    "n_pos": int((g["delta_frac_primary"] > 0.02).sum()),
                }
            )
    return pd.DataFrame(rows)


def plot_scatters(merged: pd.DataFrame, out: Path) -> None:
    reps = sorted(merged["rep"].unique())
    fig, axes = plt.subplots(1, len(reps), figsize=(4.2 * len(reps), 3.8), dpi=160, sharey=True)
    if len(reps) == 1:
        axes = [axes]
    for ax, rep in zip(axes, reps):
        sub = merged[merged["rep"] == rep]
        ax.scatter(
            sub["spearman"],
            sub["delta_frac_primary"],
            s=28,
            alpha=0.75,
            c="#2c7fb8",
            edgecolors="none",
        )
        ax.axhline(0.0, color="#666666", lw=0.8)
        ax.axhline(-0.02, color="#aaaaaa", lw=0.6, ls="--")
        ax.axhline(0.02, color="#aaaaaa", lw=0.6, ls="--")
        r, p = spearmanr(sub["spearman"], sub["delta_frac_primary"])
        ax.set_title(f"{rep}\nρ(Δ,Spearman)={r:.2f} (p={p:.3g})", fontsize=10)
        ax.set_xlabel("source–target Spearman(y)")
        ax.set_ylabel("mean Δfrac (B∈{30,40,50})")
    fig.suptitle("EDBO Suzuki: landscape similarity vs transfer gain", fontsize=11)
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def plot_topk(merged: pd.DataFrame, out: Path) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(11.5, 3.6), dpi=160, sharey=True)
    reps = sorted(merged["rep"].unique())
    # one panel per top-k metric, points colored by rep
    for ax, k in zip(axes, TOP_KS):
        col = f"topk{k}_jaccard"
        for rep in reps:
            sub = merged[merged["rep"] == rep]
            ax.scatter(sub[col], sub["delta_frac_primary"], s=22, alpha=0.7, label=rep)
        ax.axhline(0.0, color="#666666", lw=0.8)
        ax.set_xlabel(f"top-{k} Jaccard")
        ax.set_ylabel("mean Δfrac (B∈{30,40,50})")
        ax.set_title(f"top-{k}")
        ax.legend(fontsize=7, loc="best")
    fig.suptitle("EDBO Suzuki: top-k condition overlap vs Δfrac", fontsize=11)
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plates", type=Path, default=PLATES)
    parser.add_argument(
        "--deltas",
        type=Path,
        default=STATS / "edbo_suzuki_pair_level_deltas.csv",
    )
    parser.add_argument("--out-dir", type=Path, default=STATS)
    args = parser.parse_args()
    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    fig_dir = ROOT / "exports" / "paper_figs"
    fig_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.plates)
    wide = df.pivot_table(
        index="candidate_key", columns="plate_id", values="response", aggfunc="first"
    )
    deltas = load_primary_deltas(args.deltas)
    pairs = deltas[["source", "target"]].drop_duplicates()

    sim_rows = []
    for _, r in pairs.iterrows():
        src, tgt = r["source"], r["target"]
        y_s, y_t = align_pair(wide, src, tgt)
        row = {"source": src, "target": tgt, **pair_similarity(y_s, y_t)}
        sim_rows.append(row)
    sim = pd.DataFrame(sim_rows)
    merged = deltas.merge(sim, on=["source", "target"], how="left")

    sim_cols = [
        "spearman",
        "kendall",
        "src_best_rank_on_tgt",
        *[f"topk{k}_jaccard" for k in TOP_KS],
        *[f"topk{k}_overlap" for k in TOP_KS],
    ]
    corr = corr_table(merged, sim_cols)
    strata = quantile_strata(merged, "spearman", q=3)

    pair_path = out / "edbo_suzuki_similarity_vs_delta.csv"
    corr_path = out / "edbo_suzuki_similarity_delta_corr.csv"
    strata_path = out / "edbo_suzuki_similarity_strata.csv"
    merged.to_csv(pair_path, index=False)
    corr.to_csv(corr_path, index=False)
    strata.to_csv(strata_path, index=False)

    fig1 = fig_dir / "fig_edbo_suzuki_similarity_vs_delta.png"
    fig2 = fig_dir / "fig_edbo_suzuki_topk_vs_delta.png"
    plot_scatters(merged, fig1)
    plot_topk(merged, fig2)
    # also copy into paper_stats for ESI bundling
    plot_scatters(merged, out / fig1.name)
    plot_topk(merged, out / fig2.name)

    # note
    morgan = corr[(corr["rep"] == "morgan") & (corr["similarity"] == "spearman")]
    sp_line = ""
    if len(morgan):
        sp_line = (
            f"Morgan: Spearman(Δfrac, ρ_y) = {morgan.iloc[0]['spearman_vs_delta']:.3f} "
            f"(p={morgan.iloc[0]['spearman_p']:.3g})."
        )
    note = [
        "# EDBO Suzuki: task similarity ↔ Δfrac (W6)",
        "",
        "Post-hoc only: full-board labels used to measure landscape alignment.",
        f"Primary Δfrac = mean over B∈{list(PRIMARY_BUDGETS)} from C1 pair table.",
        "",
        sp_line,
        "",
        "## Files",
        f"- `{pair_path.name}` — pair-level similarity + Δfrac",
        f"- `{corr_path.name}` — corr(similarity, Δfrac) by representation",
        f"- `{strata_path.name}` — tercile strata of Spearman",
        f"- `{fig1.name}`, `{fig2.name}`",
        "",
        "## Corr summary (Spearman vs Δ)",
        corr[corr["similarity"].isin(["spearman", "kendall", "topk10_jaccard"])]
        .round(4)
        .to_string(index=False),
        "",
        "## Interpretation note",
        "If similarity tracks gain, expect positive corr(Spearman, Δfrac).",
        "Weak/null corr ⇒ global rank alignment alone does not explain pair heterogeneity;",
        "still consistent with task mismatch at the condition-optima level (see top-k / src-best rank).",
        "",
    ]
    (out / "edbo_suzuki_similarity_INFERENCE_NOTE.md").write_text(
        "\n".join(note), encoding="utf-8"
    )

    print(corr.round(3).to_string(index=False))
    print("Wrote", pair_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
