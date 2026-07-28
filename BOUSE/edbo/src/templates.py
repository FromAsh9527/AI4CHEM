# -*- coding: utf-8 -*-
"""反应类型模板：预填因子，用户可改。"""
from __future__ import annotations

from factors import FactorSpec

TEMPLATES: dict[str, dict] = {
    "condition_optimization": {
        "label": "条件优化",
        "description": "溶剂 / 碱 / 温度 / 当量 / 浓度 —— 典型反应条件筛选",
        "target_column": "yield",
        "batch_size": 5,
        "factors": [
            FactorSpec(key="solvent", kind="chemical", encoding="descriptor"),
            FactorSpec(key="base", kind="chemical", encoding="descriptor"),
            FactorSpec(
                key="temperature",
                kind="numeric",
                numeric_mode="list",
                values=[-40.0, -30.0, -20.0, -10.0, 0.0, 10.0, 25.0, 35.0],
            ),
            FactorSpec(
                key="base_eq",
                kind="numeric",
                numeric_mode="list",
                values=[0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0],
            ),
            FactorSpec(
                key="concentration",
                kind="numeric",
                numeric_mode="list",
                values=[0.15, 0.3, 0.6, 1.2],
            ),
        ],
    },
    "blank": {
        "label": "空白项目",
        "description": "从零添加因子",
        "target_column": "yield",
        "batch_size": 5,
        "factors": [],
    },
}


def template_choices() -> list[tuple[str, str]]:
    return [(k, v["label"]) for k, v in TEMPLATES.items()]


def apply_template(template_id: str) -> dict:
    if template_id not in TEMPLATES:
        raise KeyError(f"未知模板: {template_id}")
    t = TEMPLATES[template_id]
    return {
        "template": template_id,
        "target_column": t["target_column"],
        "batch_size": t["batch_size"],
        "acquisition_function": "EI",
        "factors": [f.to_dict() for f in t["factors"]],
    }
