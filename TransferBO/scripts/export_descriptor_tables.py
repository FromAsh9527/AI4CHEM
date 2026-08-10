#!/usr/bin/env python
"""Export CHAOS descriptor tables to data/descriptors/ for archival / GitHub.

Writes:
  chaos_morgan_r2_n2048.csv      (unique additive SMILES)
  chaos_fragprint_r2_n2048.csv   (unique additive SMILES)
  chaos_ohe_smiles.csv           (unique additive SMILES, full-library vocab)
  chaos_ohe_vocab.csv            (smiles -> column index)
  chaos_drfp_n2048.csv           (per-row reaction_smiles; 2880 rows)
  chaos_xtb_gfn2.csv             (copy/refresh from BOUSE table if present)

Fingerprints stored as 0/1 ints. Re-run anytime; overwrites outputs.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from transferbo.representations import build_representation  # noqa: E402


def _fp_frame(keys: pd.Series, key_name: str, X: np.ndarray, prefix: str) -> pd.DataFrame:
    X = np.asarray(X)
    # binary-ish fingerprints → compact ints; continuous (xtb) keep float
    if np.allclose(X, np.round(X)) and X.min() >= 0 and X.max() <= 1:
        X_out = np.rint(X).astype(np.int8)
    else:
        X_out = X.astype(np.float64)
    cols = [f"{prefix}_{i}" for i in range(X_out.shape[1])]
    out = pd.DataFrame(X_out, columns=cols)
    out.insert(0, key_name, keys.astype(str).values)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--plates",
        type=Path,
        default=ROOT / "data" / "processed" / "additives_four_plates.csv",
    )
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "data" / "descriptors",
    )
    ap.add_argument("--n-bits", type=int, default=2048)
    ap.add_argument("--radius", type=int, default=2)
    ap.add_argument("--skip-drfp", action="store_true")
    ap.add_argument("--skip-xtb-copy", action="store_true")
    args = ap.parse_args()

    df = pd.read_csv(args.plates)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    # --- unique additive SMILES ---
    uniq = df.drop_duplicates(subset=["smiles"]).copy()
    smiles = uniq["smiles"].astype(str).tolist()
    print(f"unique additives: {len(smiles)}")

    # Morgan
    print("encoding morgan ...")
    morgan = build_representation("morgan", radius=args.radius, n_bits=args.n_bits)
    morgan.fit(smiles)
    Xm = morgan.transform(smiles)
    p_m = args.out_dir / f"chaos_morgan_r{args.radius}_n{args.n_bits}.csv"
    _fp_frame(uniq["smiles"], "smiles", Xm, "morgan").to_csv(p_m, index=False)
    print(f"  wrote {p_m.name} shape={Xm.shape}")

    # Fragprint
    print("encoding fragprint ...")
    frag = build_representation("fragprint", radius=args.radius, n_bits=args.n_bits)
    frag.fit(smiles)
    Xf = frag.transform(smiles)
    p_f = args.out_dir / f"chaos_fragprint_r{args.radius}_n{args.n_bits}.csv"
    _fp_frame(uniq["smiles"], "smiles", Xf, "frag").to_csv(p_f, index=False)
    print(f"  wrote {p_f.name} shape={Xf.shape}")

    # OHE over full unique-SMILES vocabulary (archival; runtime OHE may fit subset)
    print("encoding ohe (full-library vocab) ...")
    ohe = build_representation("ohe")
    ohe.fit(smiles)
    Xo = ohe.transform(smiles)
    vocab = pd.DataFrame(
        [{"smiles": s, "ohe_index": i} for s, i in sorted(ohe.vocab_.items(), key=lambda kv: kv[1])]
    )
    p_v = args.out_dir / "chaos_ohe_vocab.csv"
    p_o = args.out_dir / "chaos_ohe_smiles.csv"
    vocab.to_csv(p_v, index=False)
    _fp_frame(uniq["smiles"], "smiles", Xo, "ohe").to_csv(p_o, index=False)
    print(f"  wrote {p_o.name} shape={Xo.shape}; {p_v.name} n={len(vocab)}")

    # DRFP: per reaction row (plate-specific)
    if not args.skip_drfp:
        if "reaction_smiles" not in df.columns:
            print("WARNING: no reaction_smiles; skipping DRFP", file=sys.stderr)
        else:
            print(f"encoding drfp ({len(df)} reactions) ...")
            drfp = build_representation("drfp", n_bits=args.n_bits)
            rxn = df["reaction_smiles"].astype(str).tolist()
            drfp.fit(rxn)
            Xd = drfp.transform(rxn)
            meta = df[["plate_id", "additive_id", "smiles", "reaction_smiles"]].copy()
            cols = [f"drfp_{i}" for i in range(Xd.shape[1])]
            Xdi = np.rint(np.asarray(Xd)).astype(np.int8)
            out_d = pd.concat(
                [meta.reset_index(drop=True), pd.DataFrame(Xdi, columns=cols)],
                axis=1,
            )
            p_d = args.out_dir / f"chaos_drfp_n{args.n_bits}.csv"
            out_d.to_csv(p_d, index=False)
            print(f"  wrote {p_d.name} shape={Xd.shape}")

    # xTB: copy from processed cache if available
    if not args.skip_xtb_copy:
        src = ROOT / "data" / "processed" / "chaos_xtb_gfn2.csv"
        dst = args.out_dir / "chaos_xtb_gfn2.csv"
        if src.is_file():
            shutil.copy2(src, dst)
            print(f"  copied {src.name} -> {dst}")
        else:
            print(f"  skip xtb copy (missing {src})", file=sys.stderr)

    # manifest
    rows = []
    for p in sorted(args.out_dir.glob("chaos_*.csv")):
        rows.append(
            {
                "file": p.name,
                "bytes": p.stat().st_size,
                "mb": round(p.stat().st_size / 1e6, 3),
            }
        )
    man = pd.DataFrame(rows)
    man_path = args.out_dir / "MANIFEST.csv"
    man.to_csv(man_path, index=False)
    print("\nmanifest:")
    print(man.to_string(index=False))
    print(f"\ndone -> {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
