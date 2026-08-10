#!/usr/bin/env python
"""PCA-reduce EDBO Suzuki Morgan / DRFP descriptor CSVs.

Fits PCA on the unique condition library only (no yield labels).
Writes companion *_pca{N}.csv tables plus a small JSON summary.
Does not touch experiment configs or running grids.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA

ROOT = Path(__file__).resolve().parents[1]


def _update_manifest(out_dir: Path) -> None:
    rows = []
    for p in sorted(out_dir.glob("*.csv")):
        if p.name == "MANIFEST.csv":
            continue
        n = p.stat().st_size
        rows.append({"file": p.name, "bytes": n, "mb": round(n / 1e6, 3)})
    pd.DataFrame(rows).to_csv(out_dir / "MANIFEST.csv", index=False)


def reduce_table(
    path: Path,
    *,
    feat_prefix: str,
    n_components: int,
    random_state: int = 0,
) -> tuple[pd.DataFrame, dict]:
    df = pd.read_csv(path)
    feat_cols = [c for c in df.columns if c.startswith(f"{feat_prefix}_")]
    if not feat_cols:
        raise ValueError(f"No columns with prefix {feat_prefix!r} in {path.name}")
    meta_cols = [c for c in df.columns if c not in feat_cols]
    X = df[feat_cols].to_numpy(dtype=np.float64)
    keep = X.std(axis=0) > 0
    Xk = X[:, keep]
    n_comp = min(n_components, Xk.shape[0] - 1, Xk.shape[1])
    pca = PCA(n_components=n_comp, random_state=random_state)
    Z = pca.fit_transform(Xk)
    zcols = [f"{feat_prefix}_pca{n_components}_{i}" for i in range(Z.shape[1])]
    out = pd.concat(
        [df[meta_cols].reset_index(drop=True), pd.DataFrame(Z, columns=zcols)],
        axis=1,
    )
    cums = np.cumsum(pca.explained_variance_ratio_)

    def n_for(thr: float) -> int:
        idx = int(np.searchsorted(cums, thr))
        return idx + 1 if idx < len(cums) else len(cums)

    info = {
        "source": path.name,
        "n_rows": int(X.shape[0]),
        "n_feat_raw": int(X.shape[1]),
        "n_feat_nonzero_var": int(keep.sum()),
        "n_components": int(Z.shape[1]),
        "variance_explained": round(float(pca.explained_variance_ratio_.sum()), 6),
        "n_comp_for_90pct": n_for(0.90),
        "n_comp_for_95pct": n_for(0.95),
        "n_comp_for_99pct": n_for(0.99),
        "pc1_var": round(float(pca.explained_variance_ratio_[0]), 6),
    }
    return out, info


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "data" / "descriptors",
    )
    ap.add_argument("--n-components", type=int, default=128)
    ap.add_argument("--random-state", type=int, default=0)
    args = ap.parse_args()

    jobs = [
        (f"edbo_suzuki_morgan_r2_n2048.csv", "morgan"),
        (f"edbo_suzuki_drfp_n2048.csv", "drfp"),
    ]
    infos = []
    for fname, prefix in jobs:
        src = args.out_dir / fname
        if not src.is_file():
            raise FileNotFoundError(
                f"Missing {src}. Run scripts/export_edbo_descriptor_tables.py first."
            )
        print(f"PCA {args.n_components} on {src.name} ...")
        out_df, info = reduce_table(
            src,
            feat_prefix=prefix,
            n_components=args.n_components,
            random_state=args.random_state,
        )
        out_path = args.out_dir / f"{src.stem}_pca{args.n_components}.csv"
        out_df.to_csv(out_path, index=False)
        info["output"] = out_path.name
        infos.append(info)
        print(
            f"  wrote {out_path.name}  shape={out_df.shape}  "
            f"var={info['variance_explained']:.4f}  "
            f"(90%/95%/99% need {info['n_comp_for_90pct']}/"
            f"{info['n_comp_for_95pct']}/{info['n_comp_for_99pct']} PCs)"
        )

    summary = args.out_dir / f"edbo_suzuki_pca{args.n_components}_summary.json"
    summary.write_text(json.dumps(infos, indent=2), encoding="utf-8")
    print(f"wrote {summary.name}")
    _update_manifest(args.out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
