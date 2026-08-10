#!/usr/bin/env python
"""Held-out / Gate evaluation grid (W8).

Default: target=plate_4 with --allow-heldout.
Compares cold / diversity / label / multitask / transfer_gate.

Examples:
  python scripts/run_gate_eval.py --dry-run
  python scripts/run_gate_eval.py --seed 0 --skip-existing
  python scripts/run_gate_eval.py --all-seeds --skip-existing
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from run_experiment import run_one  # noqa: E402
from transferbo.utils import ensure_dir, load_config, save_json  # noqa: E402
from transferbo.utils.protocol import apply_protocol, assert_not_tuning_heldout, load_protocol  # noqa: E402


def iter_jobs(cfg: dict, protocol: dict, *, target: str, sources: list[str], reps: list[str], seeds: list[int]):
    strategies = cfg.get("eval_strategies", [
        "cold_start",
        "diversity_warm",
        "label_warm",
        "multitask",
        "transfer_gate",
    ])
    for strat, rep, seed in itertools.product(strategies, reps, seeds):
        if strat in ("cold_start", "random"):
            yield strat, rep, None, target, seed
            continue
        for source in sources:
            if source == target:
                continue
            yield strat, rep, source, target, seed


def job_path(out_root: Path, strat: str, rep: str, source: str | None, target: str, seed: int) -> Path:
    return out_root / f"{strat}__{rep}__{source or 'none'}__{target}__seed{seed}.json"


def rebuild(out_root: Path) -> None:
    rows = []
    for p in out_root.glob("*.json"):
        if p.name.startswith("summary") or p.name.startswith("gate_"):
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        meta = d.get("meta") or {}
        rows.append(
            {
                "source_plate": d.get("source_plate"),
                "target_plate": d["target_plate"],
                "strategy": d["strategy"],
                "representation": d["representation"],
                "seed": d["seed"],
                "frac_of_opt": (
                    d["best_final"] / d["global_best"]
                    if d.get("global_best")
                    else None
                ),
                "queries_to_top5": (d.get("metrics") or {}).get("queries_to_top5"),
                "gate_mode": meta.get("gate_mode"),
                "gate_strategy": meta.get("gate_strategy"),
                "gate_score": meta.get("gate_score"),
            }
        )
    if not rows:
        return
    df = pd.DataFrame(rows)
    df.to_csv(out_root / "heldout_results.csv", index=False)

    # mode distribution for gate
    g = df[df["strategy"] == "transfer_gate"]
    if not g.empty:
        g["gate_mode"].value_counts(dropna=False).to_csv(out_root / "gate_mode_counts.csv")

    # mean frac by strategy
    summary = (
        df.groupby(["strategy", "representation", "source_plate"], dropna=False)["frac_of_opt"]
        .agg(["mean", "std", "count"])
        .reset_index()
    )
    summary.to_csv(out_root / "heldout_summary.csv", index=False)

    # vs cold / vs always label
    cold = (
        df[df["strategy"] == "cold_start"]
        .groupby("representation")["frac_of_opt"]
        .mean()
    )
    label = (
        df[df["strategy"] == "label_warm"]
        .groupby(["representation", "source_plate"])["frac_of_opt"]
        .mean()
    )
    gate = (
        df[df["strategy"] == "transfer_gate"]
        .groupby(["representation", "source_plate"])["frac_of_opt"]
        .mean()
    )
    cmp_rows = []
    for (rep, src), gmean in gate.items():
        c = cold.get(rep, float("nan"))
        l = label.get((rep, src), float("nan"))
        cmp_rows.append(
            {
                "representation": rep,
                "source_plate": src,
                "gate_frac": gmean,
                "cold_frac": c,
                "label_frac": l,
                "delta_vs_cold": gmean - c if pd.notna(c) else None,
                "delta_vs_label": gmean - l if pd.notna(l) else None,
            }
        )
    if cmp_rows:
        pd.DataFrame(cmp_rows).to_csv(out_root / "gate_vs_baselines.csv", index=False)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, default=ROOT / "configs/gate.yaml")
    ap.add_argument("--protocol", type=Path, default=ROOT / "configs/protocol.yaml")
    ap.add_argument("--target", type=str, default=None, help="default: protocol held_out")
    ap.add_argument("--reps", nargs="+", default=["morgan"])
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--all-seeds", action="store_true")
    ap.add_argument("--skip-existing", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--allow-heldout", action="store_true", default=True)
    ap.add_argument("--out", type=Path, default=ROOT / "results/gate/heldout_P4")
    args = ap.parse_args()

    protocol = load_protocol(args.protocol)
    cfg = apply_protocol(load_config(args.config), protocol)
    # ensure gate model path
    cfg.setdefault("gate", {})
    cfg["gate"].setdefault("model_dir", str(ROOT / "results/gate/freeze_W8"))

    target = args.target or protocol.get("held_out", {}).get("target_plate", "plate_4")
    assert_not_tuning_heldout(
        target=target,
        protocol=protocol,
        allow_heldout_eval=args.allow_heldout,
        purpose="gate_heldout_eval",
    )
    sources = [p for p in protocol.get("dev_targets", ["plate_1", "plate_2", "plate_3"]) if p != target]
    seeds = cfg.get("seeds", list(range(20)))
    if args.seed is not None:
        seeds = [args.seed]
    elif not args.all_seeds:
        seeds = [seeds[0]]

    jobs = list(iter_jobs(cfg, protocol, target=target, sources=sources, reps=args.reps, seeds=seeds))
    print(f"Jobs: {len(jobs)}  target={target}  reps={args.reps}  seeds={seeds}")
    if args.dry_run:
        for j in jobs[:20]:
            print(" ", j)
        if len(jobs) > 20:
            print(f"  ... +{len(jobs)-20} more")
        return 0

    out_root = ensure_dir(args.out)
    for i, (strat, rep, source, tgt, seed) in enumerate(jobs, 1):
        path = job_path(out_root, strat, rep, source, tgt, seed)
        if args.skip_existing and path.exists():
            print(f"[{i}/{len(jobs)}] skip {path.name}")
            continue
        print(f"[{i}/{len(jobs)}] {strat} {rep} {source}->{tgt} seed={seed}")
        run_cfg = dict(cfg)
        run_cfg["representation"] = dict(cfg.get("representation", {}))
        run_cfg["representation"]["name"] = rep
        rec = run_one(run_cfg, strategy_name=strat, source=source, target=tgt, seed=seed)
        save_json(rec, path)

    rebuild(out_root)
    print(f"Done. Tables in {out_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
