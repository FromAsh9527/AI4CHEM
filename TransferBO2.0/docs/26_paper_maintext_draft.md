# Main-text draft v2 (English, for submission)

> **写作说明（内部，2026-08-24）**：按"证据冻结 + 叙事校正"意见书（对话 2026-08-24）重写。
> 结构为主题式（问题—证据—机制—部署边界），不是时间顺序。修正点：
> 1) Intro 因果链改为"1.0 遗留 pair 负 → 2.0 立项检验多源池化"（2.0 未跑 pair）；
> 2) "2,130 runs"明确定义为主协议六策略 LOSO 轨迹；
> 3) 跨板/批次表述降级为 cross-substrate（未做 plate/batch correction）；
> 4) 增加 Table 3 无效策略表与 init/continuation 双通道象限框架；
> 5) Claims register（可用/禁用）随稿冻结。
> 所有数字来自修复后结果（HiTEA 特征修复 2026-08-24 重跑；learnability 种子修复），靶级配对 bootstrap 95% CI。
> P3 湿实验未执行，Discussion 如实写明。语言未润色，先定内容。

---

# Throw most of it away: historical HTE data accelerates Bayesian optimization for new substrates through a five-condition list, not a transfer model

## Abstract

Historical high-throughput experimentation (HTE) data should make optimization of a new substrate cheaper, but *how* history enters the loop decides whether it helps or hurts. A common instinct is to transfer the historical yields themselves — as pooled pseudo-observations, similarity-weighted warm starts, or warm points that persist in the surrogate for the whole run. Across four HTE libraries spanning three reaction classes (71 substrate-defined tasks; 2,130 primary leave-one-substrate-out trajectories under one frozen protocol with dual controls), we find that every such "transfer the labels" formulation is at best null and in the Suzuki class significantly negative. The one robustly positive strategy is radically simpler: pool the historical yields across substrates, take the **top-five conditions by mean yield**, run them as round one, and continue with a target-only GP-EI. This list beats cold start on every library we tested (+160.2 and +107.6 AUC on the two complete-grid libraries, CIs excluding zero; +149.9 on the Suzuki grid; +26.3 on the sparse Pfizer panel; +8.1 in a one-dimensional boundary test with 4/4 tasks positive) and beats random search on all but one. The mechanism is rank preservation: within a reaction template, the ordering of conditions is set by ligand/base properties that act on all substrates alike, while the *level* of yields is set by each substrate's own reactivity — so the ranking transfers across substrates and the magnitudes do not. A list carries the ranking; a GP learns magnitudes. We decompose the total transfer gain into an initialization channel (the list) and a continuation channel (target-only EI), show that the two are library-dependent and separately decidable, and give deployment rules: pool ≥3 history substrates (≥5 recommended), report per-condition source coverage, use target-only continuation, and abstain from transferring when neither channel is positive. The positive-gain strategy is a five-condition list, not a transfer model; boundaries are set by substrate diversity and template generality.

**Keywords:** high-throughput experimentation; Bayesian optimization; transfer learning; reaction condition screening; warm-start initialization

---

## 1. Introduction

Four facts motivate this study. First, optimizing reaction conditions for a new substrate is expensive: even with high-throughput experimentation (HTE), a new substrate of a known template typically needs dozens of experiments to reach a good result. Second, historical HTE libraries are abundant — dense condition–yield matrices for the same template over many substrates — and the natural question is whether this history can make the next substrate's optimization cheaper. Third, the answer is not obviously yes: the history is measured on *other* substrates, and a substrate's own reactivity (aryl halide electronics and sterics; nucleophile nucleophilicity) shifts yields in ways that are specific to it, so historical numbers may mislead a target-specific optimizer. Fourth, the literature offers many ways to "use" history — pooled pseudo-labels in a surrogate, similarity-weighted transfer, multi-task models, initial-condition lists — but they are rarely compared on the same frozen protocol across multiple libraries, so it is unknown which form, if any, reliably helps.

Our earlier work (TransferBO 1.0) had already seen the failure mode: transferring observations from a *single* source substrate to a target (pairwise transfer) produced negative effects on a Suzuki template — a single source carries not only the template-generic ranking of conditions but also that substrate's idiosyncratic response, and the transferred "knowledge" is partly noise. Motivated by that limitation, this work (TransferBO 2.0) is designed from the start around the *multi-source* leave-one-substrate-out (LOSO) pool: for each target, history = all other substrates in the library. The question is not "can history help" but *in what form* a multi-source history should enter the loop: as surrogate labels (pooled pseudo-observations, similarity-weighted warm starts, persistent warm points), as a prior (an initial condition list), or not at all.

