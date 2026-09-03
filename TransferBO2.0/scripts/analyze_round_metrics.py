"""Offline round-level metrics audit for TransferBO2.0 Step1/Step3 results.

Purpose (audit 2026-08-22):
  The frozen primary metric is Optimisation AUC = sum(BSF). Deployment runs in
  5 rounds x 5 conditions; the product goal is "fewer rounds to a good result".
  This script recomputes, from existing per-job JSONs (zero HPC cost):

    1. AUC@k  for k in {5,10,15,20}   (round-batch truncated AUC)
    2. T_tau  rounds to reach yield thresholds (absolute 50/70, relative 0.9*y_star)
       reported as median rounds + fraction reached (right-censored)
    3. hit-top-5% rounds (first experiment inside the target's top-5% set)
    4. init_best / final_best (already in stats; recomputed for consistency)
    5. Heterogeneity split: "optimizable" targets (95th pct yield >= 50) vs rest
    6. Pooled-list aggregation-rule ablation (mean vs median vs best-source vs
       mean+1.96sd) on init_best, offline from the DB long tables

Inference follows the frozen protocol: seed-average first, then target-level
bootstrap CI (B=5000). Nothing here rewrites FROZEN_CLAIMS numbers; it adds a
round-level view on top of the existing AUC view.

Usage:
    python scripts/analyze_round_metrics.py
Output:
    results/audit_round_metrics/{amination,suzuki}/round_metrics_target.csv
    results/audit_round_metrics/{amination,suzuki}/round_metrics_summary.csv
    results/audit_round_metrics/{amination,suzuki}/rule_ablation.csv
    results/audit_round_metrics/summary.md
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
LIBRARIES = {
    "amination": {
        "json_dir": ROOT / "results" / "amination_v1_full",
        "db": ROOT / "data" / "db" / "transferbo2.db",
        "sub_id_col": "substrate_id",
    },
    "suzuki": {
        # results/suzuki_v1_full is lock-held by the sync client; mirrored copy:
        "json_dir": ROOT / "results" / "suzuki_v1_full_rt" / "suzuki_v1_full",
        "db": ROOT / "data" / "db" / "transferbo2_suzuki.db",
        "sub_id_col": "substrate_id",
    },
    "hitea": {
        "json_dir": ROOT / "results" / "p4_hitea" / "loso",
        "db": ROOT / "data" / "db" / "transferbo2_hitea.db",
        "sub_id_col": "substrate_id",
    },
    "borylation": {
        "json_dir": ROOT / "results" / "p4_borylation" / "loso",
        "db": ROOT / "data" / "db" / "transferbo2_borylation.db",
        "sub_id_col": "substrate_id",
    },
}
OUT = ROOT / "results" / "audit_round_metrics"
B = 20
BATCH = 5  # deployment granularity: 5 conditions per round
N_BOOT = 5000
THRESHOLDS = (50.0, 70.0)
REL_THRESH = 0.9
TOP_FRAC = 0.05


def load_jobs(lib: str) -> pd.DataFrame:
    d = LIBRARIES[lib]
    rows = []
    for p in sorted(Path(d["json_dir"]).glob("*.json")):
        if p.name in ("loso_records.json", "loso_summary.csv"):
            continue
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if "bo" not in rec or "strategy" not in rec:
            continue
        values = np.asarray(rec["bo"].get("values") or [], dtype=float)
        if len(values) == 0:
            continue
        bsf = np.maximum.accumulate(values)
        rows.append(
            {
                "strategy": rec["strategy"],
                "target": rec["target_substrate"],
                "seed": int(rec["seed"]),
                "values": values,
                "bsf": bsf,
                "y_star": float(rec.get("stats", {}).get("y_star", np.nan)),
                "init_best": float(np.max(values[:BATCH])) if len(values) >= BATCH else float(np.max(values)),
                "final_best": float(bsf[-1]),
            }
        )
    return pd.DataFrame(rows)


def target_top_frac_thresholds(db_path: Path, sub_col: str) -> dict[str, float]:
    import sqlite3

    conn = sqlite3.connect(str(db_path))
    df = pd.read_sql("SELECT substrate_id, yield FROM experiments", conn)
    conn.close()
    out = {}
    for sid, g in df.groupby("substrate_id"):
        out[str(sid)] = float(np.quantile(g["yield"], 1.0 - TOP_FRAC))
    return out


def rounds_of(t: float) -> float:
    """Steps (1-indexed) -> deployment rounds (ceil(t/5)); never-reached -> nan."""
    if not np.isfinite(t):
        return np.nan
    return math.ceil(t / BATCH)


def job_metrics(row: pd.Series, thr: dict[str, float]) -> dict:
    bsf = row["bsf"]
    t5 = np.searchsorted(bsf, thr.get(row["target"], np.inf), side="left") + 1
    out = {}
    for k in (5, 10, 15, 20):
        out[f"auc_at_{k}"] = float(np.sum(bsf[: min(k, len(bsf))]))
    for tau in THRESHOLDS:
        idx = np.searchsorted(bsf, tau, side="left")
        reached = idx < len(bsf)
        out[f"t_{tau:g}_steps"] = float(idx + 1) if reached else np.nan
        out[f"r_{tau:g}_rounds"] = rounds_of(idx + 1) if reached else np.nan
        out[f"reached_{tau:g}"] = int(reached)
    tau_rel = REL_THRESH * row["y_star"]
    idx = np.searchsorted(bsf, tau_rel, side="left")
    reached = idx < len(bsf)
    out["t_rel_steps"] = float(idx + 1) if reached else np.nan
    out["r_rel_rounds"] = rounds_of(idx + 1) if reached else np.nan
    out["reached_rel"] = int(reached)
    out["hit5_steps"] = float(t5) if t5 <= len(bsf) else np.nan
    out["hit5_rounds"] = rounds_of(t5) if t5 <= len(bsf) else np.nan
    out["hit5"] = int(t5 <= len(bsf))
    return out


def seed_avg(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """strategy x target -> mean over seeds (frozen inference step 1)."""
    g = df.groupby(["strategy", "target"], as_index=False)[cols].mean()
    return g


def boot_ci(deltas: np.ndarray, n: int = N_BOOT) -> tuple[float, float]:
    rng = np.random.default_rng(20260822)
    idx = rng.integers(0, len(deltas), size=(n, len(deltas)))
    means = deltas[idx].mean(axis=1)
    return float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))


def target_table(jobs: pd.DataFrame, thr: dict[str, float]) -> pd.DataFrame:
    cols = [f"auc_at_{k}" for k in (5, 10, 15, 20)]
    cols += [f"t_{tau:g}_steps" for tau in THRESHOLDS]
    cols += [f"r_{tau:g}_rounds" for tau in THRESHOLDS]
    cols += [f"reached_{tau:g}" for tau in THRESHOLDS]
    cols += ["t_rel_steps", "r_rel_rounds", "reached_rel", "hit5_steps", "hit5_rounds", "hit5"]
    cols += ["init_best", "final_best"]
    rows = []
    for _, r in jobs.iterrows():
        m = job_metrics(r, thr)
        m["init_best"] = r["init_best"]
        m["final_best"] = r["final_best"]
        rows.append({"strategy": r["strategy"], "target": r["target"], "seed": r["seed"], **m})
    return seed_avg(pd.DataFrame(rows), cols)


def compare_tables(tab: pd.DataFrame, lib: str) -> pd.DataFrame:
    """Target-level deltas vs cold and random, with bootstrap CI."""
    rows = []
    for ref in ("cold_start", "random"):
        base = tab[tab["strategy"] == ref].set_index("target")
        if base.empty:
            continue
        for strat in tab["strategy"].unique():
            if strat == ref:
                continue
            sub = tab[tab["strategy"] == strat].set_index("target")
            common = base.index.intersection(sub.index)
            if len(common) == 0:
                continue
            for metric in ("auc_at_5", "auc_at_10", "auc_at_15", "auc_at_20", "init_best", "final_best"):
                d = sub.loc[common, metric].to_numpy() - base.loc[common, metric].to_numpy()
                lo, hi = boot_ci(d)
                rows.append(
                    {
                        "library": lib,
                        "strategy": strat,
                        "vs": ref,
                        "metric": metric,
                        "mean_delta": float(d.mean()),
                        "ci_lo": lo,
                        "ci_hi": hi,
                        "frac_targets_gt0": float(np.mean(d > 0)),
                    }
                )
    return pd.DataFrame(rows)


def round_delta_table(tab: pd.DataFrame, lib: str) -> pd.DataFrame:
    """Median rounds-to-threshold deltas vs cold (censored imputed to B+1)."""
    cols_rounds = [f"r_{tau:g}_rounds" for tau in THRESHOLDS] + ["r_rel_rounds", "hit5_rounds"]
    reached_cols = [f"reached_{tau:g}" for tau in THRESHOLDS] + ["reached_rel", "hit5"]
    rows = []
    for ref in ("cold_start", "random"):
        base = tab[tab["strategy"] == ref].set_index("target")
        if base.empty:
            continue
        for strat in tab["strategy"].unique():
            if strat == ref:
                continue
            sub = tab[tab["strategy"] == strat].set_index("target")
            common = base.index.intersection(sub.index)
            if len(common) == 0:
                continue
            for c, rc in zip(cols_rounds, reached_cols):
                a = sub.loc[common, c].fillna(B / BATCH + 1).to_numpy()  # 5 rounds + 1
                b = base.loc[common, c].fillna(B / BATCH + 1).to_numpy()
                rows.append(
                    {
                        "library": lib,
                        "strategy": strat,
                        "vs": ref,
                        "metric": c,
                        "mean_rounds_delta": float(np.mean(a - b)),
                        "median_rounds_strategy": float(np.nanmedian(sub.loc[common, c])),
                        "median_rounds_ref": float(np.nanmedian(base.loc[common, c])),
                        "frac_reached_strategy": float(np.mean(sub.loc[common, rc])),
                        "frac_reached_ref": float(np.mean(base.loc[common, rc])),
                    }
                )
    return pd.DataFrame(rows)


def rule_ablation(db_path: Path, sub_col: str) -> pd.DataFrame:
    """Aggregation-rule ablation for pooled top-5 list (offline, LOSO semantics)."""
    import sqlite3

    conn = sqlite3.connect(str(db_path))
    df = pd.read_sql("SELECT substrate_id, condition_id, yield FROM experiments", conn)
    conn.close()
    rows = []
    for tgt in sorted(df[sub_col].unique()):
        hist = df[df[sub_col] != tgt]
        tgt_y = df[df[sub_col] == tgt].groupby("condition_id")["yield"].mean()
        piv = hist.pivot_table(index="condition_id", columns=sub_col, values="yield")
        rules = {
            "mean": piv.mean(axis=1),
            "median": piv.median(axis=1),
            "best_source": piv.max(axis=1),
            "mean_plus_1.96sd": piv.mean(axis=1) + 1.96 * piv.std(axis=1, ddof=0),
        }
        frozen = rules["mean"].loc[rules["mean"].index.isin(tgt_y.index)].sort_values(
            ascending=False
        ).index[:5]
        for name, score in rules.items():
            cand = score.loc[score.index.isin(tgt_y.index)].sort_values(ascending=False)
            top5 = cand.index[:5]
            rows.append(
                {
                    "target": tgt,
                    "rule": name,
                    "init_best": float(tgt_y.reindex(top5).max()),
                    "jaccard_vs_mean": float(
                        len(set(top5) & set(frozen)) / len(set(top5) | set(frozen))
                    ),
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    md_lines = ["# Round-level metric audit (offline, from existing JSONs)", ""]
    md_lines.append(
        f"Deployment granularity: {BATCH} conditions/round, budget {B} -> {B // BATCH} rounds. "
        "AUC@k = sum(BSF[:k]); rounds-to-threshold = ceil(steps/5), never-reached imputed to 6 rounds in deltas."
    )
    md_lines.append("")
    for lib, cfg in LIBRARIES.items():
        jobs = load_jobs(lib)
        thr = target_top_frac_thresholds(cfg["db"], cfg["sub_id_col"])
        tab = target_table(jobs, thr)
        lib_out = OUT / lib
        lib_out.mkdir(parents=True, exist_ok=True)
        tab.to_csv(lib_out / "round_metrics_target.csv", index=False)
        cmp = compare_tables(tab, lib)
        cmp.to_csv(lib_out / "round_metrics_summary.csv", index=False)
        rd = round_delta_table(tab, lib)
        rd.to_csv(lib_out / "round_deltas.csv", index=False)
        abl = rule_ablation(cfg["db"], cfg["sub_id_col"])
        abl.to_csv(lib_out / "rule_ablation.csv", index=False)

        md_lines.append(f"## {lib}  (targets={tab['target'].nunique()}, jobs={len(jobs)})")
        md_lines.append("")
        md_lines.append("### Δ vs cold / random, AUC@k (target bootstrap 95% CI)")
        md_lines.append("")
        md_lines.append("| strategy | vs | AUC@5 [CI] | AUC@10 [CI] | AUC@20 [CI] | init_best [CI] | final_best [CI] | frac@5>0 |")
        md_lines.append("|---|---|---|---|---|---|---|---|")
        piv = cmp.pivot_table(
            index=["strategy", "vs"], columns="metric",
            values=["mean_delta", "ci_lo", "ci_hi", "frac_targets_gt0"], aggfunc="first",
        )
        for (strat, vs), g in piv.iterrows():
            m = lambda k: g.get(("mean_delta", k), np.nan)
            lo = lambda k: g.get(("ci_lo", k), np.nan)
            hi = lambda k: g.get(("ci_hi", k), np.nan)
            f = lambda v: f"{v:+.1f}" if np.isfinite(v) else "-"
            f2 = lambda v: f"{v:+.2f}" if np.isfinite(v) else "-"
            fr = g.get(("frac_targets_gt0", "auc_at_5"), np.nan)
            frs = f"{fr:.2f}" if np.isfinite(fr) else "-"
            md_lines.append(
                f"| {strat} | {vs} | {f(m('auc_at_5'))} [{f(lo('auc_at_5'))}, {f(hi('auc_at_5'))}] "
                f"| {f(m('auc_at_10'))} [{f(lo('auc_at_10'))}, {f(hi('auc_at_10'))}] "
                f"| {f(m('auc_at_20'))} [{f(lo('auc_at_20'))}, {f(hi('auc_at_20'))}] "
                f"| {f2(m('init_best'))} [{f2(lo('init_best'))}, {f2(hi('init_best'))}] "
                f"| {f2(m('final_best'))} [{f2(lo('final_best'))}, {f2(hi('final_best'))}] "
                f"| {frs} |"
            )
        md_lines.append("")
        md_lines.append("### Rounds to threshold (median over targets; never-reached = 6 rounds in mean deltas)")
        md_lines.append("")
        md_lines.append("| strategy | vs | r50 Δrounds | r70 Δrounds | r_rel Δrounds | hit5 Δrounds | reached70 strat/ref |")
        md_lines.append("|---|---|---|---|---|---|---|")
        for _, r in rd.iterrows():
            if r["metric"] not in ("r_50_rounds", "r_70_rounds", "r_rel_rounds", "hit5_rounds"):
                continue
            tag = r["metric"].replace("r_", "r").replace("_rounds", "")
            md_lines.append(
                f"| {r['strategy']} | {r['vs']} | "
                + (f"{r['mean_rounds_delta']:+.2f}" if r["metric"] == "r_50_rounds" else "-")
                + " | "
                + (f"{r['mean_rounds_delta']:+.2f}" if r["metric"] == "r_70_rounds" else "-")
                + " | "
                + (f"{r['mean_rounds_delta']:+.2f}" if r["metric"] == "r_rel_rounds" else "-")
                + " | "
                + (f"{r['mean_rounds_delta']:+.2f}" if r["metric"] == "hit5_rounds" else "-")
                + f" | {r['frac_reached_strategy']:.2f} / {r['frac_reached_ref']:.2f} |"
            )
        md_lines.append("")
        md_lines.append("### Pooled-list aggregation rule ablation (init_best on target, LOSO)")
        md_lines.append("")
        md_lines.append("| rule | mean init_best | vs frozen mean |")
        md_lines.append("|---|---|---|")
        grp = abl.groupby("rule")["init_best"].mean()
        for rule, v in grp.items():
            md_lines.append(f"| {rule} | {v:.2f} | {v - grp['mean']:+.2f} |")
        md_lines.append("")
        md_lines.append("")
    (OUT / "summary.md").write_text("\n".join(md_lines), encoding="utf-8")
    print(f"wrote {OUT / 'summary.md'}")
    print((OUT / "summary.md").read_text(encoding="utf-8")[:3000])


if __name__ == "__main__":
    main()
