"""Descriptor generators package."""

GENERATORS = {
    "rdkit_2d": "SMILES → RDKit 2D 描述符",
    "morgan": "SMILES → Morgan / ECFP 指纹",
    "maccs": "SMILES → MACCS keys（RDKit）",
    "mordred": "SMILES → Mordred（需额外安装 mordred）",
    "clean": "已有描述符表清洗（DFT/Excel）",
}