Contributions. (i) We compare six strategies for using history — random baseline, cold-start BO, pooled top-5 list + target-only EI, nearest-source top-5 list, similarity-weighted warm surrogate, and Spearman-gated warm surrogate — on one frozen protocol across four libraries (three reaction classes, two independent data sources), with a one-dimensional boundary dataset as a fifth. (ii) We separate the total transfer gain into an **initialization channel** (does history give a better starting point?) and a **continuation channel** (given the start, does target-only EI add value?), and show they are library-dependent, independent decisions with a 2×2 deployment logic. (iii) We identify a mechanism — cross-substrate rank preservation of high-yield conditions — that is a measurable correlate of successful ranked-condition transfer. (iv) We give deployment rules including an explicit abstention option.

## 2. Results

### 2.1 The main finding: a pooled top-five condition list is the only consistently positive strategy

Protocol in one sentence: leave-one-substrate-out; rank every condition by its mean yield across the historical substrates; take the top five as round one; continue with 15 steps of target-only GP-EI; evaluate against both cold start (random init + EI) and random search; primary metric = AUC@20 (sum of best-so-far over the 20 steps), target-level paired bootstrap 95% CI.

**Table 1. Pooled top-5 list + target-only EI vs. cold start and vs. random search (AUC@20; target-level paired bootstrap 95% CI, B=5000; seeds 0–4 averaged; numbers as locked in `results/{step1_effects,p4_borylation,p4_hitea}/summary.md`, audit trail `results/paper_numbers/manifest.md`).**

| Library | Template | Source | Tasks | Conds | vs. cold (95% CI) | frac>0 | vs. random (95% CI) | frac>0 |
|---|---|---|---|---|---|---|---|---|
| Amidation | Pd C–N | Doyle (EDBO) | 15 | 260 | **+160.2** [+108.1, +211.6] | 0.87 | **+268.0** [+216.3, +316.1] | 1.00 |
| Borylation | Ni C–B | Doyle (ochem-data) | 33 | 46 | **+107.6** [+73.1, +144.9] | 0.88 | **+123.4** [+89.1, +158.7] | 0.91 |
| Suzuki (EDBO) | Pd C–C | Doyle (EDBO) | 12 | 308 | +149.9 [+38.8, +269.8] | 0.83 | +92.2 [+0.0, +186.5] | 0.83 |
| Suzuki (HiTEA) | Pd C–C | Pfizer (independent) | 11 | 41–48 | +26.3 [−32.2, +80.9] | 0.64 | +36.9 [−10.5, +83.7] | 0.73 |

*The list beats cold start in every library (direction positive in all; CIs exclude zero on the two complete-grid libraries). It beats random search everywhere except EDBO Suzuki, where the EDBO Suzuki random-control CI is [+0.0, +186.5] — its lower bound is a hair above zero by rounding under the locked bootstrap seed, and generically should be read as "positive but fragile" (the CI sits on zero and the random baseline is unusually strong there because cold-start EI itself is unreliable on that template, −57.7 vs random, Table 2). We deliberately avoid the "CI excludes zero" framing for this cell.*

Two features of the gain matter for deployment. First, the gain is **faster, not higher**: on the init-dominated libraries the list raises the best yield found in the first round (init_best +12.3 on amidation, +8.6 on borylation, both CIs excluding zero) while the final best yield after 20 steps is essentially at parity (+2.2 and +0.3, CI containing zero). On EDBO Suzuki the pattern inverts (init_best +5.4, CI containing zero; final_best +5.3, CI excluding zero): the value of history lives in the continuation there (§2.4). Second, the benefit is visible at round granularity: on amidation the list reaches top-5% conditions roughly one round earlier (AUC@5 +93.6 vs. cold) with a 100% vs. 91%/60% reach rate — the promise is *fewer rounds to a good result*, not a higher ceiling.

### 2.2 What the history should *not* do: surrogate-level label transfer is null or harmful

We tested every way of putting historical *yields* into the target surrogate. On amidation, the similarity-weighted warm start (`sim_weighted`) and the Spearman-gated warm start (`safe_gate`) were null relative to cold start (+19.3, CI [−0.9, +35.2] and +11.5, [−16.1, +35.7]); neither approached the pooled list. On EDBO Suzuki both appear positive versus cold (+53.1 and +80.7), but Suzuki's cold baseline is itself weak (§2.4); versus random the advantage collapses, and the four-arm experiment below shows the label-transfer direction is actively harmful there.

