"""Build all SNAr validation plating tables (docs/23 v2).

- 128-condition space: electrophile{2} x base{4} x solvent{4} x nuc_eq{2} x T{2}
- Stage 0: 36 shared conditions (stratified sample, fixed seed) x 4 history amines
  = 144 vials / 6 batches (24 per batch, batch-interleaved by condition group)
- Stage 1: 2 new amines x 2 arms x B=20 (round 1 = init, rounds 2-4 = EI);
  round 1 pre-generated (cold-5 fixed seed; topk-5 placeholder after Stage 0);
  rounds 2-4 = online template (EI outputs to be filled by BO loop)
- Scale: 4 mL (0.80 mmol DCP) or 2 mL (0.40 mmol) via --scale

Usage:
    python scripts/build_snar_plates.py --scale 4ml
    python scripts/build_snar_plates.py --scale 2ml
Output:
    results/p3_snar/scale_4ml/{materials.csv, stock_solutions.csv,
      stage0_conditions36.csv, plates_stage0_batch1..6.csv,
      plates_stage1_round1.csv, plates_stage1_rounds2_4_template.csv,
      plating_summary.md}
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SEED = 20260823

# ---------------------------------------------------------------- materials
MATERIALS = [
    # name, role, cas, mw, density(g/mL), stock_conc(M), form, note
    ("2,4-DCP", "electrophile", "3934-20-1", 148.98, None, 2.0, "solid", "moisture-sensitive; MeCN stock"),
    ("4,6-DCP", "electrophile", "1193-21-1", 148.98, None, 2.0, "solid", "MeCN stock"),
    ("aniline", "amine", "62-53-3", 93.13, 1.022, 2.0, "liquid", "history S1"),
    ("4-F-aniline", "amine", "371-40-4", 111.12, 1.173, 2.0, "liquid", "history S2"),
    ("BnNH2", "amine", "100-46-9", 107.15, 0.981, 2.0, "liquid", "history S3"),
    ("m-toluidine", "amine", "108-44-1", 107.15, 0.999, 2.0, "liquid", "history S4"),
    ("4-ethylaniline", "amine", "589-16-2", 121.18, 0.975, 2.0, "liquid", "validation T1"),
    ("2-F-aniline", "amine", "348-54-9", 111.12, 1.151, 2.0, "liquid", "validation T2"),
    ("NMM", "base", "109-02-4", 101.15, 0.920, 2.0, "liquid", "1.5 equiv when used"),
    ("DIPEA", "base", "7087-68-5", 129.24, 0.742, 2.0, "liquid", "1.5 equiv when used"),
    ("DBU", "base", "6674-22-2", 152.24, 1.019, 2.0, "liquid", "1.5 equiv when used"),
    ("MeCN", "solvent", "75-05-8", 41.05, 0.786, None, "liquid", ""),
    ("iPrOH", "solvent", "67-63-0", 60.10, 0.786, None, "liquid", ""),
    ("DMSO", "solvent", "67-68-5", 78.13, 1.100, None, "liquid", ""),
    ("dioxane", "solvent", "123-91-1", 88.11, 1.033, None, "liquid", ""),
    ("caffeine", "internal std", "58-08-2", 194.19, None, None, "solid", "in LC diluent"),
    ("HCOOH", "LC modifier", "64-18-6", 46.03, 1.220, None, "liquid", "0.1% in diluent"),
    ("2-Cl-N-phenylpyrimidin-4-amine", "calibration std", "191728-83-3", 205.65, None, None, "solid", "mono-substituted std (aniline)"),
]

ELECTROPHILES = ["2,4-DCP", "4,6-DCP"]
BASES = ["none", "NMM", "DIPEA", "DBU"]
SOLVENTS = ["MeCN", "iPrOH", "DMSO", "dioxane"]
NUC_EQ = [1.0, 3.0]
TEMPS = [25, 40]
HISTORY_AMINES = ["aniline", "4-F-aniline", "BnNH2", "m-toluidine"]
VALIDATION_AMINES = ["4-ethylaniline", "2-F-aniline"]
ANCHOR_COND = {"electrophile": "2,4-DCP", "base": "DIPEA", "solvent": "MeCN",
               "nuc_eq": 1.0, "temp_C": 40}


@dataclass
class Condition:
    electrophile: str
    base: str
    solvent: str
    nuc_eq: float
    temp_C: int

    @property
    def id(self) -> str:
        return f"{self.electrophile}|{self.base}|{self.solvent}|{self.nuc_eq:g}|{self.temp_C}"


def all_conditions() -> list[Condition]:
    return [
        Condition(e, b, s, q, t)
        for e in ELECTROPHILES
        for b in BASES
        for s in SOLVENTS
        for q in NUC_EQ
        for t in TEMPS
    ]


def sample_36() -> list[Condition]:
    """Stratified sample: cover all (electrophile x base x solvent) combos once
    (32), then add 4 balanced supplements; balanced on nuc_eq and temp."""
    rng = np.random.default_rng(SEED)
    allc = all_conditions()
    by_cell: dict[tuple, list[Condition]] = {}
    for c in allc:
        by_cell.setdefault((c.electrophile, c.base, c.solvent), []).append(c)

    picked: list[Condition] = []
    cells = sorted(by_cell)
    # deterministic pseudo-random order
    order = rng.permutation(len(cells))
    # alternate nuc_eq/temp across cells to keep balance
    for i, ci in enumerate(order):
        cell = cells[ci]
        opts = by_cell[cell]
        if i % 2 == 0:
            opts = sorted(opts, key=lambda c: (c.nuc_eq, c.temp_C))
        else:
            opts = sorted(opts, key=lambda c: (-c.nuc_eq, c.temp_C))
        picked.append(opts[i % len(opts)])

    # 4 supplements: pick 4 cells, add the (nuc_eq, temp) complement not chosen
    sup_cells = [cells[i] for i in order[:4]]
    for cell in sup_cells:
        chosen = {c.id for c in picked if (c.electrophile, c.base, c.solvent) == cell}
        for c in by_cell[cell]:
            if c.id not in chosen:
                picked.append(c)
                break
    assert len(picked) == 36
    return picked


def plate_volumes(scale_ml: float, cond: Condition, amine: str) -> dict:
    n_dcp_mmol = 0.20 * scale_ml  # mmol (0.20 M * mL)
    stock = {m[0]: m for m in MATERIALS}
    v_dcp = n_dcp_mmol / stock[cond.electrophile][5]
    n_amine = n_dcp_mmol * cond.nuc_eq
    v_amine = n_amine / stock[amine][5]
    v_base = 0.0
    if cond.base != "none":
        n_base = n_dcp_mmol * 1.5
        v_base = n_base / stock[cond.base][5]
    v_solv = scale_ml - v_dcp - v_amine - v_base
    if v_solv < 0:
        raise ValueError(f"negative solvent volume for {cond.id} {amine}")
    return {
        "v_dcp_uL": round(v_dcp * 1000, 1),
        "v_amine_uL": round(v_amine * 1000, 1),
        "v_base_uL": round(v_base * 1000, 1),
        "v_solvent_uL": round(v_solv * 1000, 1),
        "v_total_uL": round(scale_ml * 1000, 1),
    }


def row_for(scale_ml: float, batch: int, vial: int, cond: Condition, amine: str,
            arm: str = "", stage: str = "", note: str = "") -> dict:
    v = plate_volumes(scale_ml, cond, amine)
    return {
        "batch": batch, "vial": vial, "stage": stage, "arm": arm,
        "electrophile": cond.electrophile, "amine": amine,
        "base": cond.base, "solvent": cond.solvent,
        "nuc_eq": cond.nuc_eq, "temp_C": cond.temp_C,
        "scale_mL": scale_ml,
        "DCP_stock_uL": v["v_dcp_uL"], "amine_stock_uL": v["v_amine_uL"],
        "base_stock_uL": v["v_base_uL"], "solvent_uL": v["v_solvent_uL"],
        "total_uL": v["v_total_uL"], "note": note,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", choices=["4ml", "2ml"], default="4ml")
    args = ap.parse_args()
    scale_ml = 4.0 if args.scale == "4ml" else 2.0
    out = ROOT / "results" / "p3_snar" / f"scale_{args.scale}"
    out.mkdir(parents=True, exist_ok=True)

    # materials + stock solutions
    pd.DataFrame(MATERIALS, columns=["name", "role", "cas", "mw", "density", "stock_conc_M", "form", "note"]
                 ).to_csv(out / "materials.csv", index=False)
    stocks = []
    for m in MATERIALS:
        if m[5]:
            g = m[5] * m[3] * 0.010  # 10 mL stock
            stocks.append({"name": m[0], "cas": m[2], "conc_M": m[5],
                           "mass_g_per_10mL": round(g, 3), "solvent": "MeCN"})
    pd.DataFrame(stocks).to_csv(out / "stock_solutions.csv", index=False)

    # 36 shared conditions, 6 groups x 6
    cond36 = sample_36()
    rng = np.random.default_rng(SEED + 1)
    groups = np.array_split(rng.permutation(36), 6)
    cond_rows = []
    for gi, idx in enumerate(groups):
        for c in [cond36[i] for i in idx]:
            cond_rows.append({"group": gi + 1, "condition_id": c.id,
                              "electrophile": c.electrophile, "base": c.base,
                              "solvent": c.solvent, "nuc_eq": c.nuc_eq, "temp_C": c.temp_C})
    pd.DataFrame(cond_rows).to_csv(out / "stage0_conditions36.csv", index=False)

    # Stage 0: batch b = group b x all 4 history amines (24 vials/batch)
    rows = []
    for gi in range(6):
        gconds = [cond36[i] for i in groups[gi]]
        for vi, cond in enumerate(gconds):
            for amine in HISTORY_AMINES:
                rows.append(row_for(scale_ml, gi + 1, len(rows) + 1, cond, amine,
                                    stage="S0", note=f"group{gi+1}"))
    stage0 = pd.DataFrame(rows)
    stage0.to_csv(out / "plates_stage0_all.csv", index=False)
    for b in range(1, 7):
        stage0[stage0["batch"] == b].to_csv(out / f"plates_stage0_batch{b}.csv", index=False)

    # Stage 1 round 1: cold-5 fixed seed; topk-5 placeholder (needs Stage 0 results)
    allc = all_conditions()
    rng1 = np.random.default_rng(SEED + 2)
    s1_rows = []
    for amine in VALIDATION_AMINES:
        idx = rng1.choice(len(allc), size=5, replace=False)
        for i, ci in enumerate(idx):
            s1_rows.append(row_for(scale_ml, 7, len(s1_rows) + 1, allc[ci], amine,
                                   arm="B_cold", stage="S1_r1", note="cold-5, pre-generated"))
        for i in range(5):
            s1_rows.append(row_for(scale_ml, 7, len(s1_rows) + 1, Condition("2,4-DCP", "DIPEA", "MeCN", 1.0, 40),
                                   amine, arm="A_topk", stage="S1_r1",
                                   note="TOP-5 PLACEHOLDER - fill after Stage 0 (pooled mean rule)"))
    # anchors: standard condition, 2 replicates per validation amine
    for amine in VALIDATION_AMINES:
        for rep in (1, 2):
            s1_rows.append(row_for(scale_ml, 7, len(s1_rows) + 1,
                                   Condition(**ANCHOR_COND), amine,
                                   arm="anchor", stage="S1_r1",
                                   note=f"anchor rep{rep} (std cond)"))
    pd.DataFrame(s1_rows).to_csv(out / "plates_stage1_round1.csv", index=False)

    # Stage 1 rounds 2-4: template (EI online)
    tpl = []
    for rnd in (2, 3, 4):
        for amine in VALIDATION_AMINES:
            for arm in ("A_topk", "B_cold"):
                for i in range(5):
                    tpl.append({"batch": 6 + rnd, "stage": f"S1_r{rnd}", "arm": arm,
                                "amine": amine, "note": "EI point - fill online from BO loop"})
    pd.DataFrame(tpl).to_csv(out / "plates_stage1_rounds2_4_template.csv", index=False)

    # summary
    n_stage0 = len(stage0)
    lines = [
        f"# SNAr plating tables ({args.scale})",
        "",
        f"- scale: {scale_ml:g} mL/vial (DCP 0.20 M = {0.20*scale_ml:.2f} mmol)",
        f"- Stage 0: {n_stage0} vials (4 history amines x 36 shared conditions), 6 batches x 24",
        f"- Stage 1: 2 validation amines x 2 arms x B=20; round1 pre-generated "
        f"(cold-5 fixed seed; topk-5 placeholder after Stage 0); rounds 2-4 online EI template",
        f"- anchor: standard cond ({ANCHOR_COND}), 2 reps per validation amine per batch",
        f"- total pre-plated vials: {n_stage0 + 24} (Stage 0 + Stage 1 r1); online: 60 (rounds 2-4)",
        "",
        "## Stock solutions (10 mL, 2.0 M in MeCN)",
        "",
        "| name | CAS | mass g / 10 mL |",
        "|---|---|---|",
    ]
    for s in stocks:
        lines.append(f"| {s['name']} | {s['cas']} | {s['mass_g_per_10mL']} |")
    lines.append("")
    lines.append("## Reagent usage estimate (Stage 0 + Stage 1 r1)")
    lines.append("")
    df = pd.concat([stage0, pd.DataFrame(s1_rows)], ignore_index=True)
    usage = {}
    for _, r in df.iterrows():
        for key, name in (("DCP_stock_uL", r["electrophile"]), ("amine_stock_uL", r["amine"]),
                          ("base_stock_uL", r["base"])):
            if name != "none":
                usage[name] = usage.get(name, 0.0) + r[key]
    lines.append("| reagent | stock volume mL |")
    lines.append("|---|---|")
    for name, ul in sorted(usage.items()):
        lines.append(f"| {name} | {ul / 1000:.1f} |")
    lines.append("")
    (out / "plating_summary.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"\n[OK] wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
