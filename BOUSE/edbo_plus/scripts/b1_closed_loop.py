# -*- coding: utf-8 -*-
"""
Suzuki B1 闭环：无初始观测 → EDBO+ 推荐 → 查表回填真值 → 再推荐。

用法（conda: edbo_plus）::

    cd BOUSE/edbo_plus
    python scripts/b1_closed_loop.py
    python scripts/b1_closed_loop.py --batch 3 --max-rounds 20 --seed 0
"""
from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from botorch.utils.multi_objective.hypervolume import Hypervolume
from sklearn.preprocessing import MinMaxScaler

ROOT = Path(__file__).resolve().parents[1]
B1 = ROOT / "edboplus-master" / "examples" / "publication" / "Suzuki" / "data" / "dataset_B1.csv"
FACTORS = ["ligand", "base", "solvent", "ligand_equivalent"]
OBJS = ["objective_conversion", "objective_selectivity"]


def _save_csv_retry(df: pd.DataFrame, path: Path, retries: int = 8) -> None:
    last = None
    for i in range(retries):
        try:
            df.to_csv(path, index=False)
            return
        except PermissionError as e:
            last = e
            time.sleep(0.4 * (i + 1))
    raise last  # type: ignore[misc]


def _pareto_mask(Y: np.ndarray) -> np.ndarray:
    """Y: (n, m) maximization. True = non-dominated."""
    n = len(Y)
    keep = np.ones(n, dtype=bool)
    for i in range(n):
        if not keep[i]:
            continue
        for j in range(n):
            if i == j or not keep[j]:
                continue
            if np.all(Y[j] >= Y[i]) and np.any(Y[j] > Y[i]):
                keep[i] = False
                break
    return keep


def hypervolume(Y: np.ndarray, scaler: MinMaxScaler, ref_raw: np.ndarray) -> float:
    if len(Y) == 0:
        return 0.0
    Ys = scaler.transform(Y)
    rs = scaler.transform(ref_raw.reshape(1, -1))[0]
    hv = Hypervolume(ref_point=torch.tensor(rs, dtype=torch.double))
    return float(hv.compute(pareto_Y=torch.tensor(Ys, dtype=torch.double)))