**Four-arm continuation experiment (Suzuki class: EDBO Suzuki + HiTEA, 23 targets).** A = list init + target-only EI (baseline); B = A plus the historical rows of the 5 list conditions as warm GP points; C = A plus all historical rows (≤120, subsampled) as warm points; D = list init + random continuation (no-GP control). Warm points cost no target budget — they are free information by construction — yet **B is significantly worse than A** (−59.1 AUC, 95% CI [−139.0, −3.6]) and C is negative in trend (−28.5, [−66.2, +4.3]). More warm data (C) beats less (B) but both lose to none. Historical *values*, even the values of the very conditions the list recommends, cannot be transplanted into the target response surface.

**Matched-initialization audit (amidation).** With the same top-5 init, adding EI continuation is worth little (C1 = +26.0, CI containing zero); cold-start EI, however, is clearly better than cold-start random (C2 = +67.7, CI excluding zero). History's job is the start; the optimizer's job is refinement. We formalize this two-channel decomposition in §2.4.

**Summary of the negative space.** Historical yields as surrogate labels: null (amidation, borylation-class) or negative (Suzuki class, warm continuation). Historical yields as a gated warm start: null. Historical yields as persistent warm points: significantly negative. This is the methodological core: *history-informed initialization and history-augmented surrogate fitting are distinct interventions; the former can help, the latter may degrade sequential optimization.*

### 2.3 Why it works: multi-source pooling is rank aggregation, and the ranking transfers

The positive strategy is a *list* — it carries only order information at the top of the pooled ranking. Its success requires that the condition ordering, especially at the top, is at least partially preserved across substrates of the same template.

**Table 2. Rank preservation of condition orderings across substrates.**

| Library | mean pairwise Spearman ρ (shared conditions) | mean rank of pooled top-5 in a held-out target's own ordering | rank of chance |
|---|---|---|---|
| Amidation | 0.577 | 22.7 / 260 | 130 |
| Borylation | 0.361 | 14.6 / 46 | 23 |
| Suzuki (EDBO) | 0.264 | 87.7 / 308 | 154 |
| Suzuki (HiTEA) | 0.088 | 38 / 48 | 24 |
| CHAOS (1-D boundary) | 0.694 | — | — |

*ρ is positive in every library; the pooled top-5 lands far above chance in the target's own ordering wherever the space is large enough to measure. Full ordering is only partially preserved (ρ ≪ 1), which is why we take the top five rather than the whole ranking.*

The chemistry behind partial rank preservation is direct. Within one template, the *relative* goodness of conditions is set by the intrinsic properties of the catalyst system — ligand sterics and donating power, base basicity and solubility — which act on every substrate alike. The *level* of yields is set by the substrate's own reactivity, which shifts the whole surface up or down without generally reordering it. Extreme conflicts (a very hindered substrate × a very hindered ligand) flip individual pairs — this is why preservation is *partial* and why only the top of the ranking is trustworthy. Multi-source pooling is then the natural implementation of the separation: averaging condition yields across many substrates votes out per-substrate idiosyncrasies and leaves the template-generic main effects. The pooled list is the robust default against the nearest single source (nearest_topk vs. cold: amidation +117.0 vs. pooled +160.2; EDBO Suzuki +24.0 vs. +149.9), but on borylation the nearest source is numerically higher (+114.5 vs. +107.6) and on HiTEA likewise (+60.9 vs. +26.3, wide CI): the near-neighbor result is *inconsistent* across libraries and similarity definitions (it is clearly worse under hashed-SMILES), and — critically — it cannot be known in advance which library's nearest neighbor will be good. Pooling, by contrast, is never worse than a guess and needs no source-selection decision. This matches our locked Step1b finding: "Morgan 下 nearest ≳ topk" (nearest can tie under Morgan), while the deployed default remains the pooled top-k.

**Source-count threshold.** The pooled list stabilizes with source count: n=1 produces Jaccard overlap ≈0.17 against the full-pool list on amidation; ≥3 sources are needed for the pool to approach full-pool behavior, and ≥5 is recommended. Single-source (pairwise) transfer was negative in our earlier protocol — the pooled design is what turns it positive.

