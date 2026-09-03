"""Strategy research step 1 — list-rule family test (docs/21 §0b / strategy research).

Mechanism: "ranking transfers, magnitudes do not". The frozen list rule uses
cross-source MEAN (magnitudes). If the mechanism is right, rank-based rules
(rank aggregation) should be >= the mean rule.

Rules compared (pooled top-5, LOSO semantics, target-condition-restricted):
  - mean          : cross-source yield mean (FROZEN rule)
  - rank_mean     : cross-source mean of within-source condition ranks
  - rank_median   : cross-source median of within-source ranks
  - top10_consensus: frequency in each source's top-10% condition set
  - best_source   : single best source's top-5 (lower bound, from prior ablations)

Outcome per target: init_best = max yield of the recommended top-5 on the target.
Paired bootstrap CI vs the frozen mean rule.

Usage:
    python scripts/analyze_list_rules.py
Output:
    results/strategy_list_rules/{per_target.csv, summary.md}
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "strategy_list_rules"
TOP_K = 5
N_BOOT = 5000
RNG = np.random.default_rng(20260824)

LIBRARIES = {
    "amination": {"db": ROOT / "data" / "db" / "transferbo2.db"},
    "suzuki": {"db": ROOT / "data" / "db" / "transferbo2_suzuki.db"},
    "borylation": {"db": ROOT / "data" / "db" / "transferbo2_borylation.db"},
    "hitea": {"db": ROOT / "data" / "db" / "transferbo2_hitea.db"},
}


def load_matrix(db_path: Path, min_support: int = 2) -> pd.DataFrame:
    conn = sqlite3.connect(str(db_path))
    df = pd.read_sql("SELECT substrate_id, condition_id, yield FROM experiments", conn)
    conn.close()
    df = df.groupby(["substrate_id", "condition_id"], as_index=False)["yield"].mean()
    piv = df.pivot(index="condition_id", columns="substrate_id", values="yield")
    piv = piv[piv.notna().sum(axis=1) >= min_support]
    return piv


def rule_scores(hist: pd.DataFrame, rule: str) -> pd.Series:
    """Score conditions from the history panel (conditions x sources)."""
    if rule == "mean":
        return hist.mean(axis=1)
    if rule == "rank_mean":
        ranks = hist.rank(axis=0, method="average")  # per source: rank conditions
        return ranks.mean(axis=1)
    if rule == "rank_median":
        ranks = hist.rank(axis=0, method="average")
        return ranks.median(axis=1)
    if rule == "top10_consensus":
        n = max(1, int(0.10 * hist.shape[0]))
        top_sets = [set(hist[col].sort_values(ascending=False).index[:n]) for col in hist.columns]
        return pd.Series(
            {c: sum(c in s for s in top_sets) for c in hist.index}, dtype=float
        )
    if rule == "best_source":
        return hist.max(axis=1)
    raise ValueError(rule)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    rules = ["mean", "rank_mean", "rank_median", "top10_consensus", "best_source"]
    rows = []
    for lib, cfg in LIBRARIES.items():
        mat = load_matrix(cfg["db"])
        for tgt in mat.columns:
            hist = mat.drop(columns=[tgt])
            tgt_y = mat[tgt]
            for rule in rules:
                score = rule_scores(hist, rule)
                cand = score.loc[score.index.isin(tgt_y.index)].sort_values(ascending=False)
                top5 = cand.index[:TOP_K]
                rows.append({
                    "library": lib, "target": tgt, "rule": rule,
                    "init_best": float(tgt_y.reindex(top5).max()),
                })
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "per_target.csv", index=False)

    lines = ["# List-rule family test (mechanism: ranking transfers, magnitudes do not)", "",
             "Pooled top-5 by each rule (LOSO); outcome = init_best on the target. "
             "Paired bootstrap 95% CI vs the frozen mean rule.", ""]
    lines.append("| library | rule | mean init_best | Δ vs mean | 95% CI | frac ≥ mean |")
    lines.append("|---|---|---|---|---|---|")
    summary = []
    for lib in df["library"].unique():
        sub = df[df["library"] == lib]
        base = sub[sub["rule"] == "mean"].set_index("target")["init_best"]
        for rule in rules:
            g = sub[sub["rule"] == rule].set_index("target")["init_best"]
            d = (g - base).dropna()
            if len(d) < 3:
                continue
            boot = np.array([
                d.iloc[RNG.integers(0, len(d), size=len(d))].mean() for _ in range(N_BOOT)
            ])
            lo, hi = np.quantile(boot, [0.025, 0.975])
            frac = float(np.mean(d > 1e-9))
            lines.append(f"| {lib} | {rule} | {g.mean():.2f} | {d.mean():+.2f} | "
                         f"[{lo:+.2f}, {hi:+.2f}] | {frac:.2f} |")
            summary.append({"library": lib, "rule": rule, "mean_init_best": float(g.mean()),
                            "delta_vs_mean": float(d.mean()), "ci_lo": float(lo), "ci_hi": float(hi),
                            "frac_ge_mean": frac})
    lines.append("")
    # pooled across libraries
    base_p = df[df["rule"] == "mean"].set_index(["library", "target"])["init_best"]
    lines.append("## Pooled verdict")
    lines.append("")
    for rule in rules:
        g = df[df["rule"] == rule].set_index(["library", "target"])["init_best"]
        d = (g - base_p).dropna()
        if len(d) < 10:
            continue
        boot = np.array([
            d.iloc[RNG.integers(0, len(d), size=len(d))].mean() for _ in range(N_BOOT)
        ])
        lo, hi = np.quantile(boot, [0.025, 0.975])
        lines.append(f"- **{rule}** vs mean (pooled n={len(d)}): {d.mean():+.2f} [{lo:+.2f}, {hi:+.2f}], "
                     f"frac >= mean: {np.mean(d > 1e-9):.2f}")
    lines.append("")
    lines.append("## Reading (docs/21 §0b strategy research)")
    lines.append("")
    lines.append("- If rank-based rules >= mean (CI upper > 0 or not worse): the mechanism is consistent "
                 "with the strategy — magnitudes are not needed for the list; the frozen mean rule is a "
                 "ranking-preserving heuristic.")
    lines.append("- If rank-based rules clearly > mean: upgrade the CLI rule to rank aggregation.")
    lines.append("- If rank-based rules < mean: mechanism boundary needs revision (magnitudes carry signal "
                 "the ranking discards).")
    lines.append("")
    (OUT / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
