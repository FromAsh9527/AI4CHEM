"""Strategy research step 2 — continuation decision rule (docs/24, component B).

Mechanism: continuation value = interaction learnability (low additive R² on the
history panel -> EI has room). Strategy question: can additive R² (history-only)
predict, per target, whether the EI continuation is worth running?

Outcome per target: C1 = AUC(topk_warm) - AUC(topk_random_post) (same init,
EI vs random continuation) — the value of running EI after the list.

Rule simulation: threshold theta on additive R² -> "continuation needed" if R² < theta.
Evaluate: mean C1 of targets ruled "continuation" vs "no continuation" (separation),
and AUC-loss if the rule wrongly skips continuation.

Usage:
    python scripts/analyze_continuation_rule.py
Output:
    results/strategy_continuation/{target_level.csv, summary.md}
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.linear_model import LinearRegression

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "strategy_continuation"

LIBRARIES = {
    "amination": {"db": ROOT / "data" / "db" / "transferbo2.db",
                  "json_topk": ROOT / "results" / "amination_v1_full",
                  "json_random": ROOT / "results" / "amination_matched_init_audit",
                  "factors": ["ligand", "base", "catalyst"]},
    "suzuki": {"db": ROOT / "data" / "db" / "transferbo2_suzuki.db",
               "json_topk": ROOT / "results" / "suzuki_v1_full_rt" / "suzuki_v1_full",
               "json_random": ROOT / "results" / "suzuki_p0_shared_init",
               "factors": ["ligand", "base", "solvent"]},
    "borylation": {"db": ROOT / "data" / "db" / "transferbo2_borylation.db",
                   "json_topk": ROOT / "results" / "p4_borylation" / "loso",
                   "json_random": ROOT / "results" / "p4_borylation" / "loso",
                   "factors": ["ligand", "solvent"]},
    "hitea": {"db": ROOT / "data" / "db" / "transferbo2_hitea.db",
              "json_topk": ROOT / "results" / "p4_hitea" / "loso",
              "json_random": ROOT / "results" / "p4_hitea" / "loso",
              "factors": ["catalyst_parsed", "solvent_parsed"]},
}


def load_panel(db_path: Path, lib: str) -> pd.DataFrame:
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    exp = pd.read_sql("SELECT substrate_id, condition_id, yield FROM experiments", conn)
    conds = pd.read_sql("SELECT condition_id, ligand, base, solvent, catalyst, condition_json FROM conditions", conn)
    conn.close()
    if lib == "hitea":
        parsed = conds["condition_json"].map(
            lambda s: json.loads(s).get("cond_str", "") if isinstance(s, str) else ""
        )
        parts = parsed.str.split("|", n=1)
        conds = conds.assign(
            catalyst_parsed=[p[0] if len(p) == 2 else "" for p in parts],
            solvent_parsed=[p[1] if len(p) == 2 else "" for p in parts],
        )
    panel = exp.merge(conds, on="condition_id", how="left")
    agg = {"yield": "mean"}
    for f in conds.columns:
        if f != "condition_id":
            agg[f] = "first"
    return panel.groupby(["substrate_id", "condition_id"], as_index=False).agg(agg)


def additive_r2(panel: pd.DataFrame, tgt: str, factors: list[str]) -> float:
    hist = panel[panel["substrate_id"] != tgt]
    valid = [f for f in factors if f in panel.columns]
    X = pd.get_dummies(hist[valid].fillna("nan"), columns=valid)
    y = hist["yield"].to_numpy(dtype=float)
    return float(LinearRegression().fit(X, y).score(X, y))


def mean_auc(json_dir: Path, strategy: str) -> pd.Series:
    rows = {}
    for p in sorted(Path(json_dir).glob("*.json")):
        if p.name.startswith("loso"):
            continue
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if rec.get("strategy") != strategy or "bo" not in rec:
            continue
        bsf = np.asarray(rec["bo"].get("best_so_far") or [], dtype=float)
        if len(bsf) < 20:
            continue
        t = rec["target_substrate"]
        rows.setdefault(t, []).append(float(np.sum(bsf)))
    return pd.Series({t: float(np.mean(v)) for t, v in rows.items()})


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    frames = []
    for lib, cfg in LIBRARIES.items():
        panel = load_panel(cfg["db"], lib)
        auc_topk = mean_auc(cfg["json_topk"], "topk_warm")
        auc_rand = mean_auc(cfg["json_random"], "topk_random_post")
        common = auc_topk.index.intersection(auc_rand.index)
        rows = []
        for t in common:
            rows.append({
                "library": lib, "target": t,
                "additive_r2": additive_r2(panel, t, cfg["factors"]),
                "c1_auc": float(auc_topk[t] - auc_rand[t]),
            })
        frames.append(pd.DataFrame(rows))
    df = pd.concat(frames, ignore_index=True)
    df.to_csv(OUT / "target_level.csv", index=False)

    lines = ["# Continuation decision rule (strategy research step 2)", "",
             "C1 = AUC(topk+EI) - AUC(topk+random): value of running EI after the list.",
             "additive R² (history panel) = main-effect structure; LOW R² -> interactions -> EI has room.",
             ""]
    lines.append("| library | n | mean C1 | mean additive R² | Spearman(R², C1) |")
    lines.append("|---|---|---|---|---|")
    for lib, g in df.groupby("library"):
        r = spearmanr(g["additive_r2"], g["c1_auc"]).correlation if len(g) >= 8 else np.nan
        lines.append(f"| {lib} | {len(g)} | {g['c1_auc'].mean():+.1f} | {g['additive_r2'].mean():.3f} | {r:+.3f} |")
    lines.append("")
    r_all, p_all = spearmanr(df["additive_r2"], df["c1_auc"])
    lines.append(f"- pooled Spearman(additive_r2, C1) = **{r_all:+.3f}** (p={p_all:.3f}, n={len(df)})")
    lines.append("")

    # threshold rule simulation
    lines.append("## Threshold rule: 'continuation needed if additive R² < theta'")
    lines.append("")
    lines.append("| theta | ruled 'no continuation' | mean C1 (no-cont. targets) | mean C1 (continuation targets) | separation |")
    lines.append("|---|---|---|---|---|")
    for theta in (0.15, 0.18, 0.20, 0.22, 0.25, 0.30):
        no = df[df["additive_r2"] >= theta]["c1_auc"]
        cont = df[df["additive_r2"] < theta]["c1_auc"]
        if len(no) < 3 or len(cont) < 3:
            continue
        sep = float(cont.mean() - no.mean())
        lines.append(f"| {theta:.2f} | {len(no)} | {no.mean():+.1f} | {cont.mean():+.1f} | {sep:+.1f} |")
    lines.append("")
    lines.append("## Reading (docs/24 component B)")
    lines.append("")
    lines.append("- If Spearman(R², C1) < 0 (negative): low main-effect structure predicts high continuation "
                 "value -> threshold rule is mechanism-consistent.")
    lines.append("- The rule is HONEST about budget: 'no continuation' means stop after the list (save "
                 "experiments); if those targets have small C1, little is lost.")
    lines.append("")
    (OUT / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