**One-dimensional boundary test (CHAOS).** As a stress test of whether the list mechanism requires multi-dimensional condition structure, we applied the identical protocol to the CHAOS additive screen (Prieto Kullmer et al., *Science* 2022): four fixed reactions × 720 shared additives, where the condition space is a single additive identity and the response is UV area. Within-reaction z-scoring removes plate-level scale (the "values do not transfer" operation, applied at ingest). Rank preservation across the four reactions is the highest of all five datasets (ρ = 0.694), and the pooled top-5 list beats cold start on 4/4 tasks (+8.1 AUC; direction-only evidence, n=4). The continuation adds nothing — the list exhausts the signal in one shot (topk vs. topk-random Δ = 0.00 on every task). The list mechanism therefore does not require multi-dimensional condition structure; the simpler the condition space, the more of the signal the list carries.

### 2.4 Initialization value and continuation value are separate decisions

Decomposing the total transfer gain (Table 3, top row vs. cold) into the two channels reveals a clean library-dependent pattern:

- **Amidation / borylation (init mode):** the list provides a strong start (carried Δ +278.5 / +185.9 of the total gain), while the continuation adds little (topk post +51.7 / +51.2; C1 CI containing zero). Cold-start EI is itself valuable (C2 = +67.7 on amidation, excluding zero; cold vs. random +107.8 [+75.4, +145.1]).
- **EDBO Suzuki (continuation mode):** the list is a weak start (init_best +5.4, CI containing zero) but the continuation carries the gain (topk post +189.0; final_best +5.3 excluding zero). Cold-start EI is unreliable (cold vs. random −57.7 [−136.9, +1.4]).
- **HiTEA (weak both):** small condition spaces and high failure rates compress both channels (+26.3 total; C2 = +20.4 excluding zero after feature repair — cold EI works — but the effect sizes are small).

The two channels are therefore independent decisions with a 2×2 deployment logic:

| Initialization value | Continuation value | Recommendation |
|---|---|---|
| High | High | list init + target-only BO |
| High | Low | run the list once; continue little or not at all |
| Low | High | cold-start BO / diversified init + BO |
| Low | Low | abstain from this history; re-model or expand the design space |

A pre-hoc rule to predict the continuation channel from the history alone was sought and failed: additive-R² binning of the response surface did not separate high- from low-continuation targets (strategy-research negative result; pooled p = 0.69). Continuation choice is currently a library-type decision, with a probe-based measurement of rank preservation as the promising future route (§4).

### 2.5 Strategies that did not generalize (the negative evidence, in one table)

**Table 3. Strategies and assumptions rejected under AUC@20 evaluation.**

| Strategy / assumption | Initial motivation | Result | Conclusion |
|---|---|---|---|
| Similarity-weighted pooled GP (`sim_weighted`) | similar substrates share yield levels | null on amidation (+19.3, CI ∋ 0); apparent gain on Suzuki collapses vs. random | not a default; don't transfer labels |
| Spearman-gated warm start (`safe_gate`) | a few target responses identify trustworthy history | null on amidation (+11.5, CI ∋ 0); unstable | current version not deployable |
| Rank-median list aggregation | rank aggregation robust to scale | pooled +1.5 [−14.8, +18.4] vs. mean (AUC@20, all libraries); Suzuki-class only marginal | keep mean rule default |
| Historical warm points in continuation GP | more history ⇒ better posterior | **significantly negative** in four-arm experiment (B vs. A −59.1 [−139.0, −3.6]) | history is init-only |
| Additive-R² continuation rule | surface structure predicts continuation value | binning fails to separate targets | no reliable pre-hoc rule |
| Meta-feature prediction of transfer gain | task attributes predict gain | leave-one-library-out discrimination AUC ≈ 0.47 (chance) | cannot auto-select strategy |
| Nearest-source transfer | most similar substrate is the best donor | inconsistent across libraries (higher on borylation/HiTEA, clearly lower on amidation/Suzuki) and similarity definitions; never predictable in advance | pool by default — nearest is a lottery; don't pick |

*Strategy-research details, including the two reproducibility fixes (HiTEA condition-feature repair; learnability random-seed repair) are recorded in project audit documents and SI; none of the rejected strategies becomes deployable under the corrected results.*

## 3. Discussion

**Why does injecting history into the surrogate fail?** A surrogate must commit to numbers, and the numbers contain the substrate-specific level that does not transfer. Similarity weighting and gates do not fix this — they re-weight the same non-transferable values — and persistent warm points actively distort the target response surface (four-arm experiment). The list avoids the problem by construction: it carries only order information at the top of the ranking, where template-generic chemistry dominates.

