#!/usr/bin/env python
"""Export EDBO Suzuki condition-library descriptor tables (Morgan / DRFP).

Unique X = ligand||base||solvent (308). Substrates are not in features.
Writes CSV under data/descriptors/ for archival, visualization, and later
table-backed runs. Does not modify experiment configs or running grids.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from transferbo.representations import build_representation  # noqa: E402


def _fp_frame(keys: pd.Series, key_name: str, X: np.ndarray, prefix: str) -> pd.DataFrame:
    X = np.asarray(X)
    if np.allclose(X, np.round(X)) and X.min() >= 0 and X.max() <= 1:
        X_out = np.rint(X).astype(np.int8)
    else:
        X_out = X.astype(np.float64)
    cols = [f"{prefix}_{i}" for i in range(X_out.shape[1])]
    out = pd.DataFrame(X_out, columns=cols)
    out.insert(0, key_name, keys.astype(str).values)
    return out


def _update_manifest(out_dir: Path) -> None:
    rows = []
    for p in sorted(out_dir.glob("*.csv")):
        if p.name == "MANIFEST.csv":
            continue
        n = p.stat().st_size
        rows.append({"file": p.name, "bytes": n, "mb": round(n / 1e6, 3)})
    pd.DataFrame(rows).to_csv(out_dir / "MANIFEST.csv", index=False)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--plates",
        type=Path,
        default=ROOT / "data" / "processed" / "edbo_suzuki_plates.csv",
    )
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "data" / "descriptors",
    )
    ap.add_argument("--n-bits", type=int, default=2048)
    ap.add_argument("--radius", type=int, default=2)
    ap.add_argument("--skip-morgan", action="store_true")
    ap.add_argument("--skip-drfp", action="store_true")
    args = ap.parse_args()

    df = pd.read_csv(args.plates)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    # One row per unique condition key (shared across all substrate tasks).
    key_cols = ["smiles"]
    if "reaction_smiles" in df.columns:
        key_cols.append("reaction_smiles")
    meta_cols = [c for c in [
        "smiles",
        "reaction_smiles",
        "additive_id",
        "candidate_key",
        "ligand_smiles",
        "base_smiles",
        "solvent_smiles",
    ] if c in df.columns]
    uniq = df.drop_duplicates(subset=["smiles"]).loc[:, meta_cols].copy()
    uniq = uniq.reset_index(drop=True)
    print(f"unique conditions: {len(uniq)}  (from {len(df)} plate rows)")

    if not args.skip_morgan:
        smiles = uniq["smiles"].astype(str).tolist()
        print("encoding morgan (multi-component concat) ...")
        morgan = build_representation("morgan", radius=args.radius, n_bits=args.n_bits)
        morgan.fit(smiles)
        Xm = morgan.transform(smiles)
        p_m = args.out_dir / f"edbo_suzuki_morgan_r{args.radius}_n{args.n_bits}.csv"
        # Keep human-readable meta beside fingerprints for visualization / joins.
        feat = _fp_frame(uniq["smiles"], "smiles", Xm, "morgan")
        extra = [c for c in meta_cols if c != "smiles"]
        out_m = pd.concat([uniq[extra].reset_index(drop=True), feat], axis=1)
        # smiles as first column
        cols = ["smiles"] + extra + [c for c in out_m.columns if c.startswith("morgan_")]
        out_m = out_m.loc[:, cols]
        out_m.to_csv(p_m, index=False)
        print(f"  wrote {p_m.name} shape={Xm.shape}  (d={Xm.shape[1]} = {args.n_bits} x n_parts)")

    if not args.skip_drfp:
        if "reaction_smiles" not in uniq.columns:
            print("WARNING: no reaction_smiles; skipping DRFP", file=sys.stderr)
        else:
            rxn = uniq["reaction_smiles"].astype(str).tolist()
            print("encoding drfp ...")
            drfp = build_representation("drfp", n_bits=args.n_bits)
            drfp.fit(rxn)
            Xd = drfp.transform(rxn)
            p_d = args.out_dir / f"edbo_suzuki_drfp_n{args.n_bits}.csv"
            feat = _fp_frame(uniq["reaction_smiles"], "reaction_smiles", Xd, "drfp")
            extra = [c for c in meta_cols if c != "reaction_smiles"]
            out_d = pd.concat([uniq[extra].reset_index(drop=True), feat], axis=1)
            cols = ["reaction_smiles"] + extra + [c for c in out_d.columns if c.startswith("drfp_")]
            out_d = out_d.loc[:, cols]
            out_d.to_csv(p_d, index=False)
            print(f"  wrote {p_d.name} shape={Xd.shape}")

    _update_manifest(args.out_dir)
    print(f"updated {args.out_dir / 'MANIFEST.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
