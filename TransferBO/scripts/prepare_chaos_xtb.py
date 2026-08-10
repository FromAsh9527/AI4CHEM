#!/usr/bin/env python
"""Compute BOUSE xTB descriptors for CHAOS 720 additives → data/processed/chaos_xtb_gfn2.csv

Uses AI4CHEM/BOUSE descriptors pipeline + third_party xtb.exe.
Resume-friendly: skips SMILES already present in the output table.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
BOUSE_DESC = ROOT.parents[0] / "BOUSE" / "descriptors"
DEFAULT_OUT = ROOT / "data" / "processed" / "chaos_xtb_gfn2.csv"
DEFAULT_FAILED = ROOT / "data" / "processed" / "chaos_xtb_gfn2_failed.csv"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--plates",
        type=Path,
        default=ROOT / "data" / "processed" / "additives_four_plates.csv",
    )
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--failed", type=Path, default=DEFAULT_FAILED)
    ap.add_argument("--gfn", type=int, default=2, choices=[0, 1, 2])
    ap.add_argument("--opt", action="store_true", help="GFN geometry opt (much slower)")
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--xtb", type=str, default=None)
    ap.add_argument("--limit", type=int, default=0, help="debug: only first N smiles")
    args = ap.parse_args()

    if not BOUSE_DESC.is_dir():
        print(f"BOUSE descriptors not found: {BOUSE_DESC}", file=sys.stderr)
        return 1
    sys.path.insert(0, str(BOUSE_DESC))
    from generators.xtb.core import compute, find_xtb  # noqa: E402

    exe = find_xtb(args.xtb)
    print(f"xtb exe: {exe}")

    plates = pd.read_csv(args.plates)
    smiles = plates["smiles"].astype(str).drop_duplicates().tolist()
    if args.limit and args.limit > 0:
        smiles = smiles[: args.limit]

    done: set[str] = set()
    if args.out.is_file():
        prev = pd.read_csv(args.out)
        if "smiles" in prev.columns:
            done = set(prev["smiles"].astype(str))
            print(f"resume: {len(done)} already in {args.out.name}")

    todo = [s for s in smiles if s not in done]
    print(f"unique smiles={len(smiles)}; todo={len(todo)}; opt={args.opt}")
    if not todo:
        print("nothing to do")
        return 0

    mols = pd.DataFrame(
        {"molecule_id": [f"add_{i}" for i in range(len(todo))], "smiles": todo}
    )
    desc, failed = compute(
        mols, xtb=exe, gfn=args.gfn, opt=bool(args.opt), timeout=args.timeout
    )

    # attach smiles back
    if not desc.empty:
        id2smi = dict(zip(mols["molecule_id"], mols["smiles"]))
        desc["smiles"] = desc["molecule_id"].map(id2smi)
        cols = ["smiles"] + [c for c in desc.columns if c.startswith("xtb_")]
        desc = desc[cols]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    if args.out.is_file() and not desc.empty:
        old = pd.read_csv(args.out)
        merged = pd.concat([old, desc], ignore_index=True)
        merged = merged.drop_duplicates(subset=["smiles"], keep="last")
        merged.to_csv(args.out, index=False)
        print(f"wrote {args.out} n={len(merged)}")
    elif not desc.empty:
        desc.to_csv(args.out, index=False)
        print(f"wrote {args.out} n={len(desc)}")

    if failed is not None and len(failed):
        if "smiles" not in failed.columns and "molecule_id" in failed.columns:
            id2smi = dict(zip(mols["molecule_id"], mols["smiles"]))
            failed = failed.copy()
            failed["smiles"] = failed["molecule_id"].map(id2smi)
        if args.failed.is_file():
            oldf = pd.read_csv(args.failed)
            failed = pd.concat([oldf, failed], ignore_index=True).drop_duplicates(
                subset=["smiles"], keep="last"
            )
        failed.to_csv(args.failed, index=False)
        print(f"failed {len(failed)} → {args.failed}")

    # coverage report
    if args.out.is_file():
        have = set(pd.read_csv(args.out)["smiles"].astype(str))
        cov = len(have & set(smiles)) / max(len(smiles), 1)
        print(f"coverage vs CHAOS unique: {cov:.1%} ({len(have & set(smiles))}/{len(smiles)})")
        if cov < 0.95:
            print("WARNING: coverage < 95%; inspect failed list before BO grid", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
