"""SURF BH/SM: date-as-batch overlap for plate-aware fitness."""
from pathlib import Path
import pandas as pd

ROOT = Path(r"F:\BaiduSyncdisk\zhangzhou\ed\AI-Pharmacy\AI4CHEM\TransferBO\data\raw\surf")

for name in ["bh_all.csv", "sm_all.csv"]:
    df = pd.read_csv(ROOT / name)
    df["pair"] = df["startingmat_1_smiles"].astype(str) + "||" + df["startingmat_2_smiles"].astype(str)
    print("\n####", name)
    # shared conditions across dates: catalyst+base+solvent+temps
    df["cond"] = (
        df["catalyst_name"].astype(str) + "|" +
        df["reagent_1_name"].astype(str) + "|" +
        df["solvent_1_name"].astype(str) + "|" +
        df["temperature_deg_c"].astype(str)
    )
    multi_date_pairs = df.groupby("pair")["rxn_date"].nunique()
    print("pairs with >=2 dates:", int((multi_date_pairs >= 2).sum()))
    # for those pairs, shared cond across dates?
    overlap_rows = 0
    bridge_pairs = 0
    for pair, g in df.groupby("pair"):
        dates = g["rxn_date"].nunique()
        if dates < 2:
            continue
        # conditions appearing on >1 date
        c = g.groupby("cond")["rxn_date"].nunique()
        shared = int((c >= 2).sum())
        if shared > 0:
            bridge_pairs += 1
            overlap_rows += int(shared)
    print("pairs with shared cond across dates (anchor-like):", bridge_pairs)
    print("n shared cond definitions:", overlap_rows)
    print("condition space size:", df["cond"].nunique())
    print("yield/proxy describe:\n", df["product_1_area%"].describe())
