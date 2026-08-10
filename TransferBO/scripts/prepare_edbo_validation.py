#!/usr/bin/env python
"""Prepare EDBO (Shields Nature 2021) Suzuki + aryl_amination for TransferBO validation.

Same-library split (see docs/edbo_external_replication_design.md):
  - suzuki: task = (electrophile, nucleophile); X = ligand×base×solvent (308)
  - aryl_amination: task = aryl halide; X = additive×base×ligand (~260)

Substrates define plate_id only — never enter condition features.
Condition DFT tables exclude E/N or aryl halide.
Also writes reaction_smiles for DRFP: condition components as a pseudo-reaction
(no substrate), so Morgan / DRFP / DFT can all run under the CHAOS main protocol.

Outputs under data/processed/ and data/descriptors/.
"""

from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
EDBO = ROOT.parents[1] / "third_party" / "edbo-master" / "experiments" / "data"


def _cid(*parts: str) -> str:
    raw = "||".join(map(str, parts))
    return "C_" + hashlib.md5(raw.encode()).hexdigest()[:12]


def _condition_reaction_smiles(*components: str) -> str:
    """Pseudo reaction SMILES for DRFP over condition components only (no substrate).

    Use empty product side: identity A>>A yields an all-zero DRFP (no diff bits).
    """
    left = ".".join(str(c) for c in components)
    return f"{left}>>"


def _task_id(*parts: str, prefix: str) -> str:
    raw = "||".join(map(str, parts))
    return f"{prefix}_" + hashlib.md5(raw.encode()).hexdigest()[:8]


def _numeric_feats(df: pd.DataFrame, id_cols: list[str], prefix: str) -> pd.DataFrame:
    """Keep SMILES key + numeric DFT columns; prefix to avoid collisions."""
    smi_cols = [c for c in df.columns if c.lower().endswith("_smiles") or c.lower() == "smiles"]
    key = smi_cols[0]
    drop = set(id_cols) | set(smi_cols) | {c for c in df.columns if c.endswith("_file_name")}
    num = []
    for c in df.columns:
        if c in drop:
            continue
        if pd.api.types.is_numeric_dtype(df[c]):
            num.append(c)
    out = df[[key] + num].copy()
    out = out.rename(columns={key: "component_smiles"})
    # drop all-nan / constant
    keep = []
    for c in num:
        v = out[c]
        if v.notna().sum() == 0:
            continue
        if v.nunique(dropna=True) <= 1:
            continue
        keep.append(c)
    out = out[["component_smiles"] + keep]
    rename = {c: f"{prefix}__{c}" for c in keep}
    return out.rename(columns=rename)


def _join_condition_dft(
    components: dict[str, pd.DataFrame],
    keys: dict[str, str],
) -> pd.Series:
    """components: name -> feat table with component_smiles; keys: name -> smiles value."""
    vecs = []
    colnames = []
    for name, smi in keys.items():
        tab = components[name]
        row = tab[tab["component_smiles"].astype(str) == str(smi)]
        if row.empty:
            raise KeyError(f"DFT miss {name}: {smi[:60]}")
        feats = row.drop(columns=["component_smiles"]).iloc[0]
        vecs.append(feats.to_numpy(dtype=np.float64))
        colnames.extend(feats.index.tolist())
    return pd.Series(np.concatenate(vecs), index=colnames)


def prepare_suzuki(edbo: Path, out_plates: Path, out_dft: Path) -> pd.DataFrame:
    idx = pd.read_csv(edbo / "suzuki" / "experiment_index.csv")
    lig = _numeric_feats(
        pd.read_csv(edbo / "suzuki" / "ligand-boltzmann_dft.csv"),
        ["ligand_file_name"],
        "lig",
    )
    base = _numeric_feats(
        pd.read_csv(edbo / "suzuki" / "base_dft.csv"), ["base_file_name"], "base"
    )
    sol = _numeric_feats(
        pd.read_csv(edbo / "suzuki" / "solvent_dft.csv"), ["solvent_file_name"], "sol"
    )
    comps = {"lig": lig, "base": base, "sol": sol}

    # unique conditions
    conds = idx[["Ligand_SMILES", "Base_SMILES", "Solvent_SMILES"]].drop_duplicates()
    dft_rows = []
    for _, r in conds.iterrows():
        key = f"{r.Ligand_SMILES}||{r.Base_SMILES}||{r.Solvent_SMILES}"
        ser = _join_condition_dft(
            comps,
            {"lig": r.Ligand_SMILES, "base": r.Base_SMILES, "sol": r.Solvent_SMILES},
        )
        dft_rows.append({"smiles": key, **ser.to_dict()})
    dft = pd.DataFrame(dft_rows)
    # sanitize column names for CSV
    dft.columns = [re.sub(r"[^0-9a-zA-Z_]+", "_", c) for c in dft.columns]
    out_dft.parent.mkdir(parents=True, exist_ok=True)
    dft.to_csv(out_dft, index=False)

    # plates
    rows = []
    for _, r in idx.iterrows():
        key = f"{r.Ligand_SMILES}||{r.Base_SMILES}||{r.Solvent_SMILES}"
        plate = _task_id(r.Electrophile_SMILES, r.Nucleophile_SMILES, prefix="suz")
        rows.append(
            {
                "plate_id": plate,
                "smiles": key,
                "reaction_smiles": _condition_reaction_smiles(
                    r.Ligand_SMILES, r.Base_SMILES, r.Solvent_SMILES
                ),
                "response": float(r["yield"]),
                "additive_id": _cid(r.Ligand_SMILES, r.Base_SMILES, r.Solvent_SMILES),
                "candidate_key": key,
                "ligand_smiles": r.Ligand_SMILES,
                "base_smiles": r.Base_SMILES,
                "solvent_smiles": r.Solvent_SMILES,
                "electrophile_smiles": r.Electrophile_SMILES,
                "nucleophile_smiles": r.Nucleophile_SMILES,
                "source_dataset": "edbo_suzuki",
            }
        )
    plates = pd.DataFrame(rows)
    # short readable plate map
    tasks = (
        plates[["plate_id", "electrophile_smiles", "nucleophile_smiles"]]
        .drop_duplicates()
        .reset_index(drop=True)
    )
    tasks["plate_label"] = [f"suz_t{i+1}" for i in range(len(tasks))]
    labmap = dict(zip(tasks.plate_id, tasks.plate_label))
    plates["plate_id"] = plates["plate_id"].map(labmap)
    tasks.to_csv(out_plates.with_name("edbo_suzuki_task_map.csv"), index=False)

    out_plates.parent.mkdir(parents=True, exist_ok=True)
    plates.to_csv(out_plates, index=False)
    print(
        f"suzuki: plates={plates.plate_id.nunique()} conds={plates.smiles.nunique()} "
        f"rows={len(plates)} dft_dim={dft.shape[1]-1} -> {out_plates.name}"
    )
    return plates


