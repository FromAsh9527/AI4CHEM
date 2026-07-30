# descriptors（描述符生成）

与 `../edbo/` **并列**；有独立 Streamlit，不嵌入 EDBO 向导。  
交接约定见 [`../CONTRACT.md`](../CONTRACT.md)。

## 结构

```
descriptors/
├── app.py                 # 可视化界面
├── cli.py                 # 统一命令行
├── io_utils.py
├── generators/            # 每种描述符独立目录
│   ├── rdkit_2d/
│   ├── maccs/
│   ├── morgan/
│   ├── mordred/           # 需 pip install mordred
│   ├── xtb/               # 需 xtb 可执行文件（third_party/xtb/）
│   └── clean/
├── examples/molecules.csv
└── output/
```

## 可视化

```bash
cd BOUSE/descriptors
conda activate edbo
streamlit run app.py
```

## 命令行

```bash
python cli.py list
python cli.py from-smiles examples/molecules.csv --backend rdkit_2d -o output/demo.csv
python cli.py from-smiles examples/molecules.csv --backend maccs -o output/maccs.csv
python cli.py from-smiles examples/molecules.csv --backend morgan --n-bits 128 -o output/fp.csv
python cli.py from-smiles examples/molecules.csv --backend mordred -o output/mordred.csv
python cli.py from-smiles examples/molecules.csv --backend xtb -o output/xtb.csv
python cli.py from-smiles examples/molecules.csv --backend xtb --opt -o output/xtb_opt.csv
python cli.py clean dft.csv --id-col solvent_SMILES -o output/clean.csv --max-features 20
python cli.py validate output/demo.csv
```

分类型脚本：`python generators/<name>/generate.py ...`

## 导入 EDBO

```bash
cd BOUSE
python scripts/import_descriptor.py descriptors/output/demo.csv \
  --workspace edbo/workspaces/<项目> --factor solvent
```