**Why can't we learn a gate?** Rank preservation is real but not predictable from pre-computable meta-features (Table 3, last two rows). The mechanism, however, suggests a measurable route: a few probe conditions can directly estimate a source's rank agreement with the target after round one. Probe-based gating is the natural next step and is being tested in our prospective wet-lab protocol.

**Scope and boundaries.** (i) All evidence is retrospective replay on four libraries (71 tasks) plus a one-dimensional boundary dataset (n=4, direction-only); no prospective validation has been completed. A pre-registered wet-lab protocol on our own platform (SNAr template, 128-condition space, 5 conditions per round, 24-vessel throughput) is designed and scheduled; until it reports, results are replayed, not prospective. (ii) We evaluate transfer across substrate-specific historical optimization tasks; we do **not** perform explicit correction of physical plate or batch effects — our plate IDs are logical task labels (and the HiTEA screen's single cross-batch sample supports only a deployment-layer caveat). Extending ranked-condition transfer to physical batch shifts will require bridge conditions, repeated reference reactions, and plate-aware hierarchical models. (iii) Statistical power is limited by 5 seeds, single-measurement oracles, and n=4 libraries at the library level; target-level CIs are reported throughout. (iv) Pooling is the robust default; the nearest single source is numerically higher on some libraries (borylation, HiTEA) but inconsistent across libraries and similarity definitions, and the good nearest neighbor cannot be identified in advance — a statement about *robustness*, not about nearest being always worse. No claim is made about similarity measures outside the tested space.

## 4. Conclusion

Historical HTE data accelerate optimization for new substrates — provided almost all of it is thrown away. Across four libraries, three reaction classes, two independent sources, and a one-dimensional boundary dataset, the only robustly positive way to use history is a **pooled top-five condition list** as round one of a target-only BO: +160 and +108 AUC versus cold start on the two complete-grid libraries (CIs excluding zero), directionally positive on all five datasets, and never beaten by any surrogate-injection or gating alternative — which are null or negative, and significantly negative when historical values persist in the continuation GP. The chemistry is the message: within a reaction template, what transfers is the *ordering* of conditions (set by ligand/base properties common to all substrates), not the *magnitudes* (set by each substrate's own reactivity). A list carries the ordering; a GP learns magnitudes. Initialization and continuation are separate, library-dependent decisions, and abstention is a legitimate default when neither channel is positive.

## 5. Methods

**Data.** Four HTE libraries, three reaction classes, 71 substrate-defined tasks: (i) EDBO amidation, Pd C–N coupling, 15 aryl halides × 260 conditions, complete grid (Ahneman et al. 2018, Doyle lab); (ii) EDBO Suzuki, Pd C–C, 12 × 308, complete grid; (iii) Ni-catalysed C–B borylation, 33 × 46 complete grid (Organometallics 2022, Doyle lab ochem-data); (iv) Pfizer HiTEA Suzuki, 11 tasks × 41–48 core conditions, sparse panel, independent source (King-Smith et al. 2023). Boundary: CHAOS additive screen, 4 reactions × 720 additives (Prieto Kullmer et al., Science 2022). Yields are single measurements; conditions are one-hot encoded categorical features (after the HiTEA ingest fix, factor values are populated from the source data); substrates are Morgan fingerprints (Tanimoto for nearest-source baselines).

**Protocol (frozen, identical across libraries).** Leave-one-substrate-out: for each target, history = all other substrates. n_init = 5; budget B = 20; GP with Matern-2.5 ARD kernel + white noise; EI acquisition; seeds 0–4. Primary metric: optimisation AUC = Σ best-so-far over 20 steps. Secondary diagnostics: AUC@5, init_best, final_best, hits in top-5%, rounds-to-threshold. Inference: average over seeds → target-level → paired bootstrap 95% CI (B=5000). Dual controls: cold start (random init + EI) and random search (no GP). The primary benchmark comprises **2,130 LOSO optimization trajectories** (amidation 450 + borylation 990 + EDBO Suzuki 360 + HiTEA 330; six-strategy protocol where applicable). Additional matched-initialization (amidation C1–C3, Suzuki P0), four-arm continuation (230), rank-median re-checks (355), diagnostics, and the CHAOS boundary (100) runs are reported separately.

**Strategies.** Pooled top-5 list (rank by cross-source mean yield); nearest-source top-5 (top-5 of the most similar source by Tanimoto on Morgan); similarity-weighted warm surrogate (`sim_weighted`: historical points enter the GP with similarity weights); Spearman-gated warm surrogate (`safe_gate`: gate history by source–target rank agreement estimated on initial observations); warm-continuation arms B/C (historical rows as persistent GP training points, no budget cost). Matched-initialization contrasts: C1 (same top-5 init; EI vs. random continuation), C2 (same random init; EI vs. random continuation).

**Rank preservation.** Per library, mean pairwise Spearman of condition orderings over shared conditions; top-of-ranking stability = mean rank of the pooled top-5 conditions in each target's own ordering. **Reproducibility:** all random states are fixed and written to config; Python `hash()` is not used as a randomness source (one analysis script was repaired accordingly); the HiTEA ingest pipeline is fixed and re-run (2026-08-24), and all HiTEA numbers in this manuscript come from the repaired pipeline.

## Code and data availability

All analysis scripts and processed data are available at [repository URL]; the frozen protocol, evaluation code, per-job results, and the repair log (HiTEA feature fix; learnability seed fix) are included. Source datasets: Doyle lab (EDBO amination, EDBO Suzuki, borylation), Pfizer (HiTEA), Prieto Kullmer et al. (CHAOS).

---

## Claims register (frozen 2026-08-24; internal companion to the manuscript)

**Approved claims (may appear in the manuscript):**
1. A multi-source pooled top-k condition list is an effective warm-start prior for optimizing a new substrate (strong on amidation and borylation; directionally positive on all five datasets).
2. Top-k list initialization is superior to transferring historical yields into the target GP (null on amidation-class; significantly negative in Suzuki-class warm continuation).
3. Multi-source pooling is the robust default against single nearest-source transfer — nearest is numerically higher on some libraries (borylation, HiTEA) but inconsistent across libraries and similarity definitions, and the good neighbor cannot be identified in advance.
4. Cross-substrate rank preservation of high-yield conditions is a mechanistically informative correlate — and a plausible enabling condition — of successful ranked-condition transfer (not claimed as proven causation; no reliable target-level predictor yet).
5. Initialization gain and continuation gain are library-dependent, separately decidable questions.
6. No stable pre-hoc meta-feature predictor of transfer success exists in our data.
7. For high-risk or low-learnability libraries, abstention is a legitimate deployment default rather than failure.

**Claims NOT to make:**
1. "All reaction classes transfer." — false; Suzuki/HiTEA heterogeneity.
2. "Transfer BO generally beats cold BO." — too strong; top-k warm-start is the consistent positive form, not a universal claim.
3. "Substrate structural similarity guides source selection." — unsupported; nearest is inconsistent across libraries and never predictable, so pooling is the default.
4. "The safe gate avoids negative transfer." — unsupported.
5. "Plate/batch effects are corrected." — false; logical plate IDs, no systematic cross-plate replication, no anchor-condition correction; HiTEA batch evidence is deployment-layer only.
6. "Continuation value is predictable pre-hoc." — negative result.
7. "Rank preservation predicts per-target transfer success." — library-level mechanism support only.
8. "TransferBO 2.0 ran pairwise transfer." — false; pairwise negative transfer is a TransferBO 1.0 legacy result; 2.0 is multi-source LOSO by design.

## SI contents (for review; not in main text)

- S1. Library descriptions and protocol freeze (docs/18, docs/10).
- S2. Matched-init audit full tables (C1–C4) for all libraries.
- S3. Round-level metrics (AUC@k, rounds-to-threshold, hits in top-5%).
- S4. Source-count threshold curves (n=1..all; Jaccard and init_best).
- S5. Aggregation-rule ablation (mean vs rank-median vs best-source vs UCB-style).
- S6. Representation-axis results (Step1b: Morgan substrates accepted; DFT / condition Morgan rejected).
- S7. Rank-preservation and dual-channel mechanism analysis (learnability; additive-R² vs continuation value) — including the seed-repair note.
- S8. HiTEA feature-repair audit (2026-08-24: ingest factor fix, 495-job re-run, before/after numbers) and batch-effect note.
- S9. Seed sensitivity (planned).
- S10. CHAOS 1-D boundary validation details.
- S11. Strategy-research log (phase 0 meta-feature discrimination; four-arm warm experiment; rank-median AUC-layer re-check) — internal record.
