"""Deeper fitness scoring for TransferBO2.0 dual-shift needs."""
from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(r"F:\BaiduSyncdisk\zhangzhou\ed\AI-Pharmacy\AI4CHEM\TransferBO\data")

def dens(df, sub_cols, resp="response"):
    if isinstance(sub_cols, str):
        sub_cols = [sub_cols]
    g = df.groupby(sub_cols).size()
    print(f"  #tasks={len(g)}  median_n={g.median():.0f}  min={g.min()} max={g.max()} mean={g.mean():.1f}")
    return g

print("\n## CHAOS additives")
df = pd.read_csv(ROOT/"processed/additives_four_plates.csv")
print(df.groupby("plate_id").size())
print("unique additives", df["smiles"].nunique())

print("\n## EDBO Suzuki")
df = pd.read_csv(ROOT/"processed/edbo_suzuki_plates.csv")
df["pair"] = df["electrophile_smiles"] + "||" + df["nucleophile_smiles"]
print("plates", df["plate_id"].nunique(), "pairs", df["pair"].nunique())
print(df.groupby("plate_id")["pair"].nunique().describe())
dens(df, "pair")
dens(df, "plate_id")
# how many conditions per pair on a plate
print(df.groupby(["plate_id","pair"]).size().describe())

print("\n## EDBO Amination")
df = pd.read_csv(ROOT/"processed/edbo_amination_plates.csv")
print("plates/tasks", df["plate_id"].nunique(), "substrates", df["substrate_smiles"].nunique())
dens(df, "substrate_smiles")
print(df.groupby(["plate_id","substrate_smiles"]).size().describe())

print("\n## Doyle CN (Ahneman-like)")
df = pd.read_csv(ROOT/"processed/doyle_cn_plates.csv")
print("tasks", df["plate_id"].nunique(), "substrates", df["substrate_smiles"].nunique(), "additives", df["additive_smiles"].nunique())
dens(df, "substrate_smiles")
# condition factors
print("ligands", df["ligand_smiles"].nunique(), "bases", df["base_smiles"].nunique())

print("\n## SURF SM")
df = pd.read_csv(ROOT/"raw/surf/sm_all.csv")
df["pair"] = df["startingmat_1_smiles"].astype(str) + "||" + df["startingmat_2_smiles"].astype(str)
print("dates", df["rxn_date"].nunique(), "examples", sorted(df["rxn_date"].dropna().astype(str).unique())[:8])
dens(df, "pair")
print("catalysts", df["catalyst_name"].nunique(), "bases", df["reagent_1_name"].nunique(), "solvents", df["solvent_1_name"].nunique())
print("temp unique", sorted(df["temperature_deg_c"].dropna().unique())[:10])

print("\n## SURF BH")
df = pd.read_csv(ROOT/"raw/surf/bh_all.csv")
df["pair"] = df["startingmat_1_smiles"].astype(str) + "||" + df["startingmat_2_smiles"].astype(str)
print("dates", df["rxn_date"].nunique())
dens(df, "pair")
print("catalysts", df["catalyst_name"].nunique(), "bases", df["reagent_1_name"].nunique(), "solvents", df["solvent_1_name"].nunique())
# date as batch proxy: shared pairs across dates?
ct = df.groupby(["pair","rxn_date"]).size().reset_index(name="n")
multi = ct.groupby("pair")["rxn_date"].nunique()
print("pairs spanning >1 date:", int((multi>1).sum()), "/", len(multi))

print("\n## aryl-scope-ligand")
df = pd.read_csv(ROOT/"raw/external/aryl-scope-ligand.csv")
df["pair"] = df["electrophile_smiles"] + "||" + df["nucleophile_smiles"]
dens(df, "pair")
print("ligands", df["ligand_name"].nunique())

print("\n## BH curated Source (chunked)")
path = ROOT/"raw/external/BH_HTE_Curated_Dataset_v20260219.csv"
# read only needed cols if possible
try:
    df = pd.read_csv(path, usecols=["Source","Aryl SMILES","Amine SMILES","Yield"], on_bad_lines="skip")
    print("rows", len(df))
    print(df["Source"].value_counts().head(20))
    df["pair"] = df["Aryl SMILES"].astype(str) + "||" + df["Amine SMILES"].astype(str)
    dens(df, "pair")
    dens(df, "Source")
except Exception as e:
    print("BH curated failed", e)
