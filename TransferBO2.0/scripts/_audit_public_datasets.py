"""Quick audit of candidate HTE datasets for TransferBO2.0."""
from pathlib import Path
import pandas as pd

ROOT = Path(r"F:\BaiduSyncdisk\zhangzhou\ed\AI-Pharmacy\AI4CHEM\TransferBO\data")
paths = [
    ROOT / "processed/additives_four_plates.csv",
    ROOT / "processed/edbo_suzuki_plates.csv",
    ROOT / "processed/edbo_amination_plates.csv",
    ROOT / "processed/doyle_cn_plates.csv",
    ROOT / "raw/surf/sm_all.csv",
    ROOT / "raw/surf/bh_all.csv",
    ROOT / "raw/external/BH_HTE_Curated_Dataset_v20260219.csv",
    ROOT / "raw/external/cn-processed.csv",
    ROOT / "raw/external/aryl-scope-ligand.csv",
    ROOT / "raw/external/merck-cn.csv",
    ROOT / "raw/external/amidation.csv",
]

keys = ("plate", "batch", "well", "substrate", "aryl", "amine", "halide", "boron",
        "ligand", "catalyst", "base", "solvent", "yield", "source", "reaction",
        "additive", "temp", "time")

for path in paths:
    print("\n===" , path.name, "exists=", path.exists(), "===")
    if not path.exists():
        continue
    size_mb = path.stat().st_size / 1e6
    try:
        head = pd.read_csv(path, nrows=3)
        cols = list(head.columns)
        print(f"file~{size_mb:.1f}MB n_cols={len(cols)}")
        print("cols:", cols[:45], ("..." if len(cols) > 45 else ""))
        if size_mb > 100:
            df = pd.read_csv(path, nrows=150000)
            print("sampled_rows", len(df))
        else:
            df = pd.read_csv(path)
            print("rows", len(df))
        interesting = [c for c in df.columns if any(k in c.lower() for k in keys)]
        print("interesting:", interesting[:60])
        for cand in ["plate_id", "plate", "Plate", "batch", "Batch", "source", "Source",
                     "well", "Well", "dataset", "Dataset", "campaign"]:
            if cand in df.columns:
                u = df[cand].nunique(dropna=True)
                ex = list(df[cand].dropna().astype(str).unique()[:6])
                print(f"  META {cand}: nunique={u} examples={ex}")
        for cand in df.columns:
            cl = cand.lower()
            if any(x in cl for x in ["substrate", "aryl", "amine", "electrophile",
                                     "nucleophile", "halide", "boronic", "additive",
                                     "reagent_1", "reagent_2", "starting"]):
                print(f"  SUB {cand}: nunique={df[cand].nunique()}")
    except Exception as e:
        print("ERROR", type(e).__name__, e)
