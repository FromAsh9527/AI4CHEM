# High-Throughput Experimentation Datasets for Palladium-Catalyzed Cross-Coupling Reactions

## Overview

This dataset collection contains High-Throughput Experimentation (HTE) data for palladium-catalyzed cross-coupling reactions formatted in the **Standardized Uniform Reaction Format (SURF)**. The datasets include experimental results from Suzuki-Miyaura (SM) and Buchwald-Hartwig (BH) coupling reactions performed at Roche.

## Dataset Descriptions

| File | Reaction Type | Description | Records |
|------|---------------|-------------|---------|
| `sm_all.csv` | Suzuki-Miyaura | All reaction outcomes (including failures) | 3,426 |
| `sm_positive.csv` | Suzuki-Miyaura | Only reactions with positive product formation | 1,878 |
| `bh_all.csv` | Buchwald-Hartwig | All reaction outcomes (including failures) | 10,138 |
| `bh_positive.csv` | Buchwald-Hartwig | Only reactions with positive product formation | 3,441 |

## Data Format (SURF Schema)

All datasets follow the Standardized Uniform Reaction Format (SURF) with the following columns:

### Reaction Identification
| Column | Description |
|--------|-------------|
| `rxn_id` | Unique reaction identifier (Electronic Lab Notebook reference) |
| `rxn_type` | Reaction type: "Suzuki-Miyaura" or "Buchwald-Hartwig" |
| `rxn_date` | Date of reaction execution (DD/MM/YYYY) |

### Reaction Conditions
| Column | Description |
|--------|-------------|
| `temperature_deg_c` | Reaction temperature in degrees Celsius |
| `time_h` | Reaction time in hours |

### Starting Materials
| Column | Description |
|--------|-------------|
| `startingmat_1_name` | Name of first starting material |
| `startingmat_1_smiles` | SMILES representation of first starting material |
| `startingmat_1_eq` | Molar equivalents of first starting material |
| `startingmat_2_name` | Name of second starting material (coupling partner) |
| `startingmat_2_smiles` | SMILES representation of second starting material |
| `startingmat_2_eq` | Molar equivalents of second starting material |

### Reagent
| Column | Description |
|--------|-------------|
| `reagent_1_name` | Name of the base/reagent |
| `reagent_1_smiles` | SMILES representation of the reagent |
| `reagent_1_eq` | Molar equivalents of the reagent |

### Catalyst
| Column | Description |
|--------|-------------|
| `catalyst_name` | Name of the palladium catalyst/ligand system |
| `catalyst_smiles` | SMILES representation of the catalyst |
| `catalyst_eq` | Molar equivalents of the catalyst |

### Solvent(s)
| Column | Description |
|--------|-------------|
| `solvent_1_name` | Name of primary solvent |
| `solvent_1_smiles` | SMILES representation of primary solvent |
| `solvent_1_fraction` | Volume fraction of primary solvent |
| `solvent_2_name`* | Name of secondary solvent (if applicable) |
| `solvent_2_smiles`* | SMILES representation of secondary solvent |
| `solvent_2_fraction`* | Volume fraction of secondary solvent |

*Note: Secondary solvent columns only present in Suzuki-Miyaura datasets. "NoSolvent" indicates no secondary solvent was used.

### Analytical Results
| Column | Description |
|--------|-------------|
| `startingmat_1_area%` | HPLC area percentage of remaining starting material |
| `product_1_name` | Name of the desired product |
| `product_1_smiles` | SMILES representation of the product |
| `product_1_area%` | HPLC area percentage of product (proxy for yield) |
| `contains_water` | Boolean flag indicating if aqueous base was used |

## Reaction Types

### Suzuki-Miyaura Coupling
C–C bond forming reaction between an aryl/vinyl halide and an organoboron compound in the presence of a palladium catalyst and base.

### Buchwald-Hartwig Amination
C–N bond forming reaction between an aryl halide and an amine in the presence of a palladium catalyst and base.

## Notes on Data Processing

- **Positive datasets** (`*_positive.csv`) contain only experiments where product formation was detected when measuring a value of total area percent reduced above 5% (product_1_area% > 0.05)
- **All datasets** (`*_all.csv`) include both successful and unsuccessful reactions
- Yield is reported as HPLC area percentage (`product_1_area%`), which serves as a proxy for reaction yield
- Chemical structures are encoded as canonical SMILES strings

## Usage Guidelines

These datasets are suitable for:
- Machine learning model development for reaction outcome prediction
- Analysis of structure-activity relationships in cross-coupling chemistry
- Benchmarking yield prediction algorithms
- Studying the effect of reaction conditions on catalyst performance

## Citation

If you use these datasets, please cite the associated publication.

## DOI
Record DOI: 10.5281/zenodo.18185850

## License

Please refer to the Zenodo record for licensing information.

## Contact

For questions regarding the dataset, please contact the authors through the associated publication or Zenodo record.

