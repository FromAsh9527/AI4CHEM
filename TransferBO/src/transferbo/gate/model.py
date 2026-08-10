"""Trainable TransferGate mode classifier."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from transferbo.gate.features import FEATURE_NAMES, features_to_vector
from transferbo.gate.policy import GateDecision, decide_from_prediction


@dataclass
class GateModel:
    feature_names: list[str]
    classes_: list[str]
    pipeline: Any
    meta: dict

    def predict_proba_dict(self, feat: Mapping[str, float]) -> dict[str, float]:
        x = features_to_vector(feat, self.feature_names).reshape(1, -1)
        proba = self.pipeline.predict_proba(x)[0]
        return {str(c): float(p) for c, p in zip(self.classes_, proba)}

    def predict_mode(self, feat: Mapping[str, float]) -> str:
        x = features_to_vector(feat, self.feature_names).reshape(1, -1)
        return str(self.pipeline.predict(x)[0])

    def decide(
        self,
        feat: Mapping[str, float],
        *,
        source_fraction: float = 1.0,
        neg_threshold: float = 0.45,
    ) -> GateDecision:
        mode = self.predict_mode(feat)
        probs = self.predict_proba_dict(feat)
        return decide_from_prediction(
            mode=mode,
            probs=probs,
            source_fraction=source_fraction,
            neg_threshold=neg_threshold,
        )

    def save(self, out_dir: str | Path) -> Path:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "feature_names": self.feature_names,
                "classes_": self.classes_,
                "pipeline": self.pipeline,
                "meta": self.meta,
            },
            out / "model.joblib",
        )
        (out / "feature_names.json").write_text(
            json.dumps(self.feature_names, indent=2), encoding="utf-8"
        )
        (out / "meta.json").write_text(
            json.dumps(self.meta, indent=2), encoding="utf-8"
        )
        return out


def load_gate_model(path: str | Path) -> GateModel:
    path = Path(path)
    blob_path = path / "model.joblib" if path.is_dir() else path
    blob = joblib.load(blob_path)
    return GateModel(
        feature_names=list(blob["feature_names"]),
        classes_=list(blob["classes_"]),
        pipeline=blob["pipeline"],
        meta=dict(blob.get("meta") or {}),
    )


def train_mode_classifier(
    X: np.ndarray,
    y: Sequence[str],
    *,
    feature_names: Optional[Sequence[str]] = None,
    seed: int = 0,
    C: float = 1.0,
    meta: Optional[dict] = None,
) -> GateModel:
    feature_names = list(feature_names) if feature_names is not None else list(FEATURE_NAMES)
    y = [str(v) for v in y]
    pipe = Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            (
                "clf",
                LogisticRegression(
                    max_iter=2000,
                    C=C,
                    random_state=seed,
                ),
            ),
        ]
    )
    pipe.fit(X, y)
    classes = [str(c) for c in pipe.named_steps["clf"].classes_]
    return GateModel(
        feature_names=feature_names,
        classes_=classes,
        pipeline=pipe,
        meta=meta or {},
    )