def main() -> int:
    ap = argparse.ArgumentParser(description="EDBO+ B1 closed-loop oracle test")
    ap.add_argument("--batch", type=int, default=3)
    ap.add_argument("--max-rounds", type=int, default=20)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--acq", default="EHVI", choices=["EHVI", "NoisyEHVI"])
    ap.add_argument("--init", default="cvt", choices=["cvt", "lhs", "random"])
    ap.add_argument("--hv-stop", type=float, default=0.95, help="stop when HV/HV_ground >= this")
    ap.add_argument("--name", default="b1_closed_loop")
    args = ap.parse_args()

    if str(ROOT / "edboplus-master") not in sys.path:
        # editable install should already expose edbo; keep local fallback
        pass

    from edbo.plus.optimizer_botorch import EDBOplus

    ground = pd.read_csv(B1).copy()
    ground.insert(0, "new_index", np.arange(len(ground), dtype=int))
    key = FACTORS

    best_conv = float(ground[OBJS[0]].max())
    best_sel = float(ground[OBJS[1]].max())
    ground["prod"] = ground[OBJS[0]] * ground[OBJS[1]]
    best_prod_row = ground.loc[ground["prod"].idxmax()]
    best_prod = float(best_prod_row["prod"])

    Yg = ground[OBJS].to_numpy(dtype=float)
    scaler = MinMaxScaler().fit(Yg)
    ref = Yg.min(axis=0)
    pareto_g = Yg[_pareto_mask(Yg)]
    hv_g = hypervolume(pareto_g, scaler, ref)

    print("=" * 64)
    print("Suzuki B1 closed-loop (no seed observations)")
    print(f"  n={len(ground)}  batch={args.batch}  acq={args.acq}  init={args.init}  seed={args.seed}")
    print(f"  best conversion = {best_conv}")
    print(f"  best selectivity = {best_sel}")
    print(f"  best product point = conv {best_prod_row[OBJS[0]]:.2f} / sel {best_prod_row[OBJS[1]]:.2f}")
    print(f"    { {c: best_prod_row[c] for c in key} }")
    print(f"  ground HV = {hv_g:.6f}  Pareto size = {len(pareto_g)}")
    print("=" * 64)

    # 默认写到仓库 workspaces/ 下（百度网盘已改为定时备份，不再锁文件）
    if Path(args.name).is_absolute() or str(args.name).startswith("."):
        ws = Path(args.name).resolve()
    else:
        ws = ROOT / "workspaces" / Path(args.name).name
    if ws.exists():
        shutil.rmtree(ws, ignore_errors=True)
    ws.mkdir(parents=True, exist_ok=True)
    pointer = ROOT / "workspaces" / f"{Path(args.name).name}_LAST_RUN.txt"
    try:
        pointer.parent.mkdir(parents=True, exist_ok=True)
        pointer.write_text(str(ws), encoding="utf-8")
    except OSError:
        pass
    print(f"  workspace = {ws}")

    scope = ground[["new_index"] + key].copy()
    csv_path = ws / "reaction.csv"
    _save_csv_retry(scope, csv_path)

    log_rows = []
    found_best_conv_at = None
    found_best_sel_at = None
    found_best_prod_at = None
    found_hv95_at = None

    opt = EDBOplus()
    t0 = time.time()

    for rnd in range(1, args.max_rounds + 1):
        t_r = time.time()
        print(f"\n--- Round {rnd} ---")
        df = opt.run(
            objectives=OBJS,
            objective_mode=["max", "max"],
            objective_thresholds=None,
            directory=str(ws),
            filename="reaction.csv",
            columns_features=key,
            batch=args.batch,
            init_sampling_method=args.init,
            seed=args.seed,
            acquisition_function=args.acq,
        )

        pending = df[df["priority"] >= 0.5].copy()
        if len(pending) == 0:
            pending = df[df["priority"] >= 0].head(args.batch).copy()
        pending = pending.head(args.batch)

        # oracle backfill by new_index
        for idx in pending.index:
            nid = int(df.at[idx, "new_index"])
            g = ground.loc[ground["new_index"] == nid].iloc[0]
            for o in OBJS:
                df.at[idx, o] = float(g[o])
        _save_csv_retry(df, csv_path)

        # metrics on observed
        obs = df.copy()
        for o in OBJS:
            obs[o] = pd.to_numeric(obs[o], errors="coerce")
        observed = obs.dropna(subset=OBJS)
        n_obs = len(observed)
        cur_best_c = float(observed[OBJS[0]].max()) if n_obs else 0.0
        cur_best_s = float(observed[OBJS[1]].max()) if n_obs else 0.0
        cur_best_p = float((observed[OBJS[0]] * observed[OBJS[1]]).max()) if n_obs else 0.0

        Yt = observed[OBJS].to_numpy(dtype=float)
        pareto_t = Yt[_pareto_mask(Yt)] if n_obs else np.zeros((0, 2))
        hv_t = hypervolume(pareto_t, scaler, ref) if n_obs else 0.0
        hv_pct = 100.0 * hv_t / hv_g if hv_g > 0 else 0.0

        # which of this round's samples
        shown = []
        for _, row in pending.iterrows():
            nid = int(row["new_index"])
            g = ground.loc[ground["new_index"] == nid].iloc[0]
            shown.append(
                f"#{nid} {g['ligand']}/{g['base']}/{g['solvent']}/{g['ligand_equivalent']} "
                f"→ C={g[OBJS[0]]:.1f} S={g[OBJS[1]]:.1f}"
            )
            if abs(float(g[OBJS[0]]) - best_conv) < 1e-9 and found_best_conv_at is None:
                found_best_conv_at = rnd
            if abs(float(g[OBJS[1]]) - best_sel) < 1e-9 and found_best_sel_at is None:
                found_best_sel_at = rnd
            if abs(float(g["prod"]) - best_prod) < 1e-6 and found_best_prod_at is None:
                found_best_prod_at = rnd

        if found_hv95_at is None and hv_pct >= args.hv_stop * 100:
            found_hv95_at = rnd

        for s in shown:
            print("  sample:", s)
        print(
            f"  n_obs={n_obs}  bestC={cur_best_c:.1f}/{best_conv}  "
            f"bestS={cur_best_s:.1f}/{best_sel}  bestProd={cur_best_p:.0f}/{best_prod:.0f}  "
            f"HV={hv_pct:.1f}%  ({time.time()-t_r:.1f}s)"
        )

        log_rows.append(
            {
                "round": rnd,
                "n_experiments": n_obs,
                "best_conversion": cur_best_c,
                "best_selectivity": cur_best_s,
                "best_product": cur_best_p,
                "hv_pct": hv_pct,
                "elapsed_s": round(time.time() - t0, 1),
                "samples": " | ".join(shown),
            }
        )
        pd.DataFrame(log_rows).to_csv(ws / "loop_log.csv", index=False)

        stop = False
        reasons = []
        if found_best_prod_at is not None:
            reasons.append(f"best product point @ round {found_best_prod_at}")
            stop = True
        if found_hv95_at is not None:
            reasons.append(f"HV>={args.hv_stop*100:.0f}% @ round {found_hv95_at}")
            # don't force stop only on HV unless also near product; keep going until product or max
        if found_best_conv_at and found_best_sel_at:
            reasons.append(
                f"global best C@{found_best_conv_at} & S@{found_best_sel_at}"
            )
            # both extremes found — strong stop
            stop = True

        if stop:
            print("\nSTOP:", "; ".join(reasons))
            break
    else:
        print("\nReached max rounds without early stop.")

    print("\n" + "=" * 64)
    print("SUMMARY")
    print(f"  rounds run          : {log_rows[-1]['round'] if log_rows else 0}")
    print(f"  experiments total   : {log_rows[-1]['n_experiments'] if log_rows else 0}")
    print(f"  found best conversion round : {found_best_conv_at}")
    print(f"  found best selectivity round: {found_best_sel_at}")
    print(f"  found best product round    : {found_best_prod_at}")
    print(f"  HV>={args.hv_stop*100:.0f}% first round       : {found_hv95_at}")
    if log_rows:
        print(f"  final best C/S/prod : {log_rows[-1]['best_conversion']:.1f} / "
              f"{log_rows[-1]['best_selectivity']:.1f} / {log_rows[-1]['best_product']:.0f}")
        print(f"  final HV%           : {log_rows[-1]['hv_pct']:.1f}%")
        print(f"  wall time           : {log_rows[-1]['elapsed_s']}s")
    print(f"  log                 : {ws / 'loop_log.csv'}")
    print("=" * 64)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
