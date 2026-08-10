#!/usr/bin/env python
"""Train and freeze TransferGate from results/gate/train.csv.

Example:
  python scripts/train_gate.py --train results/gate/train.csv --out results/gate/freeze_W8
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from transferbo.gate.features import FEATURE_NAMES, features_to_vector  # noqa: E402
from transferbo.gate.model import train_mode_classifier  # noqa: E402
from transferbo.utils import ensure_dir  # noqa: E402


def leave_one_pair_cv(df: pd.DataFrame, feature_names: list[str], seed: int = 0) -> dict:
    """Hold out each (source,target) pair once (across representations)."""
    pairs = df[["source_plate", "target_plate"]].drop_duplicates().values.tolist()
    y_true, y_pred, folds = [], [], []
    for src, tgt in pairs:
        te = df[(df["source_plate"] == src) & (df["target_plate"] == tgt)]
        tr = df[~((df["source_plate"] == src) & (df["target_plate"] == tgt))]
        if tr.empty or te.empty:
            continue
        X_tr = np.vstack([features_to_vector(r, feature_names) for _, r in tr.iterrows()])
        y_tr = tr["y_mode"].astype(str).tolist()
        # Need ≥2 classes to fit logistic
        if len(set(y_tr)) < 2:
            continue
        model = train_mode_classifier(X_tr, y_tr, feature_names=feature_names, seed=seed)
        for _, r in te.iterrows():
            feat = {k: float(r[k]) for k in feature_names}
            pred = model.predict_mode(feat)
            y_true.append(str(r["y_mode"]))
            y_pred.append(pred)
            folds.append({"source": src, "target": tgt, "rep": r["representation"], "true": r["y_mode"], "pred": pred})
    report = {}
    if y_true:
        report["accuracy"] = float(accuracy_score(y_true, y_pred))
        report["classification_report"] = classification_report(y_true, y_pred, zero_division=0)
        labels = sorted(set(y_true) | set(y_pred))
        report["confusion_matrix"] = {
            "labels": labels,
            "matrix": confusion_matrix(y_true, y_pred, labels=labels).tolist(),
        }
    report["folds"] = folds
    return report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", type=Path, default=ROOT / "results/gate/train.csv")
    ap.add_argument("--out", type=Path, default=ROOT / "results/gate/freeze_W8")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--C", type=float, default=1.0)
    args = ap.parse_args()

    df = pd.read_csv(args.train)
    feature_names = [c for c in FEATURE_NAMES if c in df.columns]
    X = np.vstack([features_to_vector(r, feature_names) for _, r in df.iterrows()])
    y = df["y_mode"].astype(str).tolist()

    cv = leave_one_pair_cv(df, feature_names, seed=args.seed)
    model = train_mode_classifier(
        X,
        y,
        feature_names=feature_names,
        seed=args.seed,
        C=args.C,
        meta={
            "n_train": int(len(df)),
            "y_mode_counts": df["y_mode"].value_counts().to_dict(),
            "cv_accuracy": cv.get("accuracy"),
            "feature_names": feature_names,
            "note": "Frozen on dev plates only; do not retrain with plate_4 labels.",
        },
    )
    ensure_dir(args.out)
    model.save(args.out)
    (args.out / "cv_report.json").write_text(
        json.dumps({k: v for k, v in cv.items() if k != "classification_report"}, indent=2),
        encoding="utf-8",
    )
    if "classification_report" in cv:
        (args.out / "cv_classification_report.txt").write_text(
            cv["classification_report"], encoding="utf-8"
        )
    # also dump train table snapshot
    df.to_csv(args.out / "train_snapshot.csv", index=False)
    print(f"Frozen Gate -> {args.out}")
    print(f"n_train={len(df)} classes={model.classes_}")
    print(f"LOPO-CV accuracy={cv.get('accuracy')}")
    if "classification_report" in cv:
        print(cv["classification_report"])


if __name__ == "__main__":
    main()
