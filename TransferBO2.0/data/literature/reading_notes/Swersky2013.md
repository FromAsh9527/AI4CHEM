# Swersky, Snoek, Adams 2013 — Multi-Task Bayesian Optimization

- **Full cite**: Swersky et al., NeurIPS 2013
- **DOI / URL**: (see bibliography.bib)
- **Date read**: (scaffold)
- **Reader**: platform seed note

## 1. Problem & claims

Multi-task BO transfers information across related optimisation tasks via multi-task GPs.

## 2. Data / experimental setting

- Not chemistry-specific
- Tasks share input domain; outputs correlated

## 3. Method takeaways for TransferBO2.0

| Component | Reusable idea |
|---|---|
| Representation | Treat each substrate as a task |
| Surrogate / kernel | ICM / task covariance \(B_{s,s'}\) |
| Acquisition | Joint acquisition across tasks |
| Batch correction | Not covered |
| Evaluation | Transfer vs independent BO |

## 4. Limits relative to our dual-shift setting

No plate/batch effect; new-task cold identity of \(B\) is hard — motivates descriptor-based contextual kernels.

## 5. One-sentence citation worth keeping

> Related optimisation tasks can share statistical strength through a multi-task Gaussian process.

## 6. Follow-ups

- [x] In bibliography
- [ ] Implement full ICM as optional backend (current: contextual / weighted approximations)
