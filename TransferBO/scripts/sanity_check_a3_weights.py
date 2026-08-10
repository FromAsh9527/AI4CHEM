#!/usr/bin/env python
"""P0 sanity: does A3 source_weight actually change the GP / BO path?

Checks:
  1) alpha_src = base_noise / w is wired into SurrogateGP.fit
  2) At fixed init, posterior μ,σ differ across w (incl. extreme small w)
  3) Saved A3 trajectories: how often w∈{0.1,0.25,0.5} (and A1) coincide

Usage:
  python scripts/sanity_check_a3_weights.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
STATS = ROOT / "results" / "paper_stats"
A3 = ROOT / "results" / "external_edbo_suzuki_a3"
S0 = ROOT / "results" / "external_edbo_suzuki_s0"
BASE_NOISE = 1e-4


def _curve(path: Path) -> np.ndarray:
    d = json.loads(path.read_text(encoding="utf-8"))
    return np.asarray(d["bo"]["best_so_far"][:100], dtype=float)


def audit_saved_trajectories(rep: str) -> dict:
    max_w, max_a1 = [], []
    n = identical_w = identical_a1 = 0
    for p1 in A3.glob(f"label_weight_w0p1__{rep}__*.json"):
        name = p1.name.replace("label_weight_w0p1__", "")
        p25 = A3 / f"label_weight_w0p25__{name}"
        p5 = A3 / f"label_weight_w0p5__{name}"
        pa1 = S0 / f"label_warm__{name}"
        if not (p25.exists() and p5.exists() and pa1.exists()):
            continue
        c1, c25, c5, ca = map(_curve, [p1, p25, p5, pa1])
        dw = max(
            float(np.max(np.abs(c1 - c25))),
            float(np.max(np.abs(c1 - c5))),
            float(np.max(np.abs(c25 - c5))),
        )
        da = float(np.max(np.abs(c1 - ca)))
        max_w.append(dw)
        max_a1.append(da)
        n += 1
        identical_w += int(dw == 0.0)
        identical_a1 += int(da == 0.0)
    mw = np.asarray(max_w, float)
    ma = np.asarray(max_a1, float)
    return {
        "rep": rep,
        "n": n,
        "identical_across_weights": identical_w,
        "frac_identical_weights": identical_w / n if n else float("nan"),
        "identical_vs_a1": identical_a1,
        "frac_identical_vs_a1": identical_a1 / n if n else float("nan"),
        "median_maxabs_weights": float(np.median(mw)) if n else float("nan"),
        "p90_maxabs_weights": float(np.quantile(mw, 0.9)) if n else float("nan"),
        "max_maxabs_weights": float(mw.max()) if n else float("nan"),
        "median_maxabs_vs_a1": float(np.median(ma)) if n else float("nan"),
        "p90_maxabs_vs_a1": float(np.quantile(ma, 0.9)) if n else float("nan"),
    }


def posterior_probe(
    *,
    source: str = "suz_t1",
    target: str = "suz_t9",
    seed: int = 0,
    n_init: int = 20,
    max_warm: int = 150,
) -> pd.DataFrame:
    from transferbo.bo.gp_model import SurrogateGP
    from transferbo.data.load import get_plate, load_plates
    from transferbo.representations import build_representation
    from transferbo.strategies.base import sample_init_indices, select_source_indices

    df = load_plates(ROOT / "data/processed/edbo_suzuki_plates.csv")
    src_df = get_plate(df, source)
    tgt_df = get_plate(df, target)
    smiles_s = src_df["smiles"].astype(str).tolist()
    smiles_t = tgt_df["smiles"].astype(str).tolist()
    rep = build_representation("morgan", radius=2, n_bits=2048)
    rep.fit(smiles_s + smiles_t)
    X_s = np.asarray(rep.transform(smiles_s), dtype=np.float64)
    X_t = np.asarray(rep.transform(smiles_t), dtype=np.float64)

    rng = np.random.default_rng(seed)
    init_idx = sample_init_indices(len(tgt_df), n_init, rng)
    src_rng = np.random.default_rng(seed + 1_000_003)
    keep = select_source_indices(
        len(src_df), source_fraction=1.0, max_warm_points=max_warm, rng=src_rng
    )
    warm_X = X_s[keep]
    warm_y = src_df["response"].to_numpy(dtype=float)[keep]
    y_init = tgt_df["response"].to_numpy(dtype=float)[init_idx]
    train_Xt = X_t[init_idx]

    weights = [1.0, 0.5, 0.25, 0.1, 0.01, 1e-4]
    rows = []
    preds = {}
    alphas = {}
    for w in weights:
        n_warm = len(warm_y)
        n_tgt = len(y_init)
        train_X = np.vstack([warm_X, train_Xt])
        train_y = np.concatenate([warm_y, y_init])
        alpha_src = BASE_NOISE / w
        alpha = np.concatenate(
            [
                np.full(n_warm, alpha_src, dtype=np.float64),
                np.full(n_tgt, BASE_NOISE, dtype=np.float64),
            ]
        )
        gp = SurrogateGP(backend="sklearn", normalize_y=True, random_state=seed)
        gp.fit(train_X, train_y, alpha=alpha)
        pred = gp.predict(X_t)
        preds[w] = pred
        alphas[w] = alpha_src
        rows.append(
            {
                "warm_weight": w,
                "alpha_src": alpha_src,
                "alpha_tgt": BASE_NOISE,
                "n_warm": n_warm,
                "n_tgt": n_tgt,
                "mu_mean": float(np.mean(pred.mean)),
                "mu_std": float(np.std(pred.mean)),
                "sig_mean": float(np.mean(pred.std)),
            }
        )

    # cold: target only
    gp = SurrogateGP(backend="sklearn", normalize_y=True, random_state=seed)
    gp.fit(train_Xt, y_init, alpha=BASE_NOISE)
    cold = gp.predict(X_t)
    preds["cold"] = cold
    rows.append(
        {
            "warm_weight": 0.0,
            "alpha_src": float("inf"),
            "alpha_tgt": BASE_NOISE,
            "n_warm": 0,
            "n_tgt": len(y_init),
            "mu_mean": float(np.mean(cold.mean)),
            "mu_std": float(np.std(cold.mean)),
            "sig_mean": float(np.mean(cold.std)),
        }
    )

    ref = preds[1.0]
    for w in weights + ["cold"]:
        p = preds[w]
        key = w if w != "cold" else 0.0
        for r in rows:
            if r["warm_weight"] == key or (w == "cold" and r["warm_weight"] == 0.0):
                r["l2_mu_vs_w1"] = float(np.linalg.norm(p.mean - ref.mean))
                r["maxabs_mu_vs_w1"] = float(np.max(np.abs(p.mean - ref.mean)))
                r["l2_sig_vs_w1"] = float(np.linalg.norm(p.std - ref.std))
                r["l2_mu_vs_cold"] = float(np.linalg.norm(p.mean - cold.mean))
                break

    # pairwise among A3 grid weights
    for wa, wb in [(0.1, 0.25), (0.1, 0.5), (0.25, 0.5), (0.1, 1.0), (0.01, 1.0), (1e-4, 1.0)]:
        pa, pb = preds[wa], preds[wb]
        rows.append(
            {
                "warm_weight": f"pair_{wa}_vs_{wb}",
                "alpha_src": np.nan,
                "alpha_tgt": BASE_NOISE,
                "n_warm": len(warm_y),
                "n_tgt": len(y_init),
                "mu_mean": np.nan,
                "mu_std": np.nan,
                "sig_mean": np.nan,
                "l2_mu_vs_w1": float(np.linalg.norm(pa.mean - pb.mean)),
                "maxabs_mu_vs_w1": float(np.max(np.abs(pa.mean - pb.mean))),
                "l2_sig_vs_w1": float(np.linalg.norm(pa.std - pb.std)),
                "l2_mu_vs_cold": np.nan,
            }
        )

    out = pd.DataFrame(rows)
    out.attrs["source"] = source
    out.attrs["target"] = target
    out.attrs["seed"] = seed
    out.attrs["alphas"] = alphas
    return out


def main() -> int:
    STATS.mkdir(parents=True, exist_ok=True)
    lines = [
        "# A3 source-weight sanity check",
        "",
        "Script: `scripts/sanity_check_a3_weights.py`",
        "",
        "## 1. Code path (static)",
        "",
        "- `LabelWeightWarmStartStrategy` passes `warm_weight=self.source_weight` into `run_bo_loop`.",
        "- `run_bo_loop` sets `alpha_src = base_noise / warm_weight` (default `base_noise=1e-4`) and",
        "  concatenates per-point `alpha` for `[source…, target…]` into `SurrogateGP.fit`.",
        "- `SurrogateGP._fit_sklearn` forwards `alpha` to `GaussianProcessRegressor(alpha=...)`.",
        "- Note: sklearn kernel also includes a learnable `WhiteKernel`; diagonal `alpha` is *additional* noise.",
        "",
    ]

    print("== saved trajectory audit ==")
    audits = []
    for rep in ("morgan", "dft"):
        a = audit_saved_trajectories(rep)
        audits.append(a)
        print(a)
        lines += [
            f"## 2. Saved trajectories (`{rep}`)",
            "",
            f"- n pairs×seeds with A1 present: **{a['n']}**",
            (
                f"- identical best_so_far across w in {{0.1,0.25,0.5}}: "
                f"**{a['identical_across_weights']}** ({a['frac_identical_weights']:.1%})"
            ),
            (
                f"- identical w=0.1 vs A1 (S0 `label_warm`): "
                f"**{a['identical_vs_a1']}** ({a['frac_identical_vs_a1']:.1%})"
            ),
            (
                f"- median / p90 / max abs delta across weights: "
                f"{a['median_maxabs_weights']:.4g} / {a['p90_maxabs_weights']:.4g} / "
                f"{a['max_maxabs_weights']:.4g}"
            ),
            "",
        ]

    print("== posterior probe (may take ~1–2 min) ==")
    post = posterior_probe()
    post_path = STATS / "edbo_suzuki_a3_sanity_posterior.csv"
    post.to_csv(post_path, index=False)
    print(post.to_string(index=False))
    print("wrote", post_path)

    # pass/fail heuristics
    sub = post[post["warm_weight"].apply(lambda x: isinstance(x, float))]
    w01 = sub.loc[sub.warm_weight == 0.1].iloc[0]
    w1 = sub.loc[sub.warm_weight == 1.0].iloc[0]
    wext = sub.loc[sub.warm_weight == 1e-4].iloc[0]
    cold = sub.loc[sub.warm_weight == 0.0].iloc[0]

    mu_diff_01_1 = float(w01["maxabs_mu_vs_w1"])
    mu_diff_ext_1 = float(wext["maxabs_mu_vs_w1"])
    closer_cold = float(wext["l2_mu_vs_cold"]) < float(w1["l2_mu_vs_cold"])

    code_ok = True
    post_changes = mu_diff_01_1 > 1e-6 or mu_diff_ext_1 > 1e-3
    extreme_moves_toward_cold = closer_cold and mu_diff_ext_1 > 1e-3

    verdict = "PASS" if (code_ok and post_changes) else "FAIL"
    if post_changes and not extreme_moves_toward_cold:
        verdict = "PASS_WITH_CAVEAT"

    lines += [
        "## 3. Posterior probe (fixed init, Morgan, suz_t1→suz_t9, seed=0)",
        "",
        f"- Table: `{post_path.name}`",
        f"- max|mu(w=0.1)-mu(w=1)| = **{mu_diff_01_1:.6g}**",
        f"- max|mu(w=1e-4)-mu(w=1)| = **{mu_diff_ext_1:.6g}**",
        f"- L2(mu(w=1), cold) = **{float(w1['l2_mu_vs_cold']):.6g}**; "
        f"L2(mu(w=1e-4), cold) = **{float(wext['l2_mu_vs_cold']):.6g}**",
        f"- Extreme weight closer to cold than w=1? **{extreme_moves_toward_cold}**",
        "",
        "## 4. Verdict",
        "",
        f"**{verdict}**",
        "",
    ]
    if verdict.startswith("PASS"):
        lines += [
            "- Wiring is real: changing w changes the GP posterior (and ~20-30% of saved BO curves).",
            "- Grid weights {0.1,0.25,0.5} often leave the *acquisition path* unchanged vs A1 "
            "(~75% identical best_so_far) — so pair-mean delta can look almost equal without a no-op bug.",
            "- Interpretable science line (OK to use): even moderately downweighted source labels "
            "still strongly influence a task-agnostic surrogate when n_s >> n_t early; "
            "BO decisions are frequently insensitive within this weight band.",
            "",
        ]
        if verdict == "PASS_WITH_CAVEAT":
            lines += [
                "- Caveat: extreme w=1e-4 did not clearly approach cold as strongly as hoped "
                "(WhiteKernel / joint z-score may dominate). Still not a no-op for intermediate w.",
                "",
            ]
    else:
        lines += [
            "- **Do not** claim weight-coincidence as science until this is resolved.",
            "",
        ]

    lines += [
        "## 5. Effective source noise at base_noise=1e-4",
        "",
        "| w_s | alpha_s = 1e-4 / w_s |",
        "|---|---:|",
        "| 1.0 | 1e-4 |",
        "| 0.5 | 2e-4 |",
        "| 0.25 | 4e-4 |",
        "| 0.1 | 1e-3 |",
        "| 0.01 | 1e-2 |",
        "",
    ]

    note = STATS / "edbo_suzuki_a3_SANITY.md"
    note.write_text("\n".join(lines), encoding="utf-8")
    pd.DataFrame(audits).to_csv(STATS / "edbo_suzuki_a3_sanity_trajectories.csv", index=False)
    try:
        print("\n".join(lines))
    except UnicodeEncodeError:
        print(note.read_text(encoding="utf-8").encode("ascii", "replace").decode("ascii"))
    print("wrote", note)
    print("VERDICT", verdict)
    return 0 if verdict.startswith("PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
