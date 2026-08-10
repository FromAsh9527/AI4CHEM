"""Molecular / reaction representations: OHE, Morgan, fragprint, DRFP, xTB table."""

from __future__ import annotations

from typing import Sequence

import numpy as np

from .ohe import OneHotEncoder
from .morgan import MorganFingerprint
from .fragprint import FragprintEncoder
from .base import Representation
from .xtb_table import XTBTableEncoder


def build_representation(name: str, **kwargs) -> Representation:
    name = name.lower().strip()
    if name in ("ohe", "onehot", "one-hot"):
        return OneHotEncoder(**kwargs)
    if name in ("morgan", "ecfp"):
        return MorganFingerprint(**kwargs)
    if name in ("fragprint", "fragprints"):
        return FragprintEncoder(**kwargs)
    if name == "drfp":
        from .drfp_rep import DRFPEncoder

        return DRFPEncoder(**kwargs)
    if name in ("xtb", "xtb_table", "gfn2", "dft", "dft_table", "feature_table"):
        return XTBTableEncoder(**kwargs)
    raise ValueError(f"Unknown representation: {name!r}")


def encode_smiles(rep: Representation, smiles: Sequence[str]) -> np.ndarray:
    return rep.transform(list(smiles))


__all__ = [
    "Representation",
    "OneHotEncoder",
    "MorganFingerprint",
    "FragprintEncoder",
    "XTBTableEncoder",
    "build_representation",
    "encode_smiles",
]
