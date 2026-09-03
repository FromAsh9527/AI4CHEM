"""Final P4 eligibility audit for Pfizer HiTEA (docs/18_p4_hitea_holdout.md §2).

Family comparison + chosen roster:
  - BUCHWALD: too sparse (max 30 core conditions per halide, 0 tasks >= 40) -> rejected
  - HYDROGENATION: too sparse -> rejected
  - ULLMANN: 6 tasks >= 40 but 81% failures, median yield 0 -> optional secondary
  - SUZUKI: 11 tasks >= 40 core conditions, 30% failures, median yield 14 -> PRIMARY

Chosen definition (pre-registered in docs/18):
  - task      = canonical Reactant_1 SMILES (aryl halide OR boronate as encoded;
                partner identity r2 varies within cell)
  - condition = Catalyst_2_ID_1_SMILES | Solvent_1_Name   (catalyst_2 = the real
                catalyst/ligand system; Catalyst_1 is Pd(OAc)2 in 99.7% of rows)
  - yield     = mean Product_Yield_PCT_Area_UV over the cell (partner, T, time, cat1)
  - core condition space = conditions observed on >= 3 tasks
  - roster    = tasks with >= 40 core conditions measured

Usage:
    python scripts/audit_hitea.py
Output:
    results/p4_hitea/audit.md, audit_task_roster.csv, audit_core_conditions.csv
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "raw" / "hitea" / "8_SEPT_APPROVED_full_dataset.csv"
OUT = ROOT / "results" / "p4_hitea"
MIN_CORE_CONDS = 40
MIN_SUPPORT = 3

HALIDE_RE = re.compile(r"\[[A-Za-z][a-z]?\](?:[^\]]*Br|Br|I|Cl|F)|Br|I|Cl", re.I)


def cond_of(row: pd.Series) -> str:
    c2 = str(row.get("catalyst_2_ID_1_SMILES") or "").strip()
    sv = str(row.get("Solvent_1_Name") or "").strip()
    return f"{c2}|{sv}"


def is_halide(smiles: str) -> bool:
    return bool(re.search(r"Br|\[Br|I\b|\[I|Cl", smiles)) and "B1" not in smiles and "B(" not in smiles


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    full = pd.read_csv(SRC, low_memory=False)
    lines = ["# Pfizer HiTEA — P4 eligibility audit (final)", ""]
    lines.append(f"source: `{SRC.name}`  rows: {len(full)}")
    lines.append("")

    fam_rows = {}
    for fam in ["BUCHWALD", "SUZUKI", "ULLMANN", "HYDROGENATION"]:
        sub = full[full["KeyWord_STD"] == fam].copy()
        sub["r1"] = sub["Reactant_1_SMILES"].astype(str).str.strip()
        sub["cond"] = sub.apply(cond_of, axis=1)
        sub["y"] = pd.to_numeric(sub["Product_Yield_PCT_Area_UV"], errors="coerce")
        sub = sub.dropna(subset=["y"])
        panel = sub.groupby(["r1", "cond"])["y"].mean().reset_index()
        sup = sub.groupby("cond")["r1"].nunique()
        core = set(sup[sup >= MIN_SUPPORT].index)
        per = panel[panel["cond"].isin(core)].groupby("r1")["cond"].nunique()
        fam_rows[fam] = {
            "rows": len(sub),
            "tasks": sub["r1"].nunique(),
            "n_cond": sub["cond"].nunique(),
            "core": len(core),
            "tasks_ge20": int((per >= 20).sum()),
            "tasks_ge40": int((per >= 40).sum()),
            "y_med": float(sub["y"].median()),
            "fail_frac": float((sub["y"] <= 1).mean()),
        }

    lines.append("## 1. Family comparison (task = Reactant_1, condition = catalyst_2|solvent)")
    lines.append("")
    lines.append("| family | rows | tasks | conditions | core(>=3) | tasks>=20 | tasks>=40 | yield med | fail<=1 |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for fam, r in fam_rows.items():
        lines.append(
            f"| {fam} | {r['rows']} | {r['tasks']} | {r['n_cond']} | {r['core']} "
            f"| {r['tasks_ge20']} | {r['tasks_ge40']} | {r['y_med']:.1f} | {r['fail_frac']:.2f} |"
        )
    lines.append("")
    lines.append("**裁决：SUZUKI 为主验证家族**（11 任务 >=40 核心条件、30% 失败样本、产率有区分度）；"
                 "BUCHWALD/HYDROGENATION 面板过稀被拒；ULLMANN 作可选次级（6 任务但 81% 失败）。")
    lines.append("")

    # 2) Suzuki roster
    sub = full[full["KeyWord_STD"] == "SUZUKI"].copy()
    sub["r1"] = sub["Reactant_1_SMILES"].astype(str).str.strip()
    sub["cond"] = sub.apply(cond_of, axis=1)
    sub["y"] = pd.to_numeric(sub["Product_Yield_PCT_Area_UV"], errors="coerce")
    sub = sub.dropna(subset=["y"])
    panel = sub.groupby(["r1", "cond"])["y"].mean().reset_index()
    sup = sub.groupby("cond")["r1"].nunique()
    core = set(sup[sup >= MIN_SUPPORT].index)
    core_conds = pd.DataFrame(
        {"condition_id": sorted(core), "n_tasks": [sup[c] for c in sorted(core)]}
    )
    core_conds.to_csv(OUT / "audit_core_conditions.csv", index=False)

    rows = []
    for r1, g in panel[panel["cond"].isin(core)].groupby("r1"):
        if len(g) < MIN_CORE_CONDS:
            continue
        yy = sub[sub["r1"] == r1]["y"]
        rows.append(
            {
                "task_id": f"hit_{len(rows) + 1:02d}",
                "reactant1_smiles": r1,
                "is_halide": is_halide(r1),
                "n_core_conds": len(g),
                "n_reactions": int(len(sub[sub["r1"] == r1])),
                "yield_mean": float(yy.mean()),
                "yield_median": float(yy.median()),
                "yield_95pct": float(yy.quantile(0.95)),
                "y_star": float(yy.max()),
                "frac_fail": float((yy <= 1).mean()),
            }
        )
    roster = pd.DataFrame(rows).sort_values("n_core_conds", ascending=False)
    roster.to_csv(OUT / "audit_task_roster.csv", index=False)

    lines.append("## 2. Suzuki candidate roster (>= 40 core conditions)")
    lines.append("")
    lines.append(f"**{len(roster)} tasks**；halide 类任务：{int(roster['is_halide'].sum())} 个。")
    lines.append("")
    lines.append("| task | is_halide | n_core | n_rxns | yield med | y95 | y* | fail frac |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for _, r in roster.iterrows():
        lines.append(
            f"| {r['task_id']} | {r['is_halide']} | {r['n_core_conds']} | {r['n_reactions']} "
            f"| {r['yield_median']:.1f} | {r['yield_95pct']:.1f} | {r['y_star']:.1f} | {r['frac_fail']:.2f} |"
        )
    lines.append("")
    lines.append(f"LOSO jobs = tasks x strategies x seeds = {len(roster)} x 6 x 5 = **{len(roster) * 30}**")
    lines.append("")

    (OUT / "audit.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
