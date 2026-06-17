# confgate — Next Experiments (Priority Queue)

_The grouping deliverable: swept papers -> CF/CH levers -> ranked CG-FE
experiments that could beat the free length+logprob gate._

_Auto-generated from the confgate research graph. Do not edit directly._
_Regenerate: `cd research-graph && python generate_next_experiments.py`_
_Generated: 2026-06-16 23:43 UTC_

---

## CRITICAL (ROI 9-10) — Do these first

### CG-FE18 (CG) — [ROI: 9, READY, HIGH]

**What:** Information-removal stress test of the free (length+logprob) gate: build a text analog of the paper's 18->6 frame cut by progressively truncating MATH-500 problem context / dropping reasoning scaffold, then re-measure free-gate OOF AUROC and fixed-threshold conditional risk versus the in-distribution pins.

**Why:** confgate validated CF-1 across family/scale/domain shift but never under information removal. The paper shows confidence (incl. logprob) fails to contract under a 67% evidence cut. If free-gate AUROC collapses under text information-removal while length-only holds, CF-1's 'most generalizing' claim is bounded to the three tested shift axes.

**Cost:** 1-2 days local CPU (fresh generations on truncated prompts, 1.5-2B model)
**Triggered by:** [Explicit Abstention Knobs for Predictable Reliability in Video Question Answering](https://arxiv.org/abs/2601.00138)
**Depends on:** CF-2, CF-1
**Would update:** CF-1
**Trigger condition:** Paper 2601.00138 shows logprob p_max increases (0.870->0.876) under a 67% evidence cut while accuracy drops; confidence non-contraction is a fourth, untested shift axis for the free gate.

---

## HIGH (ROI 7-8)

### CG-FE1 (CG) — [ROI: 8, READY, HIGH]

**What:** Swap confgate's light-head nonconformity for an LAC softmax-margin score (S=1-p_correct over sampled-answer clusters) and re-run cross-domain MATH->BBH split-conformal LTT at eps=0.2.

**Why:** Kumar 2023 shows LAC margin transfers across MMLU subjects with only ~7pp coverage loss; confgate's cross-domain wall (validity 0.0) may be a score artifact, not fundamental. A bounded margin score is the most promising candidate to crack CF-5.

**Cost:** 30min CPU
**Triggered by:** [Conformal Prediction with Large Language Models for Multi-Choice Question Answering](https://arxiv.org/abs/2305.18404)
**Trigger condition:** Out-of-subject exchangeability degrades only to ~83% coverage (vs 90% target) under LAC margin, far softer than confgate's 0.0 cross-domain validity.

### CG-FE11 (CG) — [ROI: 8, READY, HIGH]

**What:** Recompute free-gate / length-only / logprob-only OOF AUROC on BASE SmolLM2-1.7B vs the Instruct checkpoint over the same MATH-500 items; measure the length-only AUROC delta against the pinned 0.781.

**Why:** SmolLM2's SmolTalk (Smol-Constraint/Rewrite/Summarization) + UltraFeedback DPO explicitly train length/constraint control, which can decouple n_gen_tokens from difficulty. If the length signal is materially weaker post-training, CF-1's 'most generalizing' is a recipe artifact, not a universal property.

**Cost:** 30min CPU (re-score cached generations from two checkpoints)
**Triggered by:** [SmolLM2: When Smol Goes Big -- Data-Centric Training of a Small Language Model](https://arxiv.org/abs/2502.02737)
**Depends on:** CF-2, CF-1
**Would update:** CF-1
**Trigger condition:** 2502.02737 documents the length-control post-training stack behind the pinned 0.810 SmolLM2 gate.

### CG-FE19 (CG) — [ROI: 8, READY, HIGH]

**What:** Observability-conditioned cross-domain conformal certificate: add an evidence/observability proxy (prompt length, n_gen_tokens, retrieved-context size) as a warrant-style conditioning term (p <= zeta_hat(e)+eps) inside certify_cross_domain(), and test whether MATH->BBH validity rises above the pinned 0.0 at eps=0.2.

**Why:** CF-5 attributes the cross-domain wall to head capacity ('any light head'). The paper reframes it as missing evidence-conditioning. If a cheap observability proxy restores validity>0, the wall was mis-diagnosed and CH-4 has a light-head route.

**Cost:** 20min CPU (reuses cached cross-domain scores + pinned arrays)
**Triggered by:** [Explicit Abstention Knobs for Predictable Reliability in Video Question Answering](https://arxiv.org/abs/2601.00138)
**Depends on:** CF-5
**Would update:** CF-5
**Trigger condition:** Paper 2601.00138's warrant bound p<=zeta(e)+eps targets exactly the failure (confidence not tracking what evidence supports) behind cross-domain validity 0.0.

### CG-FE22 (CG) — [ROI: 8, READY, HIGH]

**What:** Fit a TF-IDF (1-3 gram) logistic-regression readout on raw MATH-500/BBH prompt strings to predict correctness, OOF, and compare AUROC to the pinned preflight prompt-length-only ceiling 0.7056.

**Why:** CF-7 closed the preflight question using length + prompt-cloud eigenspectrum but never tested lexical n-gram content; this paper shows prompt-text n-grams predict a downstream model behavior at ~76% pre-generation. If lexical features clear ~0.73, CF-7's ceiling is too narrow and CH-2 has a winner.

**Cost:** 30min CPU
**Triggered by:** [I'm Afraid I Can't Do That: Predicting Prompt Refusal in Black-Box Generative Language Models](https://arxiv.org/abs/2306.03423)
**Depends on:** CF-7
**Would update:** CF-7
**Trigger condition:** Reuter & Schulze 2306.03423: TF-IDF 1-3-gram logreg predicts refusal from prompt alone at 73.9% (LR) / 75.9% (BERT).

### CG-FE6 (CG) — [ROI: 8, READY, HIGH]

**What:** Swap confgate's light-head nonconformity for an LAC softmax-margin score (S=1-p_correct over sampled-answer clusters) and re-run cross-domain MATH->BBH split-conformal LTT at eps=0.2.

**Why:** Kumar 2023 shows LAC margin transfers across MMLU subjects with only ~7pp coverage loss; confgate's cross-domain wall (validity 0.0) may be a score artifact, not fundamental. A bounded margin score is the most promising candidate to crack CF-5.

**Cost:** 30min CPU
**Triggered by:** [Conformal Prediction with Large Language Models for Multi-Choice Question Answering](https://arxiv.org/abs/2305.18404)
**Depends on:** CF-4, CF-5
**Would update:** CF-5
**Trigger condition:** Out-of-subject exchangeability degrades only to ~83% coverage (vs 90% target) under LAC margin, far softer than confgate's 0.0 cross-domain validity.

### CG-FE12 (CG) — [ROI: 7, READY, HIGH]

**What:** Join the pinned free-gate OOF AUROCs (SmolLM2 0.810, Gemma-2-2B 0.844, OLMo-2-1B 0.838) against each base's published GSM8K/MATH accuracy and test whether gate AUROC trends DOWN as base accuracy rises.

**Why:** Free-scalar separability depends on base error structure. SmolLM2 underperforms Qwen2.5-1.5B on math despite curation; if AUROC anti-correlates with base capability, the gate degrades in exactly the stronger-base configuration CF-8's base-swap prescribes, and the 0.810 anchor is partly base-mediocrity.

**Cost:** 20min CPU (AUROC side is pinned; only join external accuracy)
**Triggered by:** [SmolLM2: When Smol Goes Big -- Data-Centric Training of a Small Language Model](https://arxiv.org/abs/2502.02737)
**Depends on:** CF-8, CF-1
**Would update:** CF-1
**Trigger condition:** 2502.02737 Tables 4/5 show SmolLM2 < Qwen2.5-1.5B on GSM8K/MATH.

### CG-FE15 (CG) — [ROI: 7, READY, HIGH]

**What:** Zero-training contrastive-logprob readout: re-score cached MATH-500 generations under a 'generate a correct solution' vs 'generate an incorrect solution' prefix on the shipped small models; test whether Delta = logprob(correct-prefix) - logprob(incorrect-prefix) beats the free gate's OOF AUROC on held-out families.

**Why:** NAT shows instruction-tuned models hold accessible correct-vs-incorrect knowledge surfaced by prefix conditioning. mean_logprob alone is ~chance for SmolLM2 (0.5175); a contrastive framing may recover signal the free gate discards, directly attacking CH-1 with no fine-tuning and no new data.

**Cost:** 30min CPU
**Triggered by:** [Learning From Failure: Integrating Negative Examples when Fine-tuning Large Language Models as Agents](https://arxiv.org/abs/2402.11651)
**Depends on:** CF-2, CF-1
**Would update:** CF-1
**Trigger condition:** NAT prefix-conditioning steers generation correctness via a natural-language prompt.

### CG-FE16 (CG) — [ROI: 7, READY, MEDIUM]

**What:** NAT vs vanilla SFT base-swap ceiling: fine-tune a domain-specialized small base (SmolLM2-1.7B or Qwen2.5-Math) on MATH-500 ReAct trajectories with NAT correct/incorrect prefix labeling vs positives-only SFT; measure resulting base accuracy AND the free-gate / gate-ordered-cascade ceiling each base supports.

**Why:** CF-8's recipe treats base-swap as the deployment lever and warns against gate-curation of distillation data. NAT shows a third lever: keeping the 60%+ discarded negatives with correct/incorrect labels. If NAT-training raises the base ceiling above plain base-swap at matched compute, CF-8 is incomplete.

**Cost:** H100 day
**Triggered by:** [Learning From Failure: Integrating Negative Examples when Fine-tuning Large Language Models as Agents](https://arxiv.org/abs/2402.11651)
**Depends on:** CF-1, CF-8
**Would update:** CF-8
**Trigger condition:** NAT beats positives-only agent-SFT by up to +8.74% by recovering signal from failed trajectories.

### CG-FE2 (CG) — [ROI: 7, READY, HIGH]

**What:** Reframe in-domain certification as a conformal set over k sampled completions per MATH category (LAC over answer clusters) instead of a binary correctness gate, and measure group-conditional coverage vs certify_grouped.

**Why:** Their per-subject (Mondrian) CP reaches valid ~90% coverage at usable set sizes (2.4-3.7) because a bounded label-space yields separated scores; confgate's near-zero Mondrian coverage (0.005-0.05) may stem from binary-correctness flatness, not the group budget.

**Cost:** 1hr CPU
**Triggered by:** [Conformal Prediction with Large Language Models for Multi-Choice Question Answering](https://arxiv.org/abs/2305.18404)
**Trigger condition:** Per-subject conformal sets are valid and usable from ~50 labels, vs CF-6 needing 16-32 in-group labels for near-zero coverage.

### CG-FE20 (CG) — [ROI: 7, READY, MEDIUM]

**What:** Logprob-scalar robustness split under shift: separately track length_only vs logprob_only AUROC degradation for Gemma (where logprob carries, pinned 0.756) under the CG-FE18 information-removal condition, to test whether the logprob component is the brittle one.

**Why:** The paper's headline is that logprob p_max is LESS shift-sensitive than self-report (it increases under evidence loss). If logprob_only degrades/inverts while length_only holds, CF-2's symmetric 'pin both' is the wrong posture under shift and a length-led gate is safer.

**Cost:** 20min CPU (rides on CG-FE61 generations; two extra readouts)
**Triggered by:** [Explicit Abstention Knobs for Predictable Reliability in Video Question Answering](https://arxiv.org/abs/2601.00138)
**Depends on:** CF-2
**Would update:** CF-2
**Trigger condition:** Paper 2601.00138 Table 5: logprob p_max 0.870->0.876 under degradation vs self-report 0.832->0.804.

### CG-FE21 (CG) — [ROI: 7, READY, MEDIUM]

**What:** Cascade robustness under information-removal shift: re-run the gate-ordered cascade on the CG-FE18 degraded-evidence MATH variant and recompute hybrid_beats_hull_gap_pp to test whether the pinned +3.38pp matched-cost advantage survives when gate confidence fails to contract.

**Why:** A cascade tuned in-distribution keeps overconfident-wrong items in the cheap tier when confidence does not contract under shift. The paper shows coverage drops only 10-16% against a 67% information cut, so the cascade would retain too many degraded items and the hull gap could vanish.

**Cost:** 30min CPU (reuses CG-FE61 generations + existing cascade code)
**Triggered by:** [Explicit Abstention Knobs for Predictable Reliability in Video Question Answering](https://arxiv.org/abs/2601.00138)
**Depends on:** CF-1, CF-3
**Would update:** CF-3
**Trigger condition:** Paper 2601.00138: at fixed threshold, coverage falls 16% against a 67% evidence cut -> gate keeps too many degraded items.

### CG-FE23 (CG) — [ROI: 7, READY, HIGH]

**What:** Ensemble the free (length, logprob) gate with TF-IDF n-gram features over the prompt (and optionally the generated answer text); evaluate OOF on held-out families against the free-gate baselines (SmolLM2 0.810 / Gemma 0.844 / OLMo-2 0.838).

**Why:** CF-1 calls the free gate the most-generalizing zero-cost readout, but n-gram TF-IDF features are also zero-extra-compute and encode topical hardness that length+logprob discard by construction. A win on any held-out family refutes the 'most generalizing zero-cost' claim.

**Cost:** 45min CPU
**Triggered by:** [I'm Afraid I Can't Do That: Predicting Prompt Refusal in Black-Box Generative Language Models](https://arxiv.org/abs/2306.03423)
**Depends on:** CF-7, CF-1
**Would update:** CF-1
**Trigger condition:** Reuter & Schulze 2306.03423 demonstrate lexical prompt features carry downstream-behavior signal; CF-1 free gate is content-blind.

### CG-FE7 (CG) — [ROI: 7, READY, HIGH]

**What:** Reframe in-domain certification as a conformal set over k sampled completions per MATH category (LAC over answer clusters) instead of a binary correctness gate, and measure group-conditional coverage vs certify_grouped.

**Why:** Their per-subject (Mondrian) CP reaches valid ~90% coverage at usable set sizes (2.4-3.7) because a bounded label-space yields separated scores; confgate's near-zero Mondrian coverage (0.005-0.05) may stem from binary-correctness flatness, not the group budget.

**Cost:** 1hr CPU
**Triggered by:** [Conformal Prediction with Large Language Models for Multi-Choice Question Answering](https://arxiv.org/abs/2305.18404)
**Depends on:** CF-6
**Would update:** CF-6
**Trigger condition:** Per-subject conformal sets are valid and usable from ~50 labels, vs CF-6 needing 16-32 in-group labels for near-zero coverage.

---

## MEDIUM (ROI 5-6)

### CG-FE10 (CG) — [ROI: 6, READY, MEDIUM]

**What:** Test a set-size (singleton-set) keep/escalate rule against the gate-ordered cascade at matched cost on the 1.5B->7B MATH cascade.

**Why:** Their set-size-stratified selective classification keeps only confident singleton sets; this is an alternative cascade keep-rule that could beat gate-ordering at the +3.38pp anchor's operating point (pct_kept 0.30, acc 0.692).

**Cost:** 30min CPU
**Triggered by:** [Conformal Prediction with Large Language Models for Multi-Choice Question Answering](https://arxiv.org/abs/2305.18404)
**Depends on:** CF-3
**Would update:** CF-3
**Trigger condition:** Set-size stratification yields accuracy well above naive top-1 on kept predictions, suggesting a competitive matched-cost keep rule.

### CG-FE14 (CG) — [ROI: 6, READY, MEDIUM]

**What:** Re-run the gate-ordered cascade with a data-centric small base (SmolLM2-1.7B) as the keep model against the current Qwen-1.5B keep model; test whether the hull gap shrinks below the 0.96pp bootstrap SE.

**Why:** CF-3's +3.38pp rides on a wide 0.486-vs-0.732 keep/escalate gap. SmolLM2 shows extended-training small models acquire large-model abilities (MCF emergence), which would narrow that gap and make CF-3's dominance margin a function of keep-model undertraining.

**Cost:** 2hr CPU if SmolLM2 MATH generations are cached; else H100 to generate
**Triggered by:** [SmolLM2: When Smol Goes Big -- Data-Centric Training of a Small Language Model](https://arxiv.org/abs/2502.02737)
**Depends on:** CF-3
**Would update:** CF-3
**Trigger condition:** 2502.02737 Section 4.3 reports above-random MMLU MCF emergence in a 1.7B model after long training.

### CG-FE17 (CG) — [ROI: 6, READY, LOW]

**What:** Prompt-contrast routing signal: for each query, generate continuations under correct-prefix and incorrect-prefix and use their divergence (e.g. answer disagreement or logprob gap) as an escalation score; route the 1.5B->7B cascade by this score and compare the accuracy-cost hull gap against the gate-ordered cascade.

**Why:** CF-3 claims gate-ordered cascade dominates introspection at matched cost (+3.38pp over hull). The correct/incorrect prefix is a near-free introspection probe; if contrast-routing beats gate-order on the hull, CF-3's dominance claim fails. Risk: the contrast signal may collapse to length, which the gate already exploits.

**Cost:** 2h CPU
**Triggered by:** [Learning From Failure: Integrating Negative Examples when Fine-tuning Large Language Models as Agents](https://arxiv.org/abs/2402.11651)
**Depends on:** CF-1, CF-3
**Would update:** CF-3
**Trigger condition:** NAT's correct/incorrect conditioning exposes a cheap self-contrast difficulty signal.

### CG-FE3 (CG) — [ROI: 6, READY, MEDIUM]

**What:** Add prompt-ensemble averaging (N prompt variants, mean nonconformity) to confgate's score readout and re-run phase4 recalibration to test whether valid cross-domain/cross-scale coverage emerges below k=32 labels.

**Why:** Kumar 2023 reduces nonconformity variance by averaging softmax over 10 prompts and gets valid coverage from ~50 labels; confgate's k>=32 feasibility floor may be a high-variance-score artifact removable by ensembling.

**Cost:** CPU-hours (10x generation on cached models)
**Triggered by:** [Conformal Prediction with Large Language Models for Multi-Choice Question Answering](https://arxiv.org/abs/2305.18404)
**Trigger condition:** Ten-prompt averaging yields valid per-subject coverage at small calibration sizes, against CF-4's k>=32 recalibration floor.

### CG-FE4 (CG) — [ROI: 6, READY, MEDIUM]

**What:** Compute a normalized answer-token softmax-margin readout (LAC 1-p) over confgate generations and benchmark OOF AUROC against the free length+logprob baseline on SmolLM2/Gemma/OLMo-2.

**Why:** LAC margin is near-zero-cost and tightly correlated with accuracy; logprob_only is near chance (0.517 SmolLM2) so a decision-margin signal may add OOF AUROC over the free gate (0.810/0.844/0.838).

**Cost:** 20min CPU
**Triggered by:** [Conformal Prediction with Large Language Models for Multi-Choice Question Answering](https://arxiv.org/abs/2305.18404)
**Trigger condition:** Single-element conformal sets beat naive top-1 accuracy, implying the margin carries selective-prediction signal beyond length+logprob.

### CG-FE5 (CG) — [ROI: 6, READY, MEDIUM]

**What:** Test a set-size (singleton-set) keep/escalate rule against the gate-ordered cascade at matched cost on the 1.5B->7B MATH cascade.

**Why:** Their set-size-stratified selective classification keeps only confident singleton sets; this is an alternative cascade keep-rule that could beat gate-ordering at the +3.38pp anchor's operating point (pct_kept 0.30, acc 0.692).

**Cost:** 30min CPU
**Triggered by:** [Conformal Prediction with Large Language Models for Multi-Choice Question Answering](https://arxiv.org/abs/2305.18404)
**Trigger condition:** Set-size stratification yields accuracy well above naive top-1 on kept predictions, suggesting a competitive matched-cost keep rule.

### CG-FE8 (CG) — [ROI: 6, READY, MEDIUM]

**What:** Add prompt-ensemble averaging (N prompt variants, mean nonconformity) to confgate's score readout and re-run phase4 recalibration to test whether valid cross-domain/cross-scale coverage emerges below k=32 labels.

**Why:** Kumar 2023 reduces nonconformity variance by averaging softmax over 10 prompts and gets valid coverage from ~50 labels; confgate's k>=32 feasibility floor may be a high-variance-score artifact removable by ensembling.

**Cost:** CPU-hours (10x generation on cached models)
**Triggered by:** [Conformal Prediction with Large Language Models for Multi-Choice Question Answering](https://arxiv.org/abs/2305.18404)
**Depends on:** CF-5, CF-4
**Would update:** CF-4
**Trigger condition:** Ten-prompt averaging yields valid per-subject coverage at small calibration sizes, against CF-4's k>=32 recalibration floor.

### CG-FE9 (CG) — [ROI: 6, READY, MEDIUM]

**What:** Compute a normalized answer-token softmax-margin readout (LAC 1-p) over confgate generations and benchmark OOF AUROC against the free length+logprob baseline on SmolLM2/Gemma/OLMo-2.

**Why:** LAC margin is near-zero-cost and tightly correlated with accuracy; logprob_only is near chance (0.517 SmolLM2) so a decision-margin signal may add OOF AUROC over the free gate (0.810/0.844/0.838).

**Cost:** 20min CPU
**Triggered by:** [Conformal Prediction with Large Language Models for Multi-Choice Question Answering](https://arxiv.org/abs/2305.18404)
**Depends on:** CF-2, CF-1
**Would update:** CF-1
**Trigger condition:** Single-element conformal sets beat naive top-1 accuracy, implying the margin carries selective-prediction signal beyond length+logprob.

---

## LOW (ROI 1-4)

_(none)_

---

## Completed

_(none yet)_

---

## Closed by adjacency (MOOTED / ANSWERED)

Closed without being run: an adjacent experiment refuted the premise
(MOOTED) or already answered the question (ANSWERED). Provenance is on
the MOOTED_BY/ANSWERED_BY edge; resurrect with `update_status.py <id> READY`.

- **CG-FE24** [MOOTED by H-R, 2026-06-16] — Born MOOTED — relies on refuted premise 'curation-helps-distillation' (SPEC v8 H-R refuted: gate 0.494 < unfiltered 0.500 < skyline 0.504 <…
- **CG-FE13** [MOOTED by H-R, 2026-06-16] — Born MOOTED — relies on refuted premise 'curation-helps-distillation' (SPEC v8 H-R refuted: gate 0.494 < unfiltered 0.500 < skyline 0.504 <…

---

## Watchlist — Papers to monitor for new triggers

These papers are referenced as triggers for future experiments. When a
follow-up appears (or the original methodology gets a public implementation),
check whether any experiment's status should change.

| arxiv_id | title | triggers experiment(s) | status |
|---|---|---|---|
| [2502.02737](https://arxiv.org/abs/2502.02737) | SmolLM2: When Smol Goes Big -- Data-Centric Training of a Small Language Model | CG-FE11, CG-FE12, CG-FE14 | READY |
| [2601.00138](https://arxiv.org/abs/2601.00138) | Explicit Abstention Knobs for Predictable Reliability in Video Question Answering | CG-FE18, CG-FE19, CG-FE20, CG-FE21 | READY |
| [2402.11651](https://arxiv.org/abs/2402.11651) | Learning From Failure: Integrating Negative Examples when Fine-tuning Large Language Models as Agents | CG-FE15, CG-FE16, CG-FE17 | READY |
| [2305.18404](https://arxiv.org/abs/2305.18404) | Conformal Prediction with Large Language Models for Multi-Choice Question Answering | CG-FE1, CG-FE2, CG-FE3, CG-FE4, CG-FE5, CG-FE6, CG-FE7, CG-FE8, CG-FE9, CG-FE10 | READY |
| [2306.03423](https://arxiv.org/abs/2306.03423) | I'm Afraid I Can't Do That: Predicting Prompt Refusal in Black-Box Generative Language Models | CG-FE22, CG-FE23 | READY |
