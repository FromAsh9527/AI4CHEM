"""Strategy research step 3 — probe gate (docs/24 Phase 2, offline replay).

Mechanism: rank preservation is MEASURABLE (meta-features cannot guess it —
Phase 0). The probe gate measures it directly with a few probe experiments.

Design (mirrors the wet-lab protocol): the first round = pooled top-5 list
(probes). Using those 5 observations, estimate each source's consistency with
the target, then gate: keep pooled list / select sources / abstain.

Key validation: can a 5-point probe estimate the TRUE global rank preservation
(full-condition Spearman between source and target)? And does the gated list
beat the ungated pooled list on init_best?

Rules:
  G0: ungated pooled top-5 (baseline)
  G1: best-source top-5 (highest probe-consistency source)
  G2: select-sources pooled top-5 (sources with consistency >= median)
  G3: abstain -> random 5 (if best consistency < threshold)

Consistency measures: 5-point Spearman, and mean absolute yield gap on probes.

Usage:
    python scripts/analyze_probe_gate.py
Output:
    results/strategy_probe_gate/{per_target.csv, summary.md}
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "strategy_probe_gate"
TOP_K = 5
N_PROBE = 5
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
    return piv[piv.notna().sum(axis=1) >= min_support]


def topn(score: pd.Series, n: int, allowed: set) -> list:
    cand = score.loc[score.index.isin(allowed)].sort_values(ascending=False)
    return list(cand.index[:n])


def gate_for_target(mat: pd.DataFrame, tgt: str) -> dict:
    hist = mat.drop(columns=[tgt])
    tgt_y = mat[tgt]
    allowed = set(tgt_y.dropna().index)

    # probes = ungated pooled top-5 (mirrors wet-lab round 1)
    pooled_mean = hist.mean(axis=1)
    probes = topn(pooled_mean, N_PROBE, allowed)
    probe_y = tgt_y.reindex(probes)

    # per-source consistency on the 5 probe points
    src_spear, src_gap = {}, {}
    for s in hist.columns:
        sy = hist[s].reindex(probes)
        sub = pd.concat([probe_y, sy], axis=1).dropna()
        if len(sub) >= 4:
            r = spearmanr(sub.iloc[:, 0], sub.iloc[:, 1]).correlation
            src_spear[s] = float(r) if np.isfinite(r) else np.nan
        src_gap[s] = float((probe_y - hist[s].reindex(probes)).abs().mean())

    # true global rank preservation (full condition overlap) for validation
    global_rho = {}
    for s in hist.columns:
        sub = pd.concat([tgt_y, hist[s]], axis=1).dropna()
        if len(sub) >= 10:
            r = spearmanr(sub.iloc[:, 0], sub.iloc[:, 1]).correlation
            global_rho[s] = float(r) if np.isfinite(r) else np.nan

    # ---- rules ----
    results = {}
    # G0 baseline: pooled top-5
    results["G0_pooled"] = float(tgt_y.reindex(probes).max())

    # G1 best-source by probe Spearman
    valid_s = {s: v for s, v in src_spear.items() if v == v}
    if valid_s:
        best_s = max(valid_s, key=valid_s.get)
        lst = topn(hist[best_s], TOP_K, allowed)
        results["G1_best_source"] = float(tgt_y.reindex(lst).max())
        results["best_source_global_rho"] = global_rho.get(best_s, np.nan)
    # G1b best-source by probe gap (alternative consistency)
    if src_gap:
        best_g = min(src_gap, key=src_gap.get)
        lst = topn(hist[best_g], TOP_K, allowed)
        results["G1b_best_source_gap"] = float(tgt_y.reindex(lst).max())

    # G2 select sources with Spearman >= median
    if valid_s:
        med = float(np.nanmedian(list(valid_s.values())))
        sel = [s for s, v in valid_s.items() if v >= med]
        sub_hist = hist[sel]
        lst = topn(sub_hist.mean(axis=1), TOP_K, allowed)
        results["G2_select_sources"] = float(tgt_y.reindex(lst).max())

    # G3 abstain if best probe Spearman < threshold (random 5-point init)
    if valid_s:
        best_v = max(valid_s.values())
        results["G3_abstain_init_best"] = float(tgt_y.reindex(
            RNG.choice(sorted(allowed), size=TOP_K, replace=False)).max())
        results["G3_applied"] = float(best_v < 0.3)

    # validation: probe-based consistency vs global rho (per source, per target)
    rows_v = []
    for s in valid_s:
        rows_v.append({"target": tgt, "source": s,
                       "probe_spearman": valid_s[s],
                       "probe_gap": src_gap[s],
                       "global_rho": global_rho.get(s, np.nan)})
    results["_validation"] = rows_v
    return results


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    frame_rows, val_rows = [], []
    for lib, cfg in LIBRARIES.items():
        mat = load_matrix(cfg["db"])
        for tgt in mat.columns:
            res = gate_for_target(mat, tgt)
            base = res["G0_pooled"]
            for k, v in res.items():
                if k.startswith("G") and isinstance(v, float):
                    frame_rows.append({"library": lib, "target": tgt, "rule": k,
                                       "init_best": v, "delta_vs_pooled": v - base})
            val_rows.extend([{**r, "library": lib} for r in res.get("_validation", [])])
    df = pd.DataFrame(frame_rows)
    val = pd.DataFrame(val_rows)
    df.to_csv(OUT / "per_target.csv", index=False)
    val.to_csv(OUT / "probe_validation.csv", index=False)

    lines = ["# Probe gate (strategy research step 3, offline replay)", "",
             "Probes = ungated pooled top-5 (wet-lab round-1 mirror). Gate rules use the 5 probe "
             "observations only. Outcome = init_best of the gated list vs the pooled baseline.", ""]
    lines.append("| library | rule | mean init_best | Δ vs pooled | frac improved |")
    lines.append("|---|---|---|---|---|")
    for lib in df["library"].unique():
        base = df[(df["library"] == lib) & (df["rule"] == "G0_pooled")].set_index("target")["init_best"]
        for rule in df[df["library"] == lib]["rule"].unique():
            if rule == "G0_pooled":
                continue
            g = df[(df["library"] == lib) & (df["rule"] == rule)].set_index("target")["init_best"]
            d = (g - base).dropna()
            if len(d) < 3:
                continue
            lines.append(f"| {lib} | {rule} | {g.mean():.2f} | {d.mean():+.2f} | {np.mean(d > 1e-9):.2f} |")
    lines.append("")
    lines.append("## Probe validity: 5-point probe consistency vs TRUE global rank preservation")
    lines.append("")
    v = val.dropna(subset=["probe_spearman", "global_rho"])
    r_all, p_all = spearmanr(v["probe_spearman"], v["global_rho"])
    lines.append(f"- pooled Spearman(probe_spearman, global_rho) = **{r_all:+.3f}** (p={p_all:.2e}, n={len(v)})")
    for lib in v["library"].unique():
        sub = v[v["library"] == lib].dropna(subset=["probe_spearman", "global_rho"])
        if len(sub) >= 10:
            r, p = spearmanr(sub["probe_spearman"], sub["global_rho"])
            lines.append(f"  - {lib}: {r:+.3f} (p={p:.3f}, n={len(sub)})")
    lines.append("")
    g = val.dropna(subset=["probe_gap", "global_rho"])
    if len(g) >= 20:
        r, p = spearmanr(g["probe_gap"], g["global_rho"])
        lines.append(f"- probe gap vs global rho: {r:+.3f} (p={p:.3f}, n={len(g)}) — expected NEGATIVE (small gap = high consistency)")
    lines.append("")
    lines.append("## Verdict (docs/24 Phase 2)")
    lines.append("")
    lines.append("- If probe validity r > 0.3: 5-point probes estimate rank preservation — gate is mechanism-viable.")
    lines.append("- Gate rules: G1/G2 improve init_best in >= half of targets -> gating worth deploying;")
    lines.append("  if not -> report honestly: probes too noisy at 5 points; increase n_probe in wet lab or keep ungated pooled.")
    lines.append("")
    (OUT / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
