#!/usr/bin/env python
"""SI experimental suite — thicken the computational experiment side.

Blocks (protocol.yaml si_checks + fairness SI knobs):
  1. ucb          — acquisition sensitivity on 3 locked pairs (+ cold baselines)
  2. source_frac  — label_warm with source_fraction in {0.1, 0.5} on key pairs
  3. budget50     — budget=50 EI on key pairs (+ cold)
  4. ninit10      — n_init=10 EI on key pairs (+ cold)

Examples:
  python scripts/run_si_suite.py --block ucb --dry-run
  python scripts/run_si_suite.py --block all --skip-existing
  python scripts/run_si_suite.py --block source_frac --seeds 0-19 --skip-existing
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from run_experiment import run_one  # noqa: E402
from transferbo.utils import ensure_dir, load_config, save_json  # noqa: E402
from transferbo.utils.protocol import (  # noqa: E402
    apply_protocol,
    assert_not_tuning_heldout,
    load_protocol,
)

# Locked SI pairs from protocol (dev fold only — never plate_4 for method tweaks)
UCB_PAIRS = [
    {
        "strategy": "label_warm",
        "representation": "morgan",
        "source": "plate_3",
        "target": "plate_2",
        "reason": "strongest_positive",
    },
    {
        "strategy": "diversity_warm",
        "representation": "morgan",
        "source": "plate_1",
        "target": "plate_3",
        "reason": "strong_negative",
    },
    {
        "strategy": "label_warm",
        "representation": "morgan",
        "source": "plate_1",
        "target": "plate_3",
        "reason": "weak_edge_case",
    },
]

FRAC_PAIRS = [
    {"strategy": "label_warm", "representation": "morgan", "source": "plate_3", "target": "plate_2"},
    {"strategy": "label_warm", "representation": "morgan", "source": "plate_2", "target": "plate_1"},
    {"strategy": "label_warm", "representation": "morgan", "source": "plate_1", "target": "plate_3"},
]

BUDGET_PAIRS = [
    {"strategy": "label_warm", "representation": "morgan", "source": "plate_3", "target": "plate_2"},
    {"strategy": "diversity_warm", "representation": "morgan", "source": "plate_1", "target": "plate_3"},
    {"strategy": "cold_start", "representation": "morgan", "source": None, "target": "plate_2"},
    {"strategy": "cold_start", "representation": "morgan", "source": None, "target": "plate_3"},
]


def parse_seeds(spec: str | None, default: list[int]) -> list[int]:
    if not spec:
        return list(default)
    if "-" in spec and "," not in spec:
        a, b = spec.split("-", 1)
        return list(range(int(a), int(b) + 1))
    return [int(x) for x in spec.split(",") if x.strip() != ""]


def job_name(block: str, strat: str, rep: str, source: str | None, target: str, seed: int, tag: str) -> str:
    return f"{block}__{strat}__{rep}__{source or 'none'}__{target}__{tag}__seed{seed}.json"


def base_cfg(protocol: dict) -> dict:
    cfg = apply_protocol(load_config(ROOT / "configs" / "default.yaml"), protocol)
    cfg.setdefault("transfer", {})
    cfg["transfer"]["max_warm_points"] = protocol.get("fairness", {}).get("max_warm_points", 150)
    return cfg


def make_run_cfg(
    cfg: dict,
    *,
    rep: str,
    acquisition: str,
    budget: int,
    n_init: int,
    source_fraction: float,
) -> dict:
    out = deepcopy(cfg)
    out["representation"] = dict(out.get("representation", {}))
    out["representation"]["name"] = rep
    out["bo"] = dict(out.get("bo", {}))
    out["bo"]["acquisition"] = acquisition
    out["bo"]["budget"] = budget
    out["strategy"] = dict(out.get("strategy", {}))
    out["strategy"]["n_init"] = n_init
    out["transfer"] = dict(out.get("transfer", {}))
    out["transfer"]["source_fraction"] = source_fraction
    return out


def iter_ucb_jobs(seeds: list[int]) -> Iterable[dict[str, Any]]:
    targets_need_cold = sorted({p["target"] for p in UCB_PAIRS})
    for target, seed in itertools.product(targets_need_cold, seeds):
        yield {
            "block": "ucb",
            "strategy": "cold_start",
            "representation": "morgan",
            "source": None,
            "target": target,
            "seed": seed,
            "acquisition": "ucb",
            "budget": 100,
            "n_init": 20,
            "source_fraction": 1.0,
            "tag": "acq-ucb",
            "reason": "ucb_cold_baseline",
        }
    for p, seed in itertools.product(UCB_PAIRS, seeds):
        yield {
            "block": "ucb",
            "strategy": p["strategy"],
            "representation": p["representation"],
            "source": p["source"],
            "target": p["target"],
            "seed": seed,
            "acquisition": "ucb",
            "budget": 100,
            "n_init": 20,
            "source_fraction": 1.0,
            "tag": "acq-ucb",
            "reason": p["reason"],
        }


def iter_frac_jobs(seeds: list[int], fracs: list[float]) -> Iterable[dict[str, Any]]:
    for p, frac, seed in itertools.product(FRAC_PAIRS, fracs, seeds):
        yield {
            "block": "source_frac",
            "strategy": p["strategy"],
            "representation": p["representation"],
            "source": p["source"],
            "target": p["target"],
            "seed": seed,
            "acquisition": "ei",
            "budget": 100,
            "n_init": 20,
            "source_fraction": float(frac),
            "tag": f"frac-{frac}",
            "reason": "source_fraction_scan",
        }


def iter_budget_jobs(seeds: list[int]) -> Iterable[dict[str, Any]]:
    for p, seed in itertools.product(BUDGET_PAIRS, seeds):
        yield {
            "block": "budget50",
            "strategy": p["strategy"],
            "representation": p["representation"],
            "source": p["source"],
            "target": p["target"],
            "seed": seed,
            "acquisition": "ei",
            "budget": 50,
            "n_init": 20,
            "source_fraction": 1.0,
            "tag": "budget-50",
            "reason": "short_budget_si",
        }


def iter_ninit_jobs(seeds: list[int]) -> Iterable[dict[str, Any]]:
    pairs = [
        {"strategy": "cold_start", "representation": "morgan", "source": None, "target": "plate_2"},
        {"strategy": "cold_start", "representation": "morgan", "source": None, "target": "plate_3"},
        {"strategy": "label_warm", "representation": "morgan", "source": "plate_3", "target": "plate_2"},
        {"strategy": "diversity_warm", "representation": "morgan", "source": "plate_1", "target": "plate_3"},
    ]
    for p, seed in itertools.product(pairs, seeds):
        yield {
            "block": "ninit10",
            "strategy": p["strategy"],
            "representation": p["representation"],
            "source": p["source"],
            "target": p["target"],
            "seed": seed,
            "acquisition": "ei",
            "budget": 100,
            "n_init": 10,
            "source_fraction": 1.0,
            "tag": "ninit-10",
            "reason": "smaller_init_si",
        }


def collect_jobs(blocks: list[str], seeds: list[int]) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    if "ucb" in blocks or "all" in blocks:
        jobs.extend(iter_ucb_jobs(seeds))
    if "source_frac" in blocks or "all" in blocks:
        jobs.extend(iter_frac_jobs(seeds, [0.1, 0.5]))
    if "budget50" in blocks or "all" in blocks:
        jobs.extend(iter_budget_jobs(seeds))
    if "ninit10" in blocks or "all" in blocks:
        jobs.extend(iter_ninit_jobs(seeds))
    # de-dup by filename fields
    seen = set()
    uniq = []
    for j in jobs:
        key = (j["block"], j["strategy"], j["representation"], j["source"], j["target"], j["seed"], j["tag"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(j)
    return uniq


def rebuild_block(out_root: Path, block: str) -> None:
    enriched = []
    for p in out_root.glob(f"{block}__*.json"):
        d = json.loads(p.read_text(encoding="utf-8"))
        si = d.get("si") or {}
        gb, bf = d.get("global_best"), d.get("best_final")
        enriched.append(
            {
                "block": block,
                "strategy": d.get("strategy"),
                "representation": d.get("representation"),
                "source_plate": d.get("source_plate"),
                "target_plate": d.get("target_plate"),
                "seed": d.get("seed"),
                "acquisition": si.get("acquisition"),
                "budget": si.get("budget"),
                "n_init": si.get("n_init"),
                "source_fraction": si.get("source_fraction"),
                "tag": si.get("tag"),
                "reason": si.get("reason"),
                "frac_of_opt": (bf / gb) if gb and bf is not None else None,
                "queries_to_top5": (d.get("metrics") or {}).get("queries_to_top5"),
            }
        )
    if not enriched:
        return
    df = pd.DataFrame(enriched)
    df.to_csv(out_root / f"{block}_results.csv", index=False)
    agg = (
        df.groupby(
            [
                "strategy",
                "representation",
                "source_plate",
                "target_plate",
                "acquisition",
                "budget",
                "n_init",
                "source_fraction",
                "tag",
            ],
            dropna=False,
        )
        .agg(
            frac_mean=("frac_of_opt", "mean"),
            frac_std=("frac_of_opt", "std"),
            q5_median=("queries_to_top5", "median"),
            n=("frac_of_opt", "count"),
        )
        .reset_index()
    )
    agg.to_csv(out_root / f"{block}_summary.csv", index=False)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--block",
        nargs="+",
        default=["all"],
        choices=["ucb", "source_frac", "budget50", "ninit10", "all"],
    )
    ap.add_argument("--seeds", type=str, default="0-19")
    ap.add_argument("--skip-existing", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-runs", type=int, default=None)
    ap.add_argument("--out", type=Path, default=ROOT / "results" / "si")
    ap.add_argument("--protocol", type=Path, default=ROOT / "configs" / "protocol.yaml")
    args = ap.parse_args()

    protocol = load_protocol(args.protocol)
    seeds = parse_seeds(args.seeds, protocol.get("fairness", {}).get("seeds", list(range(20))))
    cfg0 = base_cfg(protocol)
    jobs = collect_jobs(args.block, seeds)
    out_root = ensure_dir(args.out)

    if args.skip_existing:
        before = len(jobs)
        jobs = [
            j
            for j in jobs
            if not (
                out_root
                / job_name(
                    j["block"],
                    j["strategy"],
                    j["representation"],
                    j["source"],
                    j["target"],
                    j["seed"],
                    j["tag"],
                )
            ).exists()
        ]
        print(f"Jobs remaining: {len(jobs)} / {before}", flush=True)
    else:
        print(f"Jobs: {len(jobs)}", flush=True)

    for j in jobs:
        assert_not_tuning_heldout(
            target=j["target"],
            protocol=protocol,
            allow_heldout_eval=False,
            purpose="si_suite",
        )

    if args.max_runs is not None:
        jobs = jobs[: args.max_runs]
    if args.dry_run:
        for j in jobs[:25]:
            print(" ", j)
        if len(jobs) > 25:
            print(f"  ... +{len(jobs) - 25}")
        return 0

    for i, j in enumerate(jobs, 1):
        path = out_root / job_name(
            j["block"],
            j["strategy"],
            j["representation"],
            j["source"],
            j["target"],
            j["seed"],
            j["tag"],
        )
        print(
            f"[{i}/{len(jobs)}] {j['block']} {j['strategy']} {j['source']}->{j['target']} "
            f"acq={j['acquisition']} bud={j['budget']} init={j['n_init']} "
            f"frac={j['source_fraction']} seed={j['seed']}",
            flush=True,
        )
        run_cfg = make_run_cfg(
            cfg0,
            rep=j["representation"],
            acquisition=j["acquisition"],
            budget=j["budget"],
            n_init=j["n_init"],
            source_fraction=j["source_fraction"],
        )
        rec = run_one(
            run_cfg,
            strategy_name=j["strategy"],
            source=j["source"],
            target=j["target"],
            seed=j["seed"],
        )
        rec["si"] = {
            "block": j["block"],
            "acquisition": j["acquisition"],
            "budget": j["budget"],
            "n_init": j["n_init"],
            "source_fraction": j["source_fraction"],
            "tag": j["tag"],
            "reason": j["reason"],
        }
        save_json(rec, path)

    for block in sorted({j["block"] for j in collect_jobs(args.block, seeds)}):
        rebuild_block(out_root, block)
    print(f"Done. Results in {out_root}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
