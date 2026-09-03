"""Learnability-cause quantification (offline, 4 libraries).

Answers the remaining question from the dual-channel mechanism (docs/19 §4.2):
  WHY does continuation learnability differ across libraries?
  (EDBO Suzuki topk-post +189 vs amination/borylation +51/+52 vs HiTEA +80)

Measures:
  A. Learnability (direct): per target x seed, fit the protocol GP (OHE, Matern-2.5
     ARD + White, normalize_y) on 5 random init conditions, predict the rest,
     Spearman(predicted rank, true rank). Mean over targets = library learnability.
  B. Landscape explainers:
     B1 high-value concentration: HHI of ligand/base/solvent frequencies among the
        target's top-10% conditions (high = good conditions cluster on few factors);
     B2 additive explainability: R^2 of yield ~ factor one-hot linear regression
        (library-wide; high = response surface is main-effect structured).

Associations:
  - learnability vs continuation value (topk post, from LOSO JSONs)
  - landscape explainers vs learnability

Usage:
    python scripts/analyze_learnability.py
Output:
    results/rank_preservation/learnability.csv + summary appended
"""

from __future__ import annotations

import json
import hashlib
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel, Matern, WhiteKernel
from sklearn.linear_model import LinearRegression

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "rank_preservation"

LIBRARIES = {
    "amination": {"db": ROOT / "data" / "db" / "transferbo2.db",
                  "json": ROOT / "results" / "amination_v1_full",
                  "factors": ["ligand", "base", "catalyst"]},
    "suzuki": {"db": ROOT / "data" / "db" / "transferbo2_suzuki.db",
               "json": ROOT / "results" / "suzuki_v1_full_rt" / "suzuki_v1_full",
               "factors": ["ligand", "base", "solvent"]},
    "borylation": {"db": ROOT / "data" / "db" / "transferbo2_borylation.db",
                   "json": ROOT / "results" / "p4_borylation" / "loso",
                   "factors": ["ligand", "solvent"]},
    "hitea": {"db": ROOT / "data" / "db" / "transferbo2_hitea.db",
              "json": ROOT / "results" / "p4_hitea" / "loso",
              "factors": ["catalyst_parsed", "solvent_parsed"]},
}
N_SEEDS = 3


def load_panel(db_path: Path, lib: str) -> tuple[pd.DataFrame, pd.DataFrame]:
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
    return panel, conds


def gp_learnability_factorwise(panel: pd.DataFrame, lib: str, factors: list[str]) -> pd.DataFrame:
    """GP zero-shot rank prediction using FACTOR one-hot features (low-dim,
    generalizes across conditions; measures response-surface learnability
    independent of the OHE protocol representation)."""
    import warnings
    warnings.filterwarnings("ignore")
    valid = [f for f in factors if f in panel.columns]
    X = pd.get_dummies(panel[valid].fillna("nan"), columns=valid).to_numpy(dtype=float)
    y = panel["yield"].to_numpy(dtype=float)
    rows = []
    for tgt, idx in panel.groupby("substrate_id").groups.items():
        if len(idx) <= 6:
            continue
        for seed in range(N_SEEDS):
            # NOTE: Python's built-in hash() on str is salted per process
            # (PYTHONHASHSEED), which made this analysis non-reproducible.
            # Use a deterministic digest instead.
            tgt_seed = int(hashlib.md5(tgt.encode("utf-8")).hexdigest()[:8], 16)
            rng = np.random.default_rng(1000 + tgt_seed % 100000 + seed)
            init = rng.choice(idx, size=5, replace=False)
            rest = np.setdiff1d(idx, init)
            if len(rest) < 5:
                continue
            kernel = ConstantKernel(1.0, (1e-3, 1e3)) * Matern(
                length_scale=np.ones(X.shape[1]), length_scale_bounds=(1e-2, 1e2), nu=2.5
            ) + WhiteKernel(noise_level=1e-3, noise_level_bounds=(1e-8, 1e1))
            gp = GaussianProcessRegressor(kernel=kernel, normalize_y=True,
                                          n_restarts_optimizer=1, alpha=1e-6,
                                          random_state=int(rng.integers(0, 2**31)))
            try:
                gp.fit(X[init], y[init])
                mu, _ = gp.predict(X[rest], return_std=True)
                if np.std(mu) < 1e-9:
                    continue
                r = spearmanr(mu, y[rest]).correlation
                if r is not None and np.isfinite(r):
                    rows.append({"library": lib, "target": tgt, "seed": seed,
                                 "gp_rank_corr": r, "n_rest": len(rest)})
            except Exception:
                continue
    if not rows:
        return pd.DataFrame(columns=["library", "target", "seed", "gp_rank_corr", "n_rest"])
    return pd.DataFrame(rows)