def prepare_amination(edbo: Path, out_plates: Path, out_dft: Path) -> pd.DataFrame:
    idx = pd.read_csv(edbo / "aryl_amination" / "experiment_index.csv")
    add = _numeric_feats(
        pd.read_csv(edbo / "aryl_amination" / "additive_dft.csv"),
        ["additive_file_name"],
        "add",
    )
    base = _numeric_feats(
        pd.read_csv(edbo / "aryl_amination" / "base_dft.csv"),
        ["base_file_name"],
        "base",
    )
    lig = _numeric_feats(
        pd.read_csv(edbo / "aryl_amination" / "ligand-Pd(0)_dft.csv"),
        ["ligand_file_name"],
        "lig",
    )
    comps = {"add": add, "base": base, "lig": lig}

    conds = idx[["Additive_SMILES", "Base_SMILES", "Ligand_SMILES"]].drop_duplicates()
    dft_rows = []
    for _, r in conds.iterrows():
        key = f"{r.Ligand_SMILES}||{r.Base_SMILES}||{r.Additive_SMILES}"
        ser = _join_condition_dft(
            comps,
            {"lig": r.Ligand_SMILES, "base": r.Base_SMILES, "add": r.Additive_SMILES},
        )
        dft_rows.append({"smiles": key, **ser.to_dict()})
    dft = pd.DataFrame(dft_rows)
    dft.columns = [re.sub(r"[^0-9a-zA-Z_]+", "_", c) for c in dft.columns]
    out_dft.parent.mkdir(parents=True, exist_ok=True)
    dft.to_csv(out_dft, index=False)

    # map aryl halide -> sub_s* if matches existing Doyle table
    doyle_path = ROOT / "data" / "processed" / "doyle_cn_plates.csv"
    smi2plate: dict[str, str] = {}
    if doyle_path.is_file():
        d = pd.read_csv(doyle_path)
        smi2plate = (
            d.groupby("substrate_smiles")["plate_id"].first().astype(str).to_dict()
        )

    rows = []
    for _, r in idx.iterrows():
        key = f"{r.Ligand_SMILES}||{r.Base_SMILES}||{r.Additive_SMILES}"
        aryl = str(r.Aryl_halide_SMILES)
        plate = smi2plate.get(aryl) or _task_id(aryl, prefix="am")
        rows.append(
            {
                "plate_id": plate,
                "smiles": key,
                "reaction_smiles": _condition_reaction_smiles(
                    r.Ligand_SMILES, r.Base_SMILES, r.Additive_SMILES
                ),
                "response": float(r["yield"]),
                "additive_id": _cid(r.Ligand_SMILES, r.Base_SMILES, r.Additive_SMILES),
                "candidate_key": key,
                "ligand_smiles": r.Ligand_SMILES,
                "base_smiles": r.Base_SMILES,
                "additive_smiles": r.Additive_SMILES,
                "substrate_smiles": aryl,
                "source_dataset": "edbo_aryl_amination",
            }
        )
    plates = pd.DataFrame(rows)
    # drop incomplete plates (missing cells) if any plate has fewer conds
    n_full = plates.groupby("plate_id")["smiles"].nunique().max()
    keep = (
        plates.groupby("plate_id")["smiles"].nunique() >= n_full - 2
    )  # allow tiny holes
    plates = plates[plates.plate_id.isin(keep[keep].index)].copy()
    # for remaining holes: drop conditions not present on all kept plates
    sets = [set(g.smiles) for _, g in plates.groupby("plate_id")]
    inter = set.intersection(*sets)
    plates = plates[plates.smiles.isin(inter)].copy()

    out_plates.parent.mkdir(parents=True, exist_ok=True)
    plates.to_csv(out_plates, index=False)
    print(
        f"amination: plates={plates.plate_id.nunique()} conds={plates.smiles.nunique()} "
        f"rows={len(plates)} dft_dim={dft.shape[1]-1} -> {out_plates.name}"
    )
    return plates


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--edbo", type=Path, default=EDBO)
    args = ap.parse_args()
    if not args.edbo.is_dir():
        raise SystemExit(f"EDBO data not found: {args.edbo}")

    prepare_suzuki(
        args.edbo,
        ROOT / "data/processed/edbo_suzuki_plates.csv",
        ROOT / "data/descriptors/edbo_suzuki_condition_dft.csv",
    )
    prepare_amination(
        args.edbo,
        ROOT / "data/processed/edbo_amination_plates.csv",
        ROOT / "data/descriptors/edbo_amination_condition_dft.csv",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
