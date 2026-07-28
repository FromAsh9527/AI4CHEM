# -*- coding: utf-8 -*-
"""因子与编码规格（MVP：描述符表 / 独热 / 数值网格）。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np

FactorKind = Literal["chemical", "numeric"]
ChemEncoding = Literal["descriptor", "ohe"]
NumericMode = Literal["list", "linspace", "arange"]


@dataclass
class FactorSpec:
    key: str
    kind: FactorKind
    # chemical
    encoding: ChemEncoding = "descriptor"
    id_column: str = "molecule_id"
    levels: list[str] = field(default_factory=list)  # ohe 时可写在 config
    # numeric
    numeric_mode: NumericMode = "list"
    values: list[float] = field(default_factory=list)
    linspace_min: float | None = None
    linspace_max: float | None = None
    linspace_n: int = 5
    arange_min: float | None = None
    arange_max: float | None = None
    arange_step: float | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "key": self.key,
            "kind": self.kind,
            "encoding": self.encoding,
            "id_column": self.id_column,
            "levels": self.levels,
            "numeric_mode": self.numeric_mode,
            "values": self.values,
            "linspace_min": self.linspace_min,
            "linspace_max": self.linspace_max,
            "linspace_n": self.linspace_n,
            "arange_min": self.arange_min,
            "arange_max": self.arange_max,
            "arange_step": self.arange_step,
        }
        return d

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "FactorSpec":
        return FactorSpec(
            key=str(d["key"]),
            kind=d.get("kind", "chemical"),
            encoding=d.get("encoding", "descriptor"),
            id_column=d.get("id_column", "molecule_id"),
            levels=[str(x) for x in d.get("levels", [])],
            numeric_mode=d.get("numeric_mode", "list"),
            values=[float(x) for x in d.get("values", [])],
            linspace_min=d.get("linspace_min"),
            linspace_max=d.get("linspace_max"),
            linspace_n=int(d.get("linspace_n", 5)),
            arange_min=d.get("arange_min"),
            arange_max=d.get("arange_max"),
            arange_step=d.get("arange_step"),
        )

    def numeric_levels(self) -> list[float]:
        if self.kind != "numeric":
            return []
        if self.numeric_mode == "list":
            return [float(v) for v in self.values]
        if self.numeric_mode == "linspace":
            if self.linspace_min is None or self.linspace_max is None:
                raise ValueError(f"因子 {self.key}: linspace 需要 min/max")
            n = max(2, int(self.linspace_n))
            return [float(x) for x in np.linspace(self.linspace_min, self.linspace_max, n)]
        if self.numeric_mode == "arange":
            if None in (self.arange_min, self.arange_max, self.arange_step):
                raise ValueError(f"因子 {self.key}: arange 需要 min/max/step")
            step = float(self.arange_step)
            if step == 0:
                raise ValueError(f"因子 {self.key}: arange step 不能为 0")
            xs = np.arange(float(self.arange_min), float(self.arange_max) + step * 0.5, step)
            return [float(x) for x in xs]
        raise ValueError(f"未知 numeric_mode: {self.numeric_mode}")


def factor_keys(factors: list[FactorSpec]) -> list[str]:
    return [f.key for f in factors]
