"""Tests for TransferGate features / policy (no target y leakage)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from transferbo.gate.features import (
    FEATURE_NAMES,
    GateFeatureInputs,
    compute_gate_features,
)
from transferbo.gate.model import train_mode_classifier
from transferbo.gate.policy import decide_from_prediction
from transferbo.gate.train import build_label_table


def test_features_reject_target_y():
    rng = np.random.default_rng(0)
    X_s = rng.random((30, 16))
    X_t = rng.random((25, 16))
    y_s = rng.random(30)
    with pytest.raises(ValueError, match="must not receive target"):
        compute_gate_features(
            GateFeatureInputs(
                X_source=X_s,
                y_source=y_s,
                X_target=X_t,
                representation="morgan",
            ),
            y_target=rng.random(25),
        )


def test_features_keys_and_finite():
    rng = np.random.default_rng(1)
    X_s = (rng.random((40, 32)) > 0.7).astype(float)
    X_t = (rng.random((35, 32)) > 0.7).astype(float)
    y_s = rng.random(40)
    feat = compute_gate_features(
        GateFeatureInputs(
            X_source=X_s,
            y_source=y_s,
            X_target=X_t,
            representation="morgan",
            source_fraction=0.5,
            seed=1,
        )
    )
    assert list(feat.keys()) == FEATURE_NAMES
    assert all(np.isfinite(v) for v in feat.values())
    assert feat["rep_morgan"] == 1.0
    assert feat["src_frac"] == 0.5


def test_policy_off_and_diversity_guard():
    d = decide_from_prediction(
        mode="diversity_warm",
        probs={"diversity_warm": 0.3, "label_warm": 0.4, "off": 0.3},
        source_fraction=1.0,
    )
    # argmax is label_warm
    assert d.strategy == "label_warm"
    d_div = decide_from_prediction(
        mode="diversity_warm",
        probs={"diversity_warm": 0.7, "label_warm": 0.2, "off": 0.1},
        source_fraction=1.0,
    )
    assert d_div.strategy == "diversity_warm"
    d2 = decide_from_prediction(
        mode="label_warm",
        probs={"label_warm": 0.8, "off": 0.1, "diversity_warm": 0.1},
        source_fraction=0.5,
    )
    assert d2.strategy == "label_warm"
    assert d2.strength == 0.5


def test_train_tiny_classifier():
    rng = np.random.default_rng(2)
    X = rng.normal(size=(12, len(FEATURE_NAMES)))
    y = ["off", "label_warm", "multitask", "label_warm"] * 3
    model = train_mode_classifier(X, y, feature_names=FEATURE_NAMES, seed=0)
    feat = {n: float(X[0, i]) for i, n in enumerate(FEATURE_NAMES)}
    mode = model.predict_mode(feat)
    assert mode in model.classes_


def test_build_label_table_excludes_heldout():
    rows = []
    for seed in range(3):
        for strat in ["cold_start", "label_warm", "diversity_warm", "multitask"]:
            for tgt in ["plate_1", "plate_2", "plate_4"]:
                src = "plate_3" if strat != "cold_start" else tgt
                rows.append(
                    {
                        "source_plate": src,
                        "target_plate": tgt,
                        "strategy": strat,
                        "representation": "morgan",
                        "seed": seed,
                        "frac_of_opt": 0.5
                        + (0.2 if strat == "label_warm" else 0.0)
                        - (0.15 if strat == "diversity_warm" else 0.0),
                        "queries_to_top5": 40.0,
                    }
                )
    grid = pd.DataFrame(rows)
    lab = build_label_table(grid, exclude_targets=["plate_4"])
    assert set(lab["target_plate"]) == {"plate_1", "plate_2"}
    assert (lab["y_mode"] == "label_warm").all()
