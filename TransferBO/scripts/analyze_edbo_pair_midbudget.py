#!/usr/bin/env python
"""EDBO Suzuki pair-level label−cold effects at primary mid-budget windows.

Statistical unit of analysis
----------------------------
- **Not** 1120 label trajectories as IID samples.
- Seed-level contrast: Δ(s,t,seed,B) = label(s,t,seed,B) − cold(t,seed,B).
- Pair-level effect: mean_seed Δ(s,t,·,B)  (n_seeds within pair).
- Overall / CI: mean and bootstrap over **pairs** (n≈56), optionally stratified
  by target (mean of 7 inbound pairs).

Primary windows: B ∈ {30, 40, 50} (init ends at 20). B=100 retained for ceiling
comparison only.

Also audits whether cold and label share identical target init_indices under
the same (representation, target, seed). Existing main-grid JSONs are expected
to mismatch (source subsample advanced RNG before init); post-fix label_warm
samples init first.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import TwoSlopeNorm

ROOT = Path(__file__).resolve().parents[1]
GRID = ROOT / "results" / "external_edbo_suzuki"
STATS = ROOT / "results" / "paper_stats"
FIGS = ROOT / "docs" / "figs"
PRIMARY_B = (30, 40, 50)
NEAR = 0.02


def load_rep(rep: str) -> pd.DataFrame:
    rows = []
    for p in GRID.glob("*.json"):
        name = p.name
        if f"__{rep}__" not in name:
            continue
        if not (name.startswith("cold_start") or name.startswith("label_warm")):
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        best = float(d["best_final"])
        gbest = float(d["global_best"])
        curve = [float(v) for v in d["bo"]["best_so_far"][:100]]
        meta = d.get("meta") or {}
        rows.append(
            {
                "strategy": d["strategy"],
                "rep": rep,
                "source": d.get("source_plate"),
                "target": d["target_plate"],
                "seed": int(d["seed"]),
                "best_final": best,
                "global_best": gbest,
                "frac_final": best / gbest if gbest else np.nan,
                "curve": curve,
                "init_indices": tuple(meta.get("init_indices") or []),
            }
        )
    return pd.DataFrame(rows)


def audit_init_match(df: pd.DataFrame) -> dict:
    cold = {
        (r.target, r.seed): r.init_indices
        for r in df[df.strategy == "cold_start"].itertuples(index=False)
    }
    lab = df[df.strategy == "label_warm"]
    total = 0
    match = 0
    for r in lab.itertuples(index=False):
        total += 1
        if cold.get((r.target, r.seed)) == r.init_indices:
            match += 1
    # within (target, seed): do all sources share one init?
    groups = lab.groupby(["target", "seed"])["init_indices"]
    n_groups = 0
    n_all_same = 0
    for _, g in groups:
        n_groups += 1
        if g.nunique() == 1:
            n_all_same += 1
    return {
        "n_label_traj": total,
        "n_label_eq_cold_init": match,
        "pct_label_eq_cold_init": (match / total) if total else np.nan,
        "n_target_seed_groups": n_groups,
        "pct_sources_share_init": (n_all_same / n_groups) if n_groups else np.nan,
    }


def value_at(curve: list[float], gbest: float, B: int, metric: str) -> float:
    y = curve[B - 1]
    if metric == "yield":
        return float(y)
    return float(y / gbest) if gbest else np.nan


def seed_contrasts(df: pd.DataFrame, B: int, metric: str) -> pd.DataFrame:
    """One row per (source, target, seed): Δ = label − cold(target, seed)."""
    cold = df[df.strategy == "cold_start"].copy()
    lab = df[df.strategy == "label_warm"].copy()
    cold["cold_val"] = [
        value_at(c, g, B, metric)
        for c, g in zip(cold["curve"], cold["global_best"])
    ]
    lab["label_val"] = [
        value_at(c, g, B, metric)
        for c, g in zip(lab["curve"], lab["global_best"])
    ]
    cold_key = cold[["target", "seed", "cold_val"]].drop_duplicates(
        ["target", "seed"]
    )
    m = lab.merge(cold_key, on=["target", "seed"], how="inner")
    m["delta"] = m["label_val"] - m["cold_val"]
    m["budget"] = B
    m["metric"] = metric
    return m[
        [
            "rep",
            "source",
            "target",
            "seed",
            "budget",
            "metric",
            "label_val",
            "cold_val",
            "delta",
        ]
    ]


def pair_effects(seed_df: pd.DataFrame) -> pd.DataFrame:
    g = (
        seed_df.groupby(["rep", "source", "target", "budget", "metric"], as_index=False)
        .agg(
            n_seeds=("delta", "size"),
            delta_mean=("delta", "mean"),
            delta_median=("delta", "median"),
            delta_std=("delta", "std"),
            label_mean=("label_val", "mean"),
            cold_mean=("cold_val", "mean"),
        )
    )
    g["delta_sem"] = g["delta_std"] / np.sqrt(g["n_seeds"].clip(lower=1))
    return g


def boot_mean_ci(x: np.ndarray, n_boot: int = 4000, seed: int = 0):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    if len(x) == 0:
        return np.nan, np.nan, np.nan
    rng = np.random.default_rng(seed)
    means = [float(np.mean(rng.choice(x, size=len(x), replace=True))) for _ in range(n_boot)]
    return float(np.mean(x)), float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))


def overall_from_pairs(pair_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (rep, B, metric), g in pair_df.groupby(["rep", "budget", "metric"]):
        mu, lo, hi = boot_mean_ci(g["delta_mean"].to_numpy(), seed=int(B) + 17)
        rows.append(
            {
                "rep": rep,
                "budget": B,
                "metric": metric,
                "n_pairs": len(g),
                "delta_mean": mu,
                "delta_ci_lo": lo,
                "delta_ci_hi": hi,
                "delta_median": float(np.median(g["delta_mean"])),
                "n_pos": int((g.delta_mean > NEAR).sum()),
                "n_neg": int((g.delta_mean < -NEAR).sum()),
                "n_near0": int((g.delta_mean.abs() <= NEAR).sum()),
                "unit": "pair",
            }
        )
    return pd.DataFrame(rows)


def target_from_pairs(pair_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (rep, B, metric, tgt), g in pair_df.groupby(
        ["rep", "budget", "metric", "target"]
    ):
        mu, lo, hi = boot_mean_ci(g["delta_mean"].to_numpy(), seed=hash(tgt) % 10_000)
        rows.append(
            {
                "rep": rep,
                "budget": B,
                "metric": metric,
                "target": tgt,
                "n_pairs": len(g),
                "delta_mean": mu,
                "delta_ci_lo": lo,
                "delta_ci_hi": hi,
                "unit": "pair_into_target",
            }
        )
    return pd.DataFrame(rows)


def plot_pair_strip(pair_df: pd.DataFrame, rep: str, metric: str, out: Path) -> None:
    sub = pair_df[
        (pair_df.rep == rep)
        & (pair_df.metric == metric)
        & (pair_df.budget.isin(PRIMARY_B))
    ].copy()
    if sub.empty:
        return
    budgets = list(PRIMARY_B)
    fig, axes = plt.subplots(1, len(budgets), figsize=(11.5, 4.8), dpi=140, sharey=True)
    ylabel = "Δfrac (label − cold)" if metric == "frac" else "Δyield (pp)"
    for ax, B in zip(axes, budgets):
        g = sub[sub.budget == B].sort_values("delta_mean")
        y = np.arange(len(g))
        colors = np.where(
            g.delta_mean > NEAR,
            "#2F6FED",
            np.where(g.delta_mean < -NEAR, "#C45C26", "#8A94A6"),
        )
        ax.axvline(0, color="#444", lw=0.8)
        ax.scatter(g.delta_mean, y, c=colors, s=18, zorder=3)
        if "delta_sem" in g:
            ax.hlines(
                y,
                g.delta_mean - g.delta_sem,
                g.delta_mean + g.delta_sem,
                colors=colors,
                lw=0.8,
                alpha=0.7,
            )
        mu = g.delta_mean.mean()
        ax.axvline(mu, color="#111", ls="--", lw=1, alpha=0.7)
        ax.set_title(f"B={B}  mean_pair={mu:+.3f}", fontsize=10)
        ax.set_xlabel(ylabel)
        ax.set_yticks([])
        n_pos = int((g.delta_mean > NEAR).sum())
        n_neg = int((g.delta_mean < -NEAR).sum())
        ax.text(
            0.02,
            0.98,
            f"+{n_pos} / −{n_neg} / ~{len(g)-n_pos-n_neg}",
            transform=ax.transAxes,
            va="top",
            fontsize=8,
            color="#444",
        )
    fig.suptitle(
        f"EDBO Suzuki · {rep} · pair-level effects (n_pairs={sub.budget.eq(PRIMARY_B[0]).sum()})",
        y=1.02,
    )
    fig.tight_layout()
    fig.savefig(out.with_suffix(".png"), bbox_inches="tight")
    fig.savefig(out.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)


def plot_pair_heatmap(pair_df: pd.DataFrame, rep: str, B: int, metric: str, out: Path) -> None:
    g = pair_df[
        (pair_df.rep == rep) & (pair_df.budget == B) & (pair_df.metric == metric)
    ]
    if g.empty:
        return
    mat = g.pivot(index="source", columns="target", values="delta_mean")
    plates = sorted(set(mat.index) | set(mat.columns))
    mat = mat.reindex(index=plates, columns=plates)
    v = np.nanmax(np.abs(mat.to_numpy(dtype=float)))
    v = max(float(v), 1e-3)
    norm = TwoSlopeNorm(vmin=-v, vcenter=0.0, vmax=v)
    fig, ax = plt.subplots(figsize=(6.2, 5.2), dpi=140)
    im = ax.imshow(mat.to_numpy(dtype=float), cmap="RdBu_r", norm=norm, aspect="equal")
    ax.set_xticks(range(len(plates)))
    ax.set_yticks(range(len(plates)))
    ax.set_xticklabels(plates, rotation=45, ha="right", fontsize=8)
    ax.set_yticklabels(plates, fontsize=8)
    ax.set_xlabel("target")
    ax.set_ylabel("source")
    label = "Δfrac" if metric == "frac" else "Δyield"
    ax.set_title(f"EDBO Suzuki · {rep} · pair {label} @ B={B}")
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label(f"mean_seed {label} (label−cold)")
    fig.tight_layout()
    fig.savefig(out.with_suffix(".png"), bbox_inches="tight")
    fig.savefig(out.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--reps",
        nargs="+",
        default=["morgan", "dft"],
        help="Representations to summarize (skip incomplete).",
    )
    ap.add_argument(
        "--budgets",
        nargs="+",
        type=int,
        default=[30, 40, 50, 100],
    )
    args = ap.parse_args()
    STATS.mkdir(parents=True, exist_ok=True)
    FIGS.mkdir(parents=True, exist_ok=True)

    audits = []
    seed_all = []
    pair_all = []
    for rep in args.reps:
        df = load_rep(rep)
        if df.empty:
            print(f"skip {rep}: no json")
            continue
        n_cold = int((df.strategy == "cold_start").sum())
        n_lab = int((df.strategy == "label_warm").sum())
        print(f"\n=== {rep}: cold={n_cold} label={n_lab} ===")
        audit = audit_init_match(df)
        audit["rep"] = rep
        audits.append(audit)
        print(
            "init audit: "
            f"label_eq_cold={audit['n_label_eq_cold_init']}/{audit['n_label_traj']} "
            f"({100*audit['pct_label_eq_cold_init']:.1f}%); "
            f"sources share init within (t,seed)="
            f"{100*audit['pct_sources_share_init']:.1f}%"
        )
        if n_lab < 56 * 20:
            print(f"  warn: label incomplete ({n_lab}/1120); pair means use available seeds")

        for B in args.budgets:
            for metric in ("frac", "yield"):
                seed_df = seed_contrasts(df, B, metric)
                seed_all.append(seed_df)
                pair_all.append(pair_effects(seed_df))

        pair_rep = pd.concat(
            [p for p in pair_all if (p["rep"] == rep).all()], ignore_index=True
        )
        plot_pair_strip(
            pair_rep,
            rep,
            "frac",
            FIGS / f"fig_edbo_suzuki_{rep}_pair_delta_frac_B30_50",
        )
        plot_pair_heatmap(
            pair_rep,
            rep,
            40,
            "frac",
            FIGS / f"fig_edbo_suzuki_{rep}_pair_delta_frac_heatmap_B40",
        )
        plot_pair_heatmap(
            pair_rep,
            rep,
            50,
            "frac",
            FIGS / f"fig_edbo_suzuki_{rep}_pair_delta_frac_heatmap_B50",
        )

    if not pair_all:
        print("nothing to summarize")
        return 1

    seed_df = pd.concat(seed_all, ignore_index=True)
    pair_df = pd.concat(pair_all, ignore_index=True)

    overall = overall_from_pairs(pair_df)
    by_target = target_from_pairs(pair_df)
    audit_df = pd.DataFrame(audits)

    seed_df.to_csv(STATS / "edbo_suzuki_pair_seed_deltas.csv", index=False)
    pair_df.to_csv(STATS / "edbo_suzuki_pair_level_deltas.csv", index=False)
    overall.to_csv(STATS / "edbo_suzuki_pair_overall_by_budget.csv", index=False)
    by_target.to_csv(STATS / "edbo_suzuki_pair_by_target_by_budget.csv", index=False)
    audit_df.to_csv(STATS / "edbo_suzuki_init_match_audit.csv", index=False)

    # human-readable note
    note = STATS / "edbo_suzuki_pair_level_NOTE.md"
    lines = [
        "# EDBO Suzuki pair-level mid-budget summary",
        "",
        "## Inference unit",
        "",
        "- Seed contrast: `Δ(s,t,seed,B) = label − cold(t,seed)` at budget B.",
        "- Pair effect: mean over seeds (typically 20).",
        "- Overall mean / bootstrap CI: **over pairs** (not over 1120 trajectories).",
        "- Do **not** report SEM over pooled label trajectories as if IID.",
        "",
        "## Primary windows",
        "",
        "B ∈ {30, 40, 50}. B=100 is ceiling comparison only.",
        "",
        "## Target-init matching (this main grid)",
        "",
    ]
    for r in audits:
        lines.append(
            f"- **{r['rep']}**: label init equals cold init in "
            f"{r['n_label_eq_cold_init']}/{r['n_label_traj']} "
            f"({100*r['pct_label_eq_cold_init']:.1f}%). "
            f"Within (target, seed), sources share one init "
            f"{100*r['pct_sources_share_init']:.1f}% of groups."
        )
    lines += [
        "",
        "Existing JSONs are **not** matched-target-init. Cause: `label_warm` used to",
        "draw source subsample before target init on the same RNG. Code now samples",
        "target init first (S0); re-run under a new output dir for matched sensitivity.",
        "",
        "## Overall Δfrac (pair-mean, bootstrap over pairs)",
        "",
        "```",
        overall[overall.metric == "frac"][
            [
                "rep",
                "budget",
                "n_pairs",
                "delta_mean",
                "delta_ci_lo",
                "delta_ci_hi",
                "n_pos",
                "n_neg",
                "n_near0",
            ]
        ]
        .round(4)
        .to_string(index=False),
        "```",
        "",
    ]
    note.write_text("\n".join(lines), encoding="utf-8")

    print("\n=== overall Δfrac (pair unit) ===")
    print(
        overall[overall.metric == "frac"][
            [
                "rep",
                "budget",
                "n_pairs",
                "delta_mean",
                "delta_ci_lo",
                "delta_ci_hi",
                "n_pos",
                "n_neg",
                "n_near0",
            ]
        ]
        .round(4)
        .to_string(index=False)
    )
    print(f"\nwrote {STATS / 'edbo_suzuki_pair_level_deltas.csv'}")
    print(f"wrote {note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