def hhi_top(panel: pd.DataFrame, lib: str, factors: list[str]) -> pd.Series:
    out = {}
    for tgt, g in panel.groupby("substrate_id"):
        g = g.sort_values("yield", ascending=False)
        top = g.iloc[: max(1, int(0.10 * len(g)))]
        hhi = 0.0
        for f in factors:
            if f not in top.columns:
                continue
            shares = top[f].value_counts(normalize=True)
            hhi = max(hhi, float((shares ** 2).sum()))
        out[tgt] = hhi
    return pd.Series(out)


def additive_r2(panel: pd.DataFrame, factors: list[str]) -> float:
    valid = [f for f in factors if f in panel.columns]
    X = pd.get_dummies(panel[valid].fillna("nan"), columns=valid)
    y = panel["yield"].to_numpy(dtype=float)
    reg = LinearRegression().fit(X, y)
    return float(reg.score(X, y))


def topk_post(json_dir: Path) -> pd.Series:
    rows = {}
    for p in sorted(Path(json_dir).glob("*.json")):
        if p.name.startswith("loso"):
            continue
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if rec.get("strategy") != "topk_warm" or "bo" not in rec:
            continue
        bsf = np.asarray(rec["bo"].get("best_so_far") or [], dtype=float)
        if len(bsf) < 20:
            continue
        auc = float(np.sum(bsf))
        carried = float(np.sum(bsf[:5]) + 15 * bsf[4])
        rows.setdefault(rec["target_substrate"], []).append(auc - carried)
    return pd.Series({t: float(np.mean(v)) for t, v in rows.items()})


def main() -> int:
    lib_rows = []
    tgt_rows = []
    for lib, cfg in LIBRARIES.items():
        panel, _ = load_panel(cfg["db"], lib)
        learn = gp_learnability_factorwise(panel, lib, cfg["factors"])
        learn_agg = learn.groupby("target")["gp_rank_corr"].mean()
        hhi = hhi_top(panel, lib, cfg["factors"])
        ar2 = additive_r2(panel, cfg["factors"])
        post = topk_post(cfg["json"])
        post_full = float(post.mean())  # full-target continuation value
        df = pd.DataFrame({"learnability": learn_agg, "hhi_top10": hhi, "topk_post": post}).dropna()
        df["library"] = lib
        tgt_rows.append(df.reset_index().rename(columns={"index": "target"}))
        lib_rows.append({
            "library": lib,
            "mean_learnability": float(learn["gp_rank_corr"].mean()) if len(learn) else np.nan,
            "n_learnable_targets": int(learn["target"].nunique()) if len(learn) else 0,
            "mean_hhi_top10": float(hhi.mean()),
            "additive_r2": ar2,
            "mean_topk_post": post_full,
        })
    libs = pd.DataFrame(lib_rows)
    tgts = pd.concat(tgt_rows, ignore_index=True)
    libs.to_csv(OUT / "learnability_library.csv", index=False)
    tgts.to_csv(OUT / "learnability_target.csv", index=False)

    lines = ["", "## Learnability-cause quantification (offline)", ""]
    lines.append("Learnability = protocol-GP zero-shot rank prediction (5 random init -> "
                 "Spearman on the rest); HHI = concentration of top-10% conditions on factors; "
                 "additive R2 = main-effect structure of the response surface.")
    lines.append("")
    lines.append("| library | learnability (GP rank ρ) | HHI top-10% | additive R² | topk post (continuation value) |")
    lines.append("|---|---|---|---|---|")
    for _, r in libs.iterrows():
        lines.append(f"| {r['library']} | {r['mean_learnability']:.3f} | {r['mean_hhi_top10']:.3f} "
                     f"| {r['additive_r2']:.3f} | {r['mean_topk_post']:+.1f} |")
    lines.append("")
    if len(libs) >= 4:
        from scipy.stats import spearmanr as sp
        r1, p1 = sp(libs["mean_learnability"], libs["mean_topk_post"])
        lines.append(f"- learnability vs continuation value: Spearman = **{r1:+.3f}** (p={p1:.2f}, n={len(libs)})")
        r2, p2 = sp(libs["mean_learnability"], libs["additive_r2"])
        lines.append(f"- learnability vs additive R²: Spearman = **{r2:+.3f}** (p={p2:.2f}, n={len(libs)})")
        r3, p3 = sp(libs["mean_learnability"], libs["mean_hhi_top10"])
        lines.append(f"- learnability vs HHI(top-10%): Spearman = **{r3:+.3f}** (p={p3:.2f}, n={len(libs)})")
    lines.append("")
    # target-level: learnability vs topk_post
    for lib in tgts["library"].unique():
        sub = tgts[tgts["library"] == lib]
        if len(sub) >= 8:
            r, p = spearmanr(sub["learnability"], sub["topk_post"])
            lines.append(f"- {lib} target-level: Spearman(learnability, topk_post) = {r:+.3f} (p={p:.2f}, n={len(sub)})")
    lines.append("")
    with open(OUT / "summary.md", "a", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
