# Shields et al., Nature 2021 — Bayesian reaction optimization

- **Full cite**: Shields et al., *Nature* 2021, 590, 89–96
- **DOI**: 10.1038/s41586-021-03213-y
- **Date read**: (scaffold)
- **Reader**: platform seed note

## 1. Problem & claims

Shows Bayesian optimization can efficiently search reaction condition spaces with few experiments relative to grid/DoE baselines.

## 2. Data / experimental setting

- Reaction type: multiple organic reactions (see paper)
- Plate / batch metadata: not the focus
- Serves as **cold-start BO** methodological reference for chemistry

## 3. Method takeaways for TransferBO2.0

| Component | Reusable idea |
|---|---|
| Representation | Condition encoding for mixed variables |
| Surrogate / kernel | GP-style surrogate + chemistry-facing workflow |
| Acquisition | EI-style sequential design culture in chem labs |
| Batch correction | Not covered — motivates our plate-aware extension |
| Evaluation | Emphasize early efficiency, not only final optimum |

## 4. Limits relative to our dual-shift setting

Single-campaign optimisation; does not address cross-substrate historical transfer or plate effects.

## 5. One-sentence citation worth keeping

> Bayesian optimisation is a practical tool for chemical reaction condition search under limited experimental budgets.

## 6. Follow-ups

- [x] Add to `bibliography.bib`
- [ ] Re-read methods section when writing related-work
- [ ] Align our metric suite (BSF/AUC) with their reporting style
