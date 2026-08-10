#!/usr/bin/env python
"""Run a single TransferBO experiment from a YAML config.

Examples:
  python scripts/run_experiment.py --config configs/default.yaml
  python scripts/run_experiment.py --config configs/default.yaml \\
      --strategy label_warm --source plate_1 --target plate_2 --seed 0
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from transferbo.data import PlateOracle, get_plate, load_plates  # noqa: E402
from transferbo.metrics import best_so_far_summary, queries_to_threshold  # noqa: E402
from transferbo.representations import build_representation  # noqa: E402
from transferbo.strategies import StrategyConfig, build_strategy  # noqa: E402
from transferbo.utils import ensure_dir, load_config, save_json, set_global_seed  # noqa: E402
from transferbo.utils.protocol import (  # noqa: E402
    apply_protocol,
    assert_not_tuning_heldout,
    load_protocol,
)


def _rep_kwargs(cfg: dict, name: str) -> dict:
    block = cfg.get("representation", {})
    kwargs = dict(block.get(name, {}) or {})
    # Resolve relative descriptor tables against project root
    tp = kwargs.get("table_path")
    if tp and not Path(tp).is_absolute():
        cand = ROOT / tp
        if cand.is_file() or not Path(tp).is_file():
            kwargs["table_path"] = str(cand)
    return kwargs


def encode_plate(
    rep_name: str,
    strings: list[str],
    cfg: dict,
    fit_strings: list[str],
):
    kwargs = _rep_kwargs(cfg, rep_name)
    # OHE must see the vocabulary used at transform time; fit on union
    rep = build_representation(rep_name, **kwargs)
    rep.fit(fit_strings)
    return rep, rep.transform(strings)


def _feature_strings(df: pd.DataFrame, rep_name: str) -> list[str]:
    """DRFP prefers reaction SMILES; other reps use additive SMILES."""
    if rep_name.lower() == "drfp" and "reaction_smiles" in df.columns:
        return df["reaction_smiles"].astype(str).tolist()
    return df["smiles"].astype(str).tolist()


def run_one(cfg: dict, *, strategy_name: str, source: str | None, target: str, seed: int) -> dict:
    set_global_seed(seed)
    data_cfg = cfg["data"]
    df = load_plates(
        data_cfg["processed_path"],
        plate_col=data_cfg.get("plate_col", "plate_id"),
        smiles_col=data_cfg.get("smiles_col", "smiles"),
        response_col=data_cfg.get("response_col", "response"),
        id_col=data_cfg.get("id_col", "additive_id"),
    )
    target_df = get_plate(df, target)
    source_df = get_plate(df, source) if source else None

    rep_name = cfg.get("representation", {}).get("name", "morgan")
    target_strings = _feature_strings(target_df, rep_name)
    fit_strings = list(target_strings)
    if source_df is not None:
        fit_strings = fit_strings + _feature_strings(source_df, rep_name)

    rep, X_target = encode_plate(rep_name, target_strings, cfg, fit_strings)
    X_source = None
    if source_df is not None:
        X_source = rep.transform(_feature_strings(source_df, rep_name))

    strat_cfg = cfg.get("strategy", {})
    bo_cfg = cfg.get("bo", {})
    transfer_cfg = cfg.get("transfer", {})
    config = StrategyConfig(
        n_init=int(strat_cfg.get("n_init", 20)),
        budget=int(bo_cfg.get("budget", 100)),
        acquisition=str(bo_cfg.get("acquisition", "ei")),
        batch_size=int(strat_cfg.get("batch_size", 1)),
        ucb_beta=float(bo_cfg.get("ucb_beta", 2.0)),
        backend=str(bo_cfg.get("backend", "sklearn")),
        normalize_y=bool(bo_cfg.get("normalize_y", True)),
        seed=seed,
        source_fraction=float(transfer_cfg.get("source_fraction", 1.0)),
        init_mode=str(strat_cfg.get("init_mode", "random")),
        max_warm_points=int(transfer_cfg.get("max_warm_points", strat_cfg.get("max_warm_points", 150))),
    )

    oracle = PlateOracle(target_df)
    strategy = build_strategy(strategy_name)
    run_kwargs = dict(
        target_oracle=oracle,
        X_target=X_target,
        config=config,
        source_df=source_df,
        X_source=X_source,
        representation=rep,
    )
    if strategy_name.lower() == "transfer_gate":
        gate_cfg = cfg.get("gate", {})
        model_dir = gate_cfg.get("model_dir")
        if not model_dir:
            raise ValueError("transfer_gate requires gate.model_dir in config (frozen Gate path)")
        run_kwargs["gate_model_dir"] = model_dir
        run_kwargs["representation_name"] = rep_name
        run_kwargs["neg_threshold"] = float(gate_cfg.get("neg_threshold", 0.45))
    result = strategy.run(**run_kwargs)

    metrics_cfg = cfg.get("metrics", {})
    top_fracs = metrics_cfg.get("top_fracs", [0.01, 0.05])
    metric_out = {}
    for frac in top_fracs:
        thr = oracle.top_frac_threshold(float(frac))
        q = queries_to_threshold([result.bo.best_so_far], thr)[0]
        metric_out[f"queries_to_top{int(float(frac)*100)}"] = q
        metric_out[f"threshold_top{int(float(frac)*100)}"] = thr

    return {
        "strategy": strategy_name,
        "representation": rep_name,
        "source_plate": source,
        "target_plate": target,
        "seed": seed,
        "metrics": metric_out,
        "best_final": result.bo.best_so_far[-1] if result.bo.best_so_far else None,
        "global_best": oracle.global_best(),
        "bo": result.bo.to_dict(),
        "meta": result.meta,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run TransferBO experiment")
    parser.add_argument("--config", type=Path, default=ROOT / "configs" / "default.yaml")
    parser.add_argument("--protocol", type=Path, default=ROOT / "configs" / "protocol.yaml")
    parser.add_argument("--strategy", type=str, default=None)
    parser.add_argument("--source", type=str, default=None)
    parser.add_argument("--target", type=str, default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--all-seeds", action="store_true", help="Run every seed in config")
    parser.add_argument(
        "--allow-heldout",
        action="store_true",
        help="Permit runs with target=protocol.held_out (frozen eval only)",
    )
    args = parser.parse_args(argv)

    protocol = load_protocol(args.protocol)
    cfg = apply_protocol(load_config(args.config), protocol)
    strategy = args.strategy or cfg.get("strategy", {}).get("name", "cold_start")
    source = args.source if args.source is not None else cfg.get("transfer", {}).get("source_plate")
    target = args.target or cfg.get("transfer", {}).get("target_plate", "plate_1")
    assert_not_tuning_heldout(
        target=target,
        protocol=protocol,
        allow_heldout_eval=args.allow_heldout,
        purpose="experiment",
    )
    seeds = cfg.get("seeds", [0])
    if args.seed is not None:
        seeds = [args.seed]
    elif not args.all_seeds:
        seeds = [seeds[0]]

    out_dir = ensure_dir(
        Path(cfg.get("experiment", {}).get("output_dir", "results"))
        / cfg.get("experiment", {}).get("name", "run")
        / f"{strategy}_{cfg.get('representation', {}).get('name', 'morgan')}"
        / f"{source or 'none'}__to__{target}"
    )

    records = []
    curves = []
    for seed in seeds:
        print(f">>> strategy={strategy}  {source} -> {target}  seed={seed}")
        rec = run_one(cfg, strategy_name=strategy, source=source, target=target, seed=seed)
        records.append(rec)
        curves.append(rec["bo"]["best_so_far"])
        save_json(rec, out_dir / f"seed_{seed}.json")

    summary = best_so_far_summary(curves)
    summary.to_csv(out_dir / "best_so_far_summary.csv", index=False)
    save_json(
        {
            "strategy": strategy,
            "source": source,
            "target": target,
            "seeds": seeds,
            "n_runs": len(records),
            "metrics_per_seed": [r["metrics"] for r in records],
        },
        out_dir / "summary.json",
    )
    print(f"Saved results to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
