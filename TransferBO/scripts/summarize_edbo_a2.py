#!/usr/bin/env python
"""Summarize A2 rank-pooling vs S0 cold; side-by-side with S0 A1 raw."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

NEAR = 0.02
BUDGETS = [30, 40, 50, 100]
ROOT = Path(__file__).resolve().parents[1]
A2 = ROOT / "results" / "external_edbo_suzuki_a2"
S0 = ROOT / "results" / "external_edbo_suzuki_s0"
STATS = ROOT / "results" / "paper_stats"


def load_jsons(root: Path, prefix: str, rep: str) -> pd.DataFrame:
    rows = []
    for p in root.glob(f"{prefix}__{rep}__*.json"):
        d = json.loads(p.read_text(encoding="utf-8"))
        g = float(d["global_best"])
        curve = [float(v) for v in d["bo"]["best_so_far"][:100]]
        rows.append(
            {
                "strategy": d["strategy"],
                "source": d.get("source_plate"),
                "target": d["target_plate"],
                "seed": int(d["seed"]),
                "global_best": g,
                "curve": curve,
                "init": tuple((d.get("meta") or {}).get("init_indices") or []),
            }
        )
    return pd.DataFrame(rows)


def boot_ci(x: np.ndarray, seed: int = 0):
    rng = np.random.default_rng(seed)
    boots = [
        float(np.mean(rng.choice(x, size=len(x), replace=True))) for _ in range(3000)
    ]
    return float(np.mean(x)), float(np.quantile(boots, 0.025)), float(np.quantile(boots, 0.975))


def pair_delta(lab: pd.DataFrame, cold: pd.DataFrame, arm: str, rep: str) -> pd.DataFrame:
    rows = []
    for B in BUDGETS:
        c = cold.copy()
        c["c"] = [cur[B - 1] / g for cur, g in zip(c.curve, c.global_best)]
        l = lab.copy()
        l["l"] = [cur[B - 1] / g for cur, g in zip(l.curve, l.global_best)]
        m = l.merge(
            c[["target", "seed", "c"]].drop_duplicates(["target", "seed"]),
            on=["target", "seed"],
        )
        m["delta"] = m["l"] - m["c"]
        pair = m.groupby(["source", "target"], as_index=False).agg(delta=("delta", "mean"))
        x = pair.delta.to_numpy(float)
        mu, lo, hi = boot_ci(x, seed=B + 41)
        rows.append(
            {
                "arm": arm,
                "rep": rep,
                "budget": B,
                "n_pairs": len(pair),
                "delta_mean": mu,
                "delta_ci_lo": lo,
                "delta_ci_hi": hi,
                "n_pos": int((x > NEAR).sum()),
                "n_neg": int((x < -NEAR).sum()),
                "n_near0": int((np.abs(x) <= NEAR).sum()),
            }
        )
    return pd.DataFrame(rows)


def main() -> int:
    STATS.mkdir(parents=True, exist_ok=True)
    frames = []
    for rep in ("morgan", "dft"):
        cold = load_jsons(S0, "cold_start", rep)
        a2 = load_jsons(A2, "label_rank_warm", rep)
        a1 = load_jsons(S0, "label_warm", rep)
        cmap = {(r.target, r.seed): r.init for r in cold.itertuples(index=False)}
        m2 = sum(1 for r in a2.itertuples(index=False) if cmap.get((r.target, r.seed)) == r.init)
        print(f"{rep}: a2={len(a2)} a1={len(a1)} cold={len(cold)} a2_init_match={m2}/{len(a2)}")
        frames.append(pair_delta(a2, cold, "A2_rank", rep))
        frames.append(pair_delta(a1, cold, "A1_raw_S0", rep))

    out = pd.concat(frames, ignore_index=True)
    out.to_csv(STATS / "edbo_suzuki_a2_vs_s0_pair_overall.csv", index=False)
    print("\n=== pair Δfrac (vs S0 cold) ===")
    print(
        out[out.budget.isin([40, 100])][
            ["arm", "rep", "budget", "delta_mean", "delta_ci_lo", "delta_ci_hi", "n_pos", "n_neg", "n_near0"]
        ]
        .round(4)
        .to_string(index=False)
    )
    note = STATS / "edbo_suzuki_a2_NOTE.md"
    note.write_text(
        "\n".join(
            [
                "# A2 rank / percentile pooling (EDBO Suzuki)",
                "",
                "- Dir: `results/external_edbo_suzuki_a2/`",
                "- Arm: `label_rank_warm` vs S0 `cold_start` (matched init)",
                "- Question: is A1 failure only yield-scale mismatch?",
                "",
                "```",
                out.round(4).to_string(index=False),
                "```",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"\nwrote {STATS / 'edbo_suzuki_a2_vs_s0_pair_overall.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
