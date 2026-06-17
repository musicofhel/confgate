# HYPOTHESES.md — confgate levers (CH-N)

The **relevance perimeter**: a swept paper is admitted iff it could plausibly
corroborate/contradict a CF-N **or** inform one of these levers. Each lever is a
concrete way a paper could help **beat the free gate**. Lean inclusive on
admission — a false-positive admit is far cheaper than a false-negative miss.

**Priority key.** HIGH | MEDIUM | LOW | PARKED.

**Numbering continues monotonically. Next ID: CH-14.**

---

### CH-1: A zero/low-cost readout beats free length+logprob OOF AUROC on held-out families

**Priority:** HIGH

**Motivated by:** CF-1 — free length+logprob is the current generalization
ceiling (SmolLM2 0.810 / Gemma 0.844 / OLMo-2 0.838). Any cheaper-or-equal
readout that beats it OOF on held-out families is the single biggest win.

**Test:** Fit the candidate readout under the same OOF StratifiedKFold-5 protocol
on the three held-out families; compare AUROC to the free baseline per family.

**Requires:** the held-out family caches; the candidate's per-example feature at
matched (≈ zero) cost.

**Would change:** CF-1 (and the shipped gate) if it wins on ≥2 of 3 families.

**Blocks:** nothing.

### CH-2: A cheap pre-generation signal beats prompt-length 0.71

**Priority:** MEDIUM

**Motivated by:** CF-7 — prompt-length-only preflight is 0.706 and the
prompt-cloud eigenspectrum added nothing (H-E refuted). A better pre-gen feature
would raise the before-generation gate.

**Test:** Compute the candidate pre-generation feature on the preflight cache;
frozen-fold OOF AUROC vs the 0.706 prompt-length baseline with a significance test.

**Requires:** the preflight cache; a pre-generation-only feature (no decode).

**Would change:** CF-7 if OOF AUROC clears 0.706 significantly.

**Blocks:** nothing.

### CH-3: A routing/cascade policy beats gate-ordered cascade at matched cost

**Priority:** HIGH

**Motivated by:** CF-3 — gate-ordering is +3.38pp over the self-consistency hull.
A learned router or better escalation policy that beats it at the same budget
raises the deployed cascade.

**Test:** Implement the candidate policy; compare accuracy at matched cost_rel
against the gate-ordered cascade on the 1.5B/7B overlap set.

**Requires:** the cascade keep/escalate caches; the candidate policy's routing signal.

**Would change:** CF-3 if it dominates gate-ordering at matched cost.

**Blocks:** nothing.

### CH-4: A light-head method delivers valid cross-domain certificates

**Priority:** HIGH

**Motivated by:** CF-5 — cross-domain (MATH→BBH) certs are infeasible with every
light head tested (validity 0.0 ∀ feasible k); a method that cracks this wall at
matched cost would be a headline result.

**Test:** Fit the candidate cross-domain recalibration; measure validity at ε=0.2,
δ=0.1, R=200 vs the validity-0.0 baseline.

**Requires:** the MATH calibration + BBH test caches; the candidate light head.

**Would change:** CF-5 (refutes "infeasible") if validity ≥ 1−δ at a deployment ε.

**Blocks:** nothing.

### CH-5: A better escalation target / base-swap raises the matched-cost ceiling

**Priority:** MEDIUM

**Motivated by:** CF-8 — Qwen2.5-Math-1.5B base-swap (+9.2pp @ ¼ cost) and
Qwen2.5-Math-7B escalation (+4.2pp) are the current ceiling. A stronger small
specialist or escalation model would extend the recipe.

**Test:** Drop the candidate model into the base-swap / escalation slot; compare
matched-cost MATH-500 accuracy (token-FLOPs budget) and free-gate OOF AUROC.

**Requires:** a model harness (likely H100 — note: experiment *execution* is v2,
out of MVP scope; this lever is for the queue).

**Would change:** CF-8 if it beats Qwen2.5-Math at matched cost.

**Blocks:** nothing (execution deferred to the v2 autopilot spec).

### CH-6: Group-conditional / adaptive conformal raises Mondrian in-domain coverage

**Priority:** MEDIUM

**Motivated by:** CF-6 — in-domain Mondrian certs are valid but ≤5.4% coverage
with a per-group label budget. A method that raises coverage while holding
validity makes the in-domain cert useful.

**Test:** Apply the candidate group-conditional/adaptive scheme to the in-domain
MATH 5-fold OOF; measure per-group validity and mean coverage vs the algebra/
prealgebra baselines.

**Requires:** the in-domain MATH per-category caches; per-group labels.

**Would change:** CF-6 if it raises coverage materially at held validity.

**Blocks:** nothing.

---


### CH-7: The free gate's AUROC anti-correlates with base-model capability
**Priority:** HIGH
**Motivated by:** 2502.02737 + CF-1 + CF-8
**Test:** Join pinned free-gate OOF AUROCs (SmolLM2 0.810, Gemma-2-2B 0.844, OLMo-2-1B 0.838) plus a strong-math base (Qwen2.5-1.5B) against each base's GSM8K/MATH accuracy; regress AUROC on base accuracy. ~30min CPU (AUROC pinned; accuracy external).
**Requires:** CPU only; pinned_meta.json + published base accuracies (no new generations for the pinned models).
**Would change:** Confirm → the 0.810 anchor is partly an artifact of base mediocrity and CF-8's base-swap erodes the gate; the free gate needs per-base recalibration. Reject → gate generalization is genuinely base-invariant, strengthening CF-1.
**Blocks:** nothing

### CH-8: Post-training length-control decouples n_gen_tokens from difficulty
**Priority:** MEDIUM
**Motivated by:** 2502.02737 + CF-1 + CF-2
**Test:** Compare length-only gate AUROC on base vs Instruct SmolLM2-1.7B over MATH-500; if Instruct's length signal is weaker, length carries difficulty only pre-alignment. ~30min CPU on cached generations.
**Requires:** CPU; both SmolLM2 checkpoints' cached MATH generations.
**Would change:** Confirm → CF-1's "most generalizing" is recipe-conditional; gates must be refit per post-training stack. Reject → length↔difficulty survives alignment, hardening CF-1/CF-2.
**Blocks:** nothing

---


### CH-9: A contrastive correct/incorrect-prompt logprob readout beats free length+logprob OOF AUROC
**Priority:** MEDIUM
**Motivated by:** 2402.11651 + CF-1
**Test:** Re-score cached MATH-500 generations under "generate a correct solution" vs "generate an incorrect solution" prefixes on the shipped small models; fit the OOF logistic on Delta = logprob(correct) - logprob(incorrect); compare AUROC to free baselines (0.810/0.844/0.838). Est ~30min CPU (no training, no new data).
**Requires:** CPU; shipped SmolLM2/Gemma/OLMo models + cached generations.
**Would change:** On confirm, CH-1 gains a concrete cheap readout that beats the free gate; on reject, CF-1's "most generalizing zero-cost readout" claim is reinforced against the prompt-conditioning family.
**Blocks:** nothing

### CH-10: Negative-aware training of the base (not just base-swap) raises the deployment ceiling
**Priority:** LOW
**Motivated by:** 2402.11651 + CF-8
**Test:** NAT-train vs positives-only-SFT a domain-specialized small base on MATH trajectories; compare base accuracy and the free-gate/cascade ceiling each supports. Est ~1 H100 day.
**Requires:** GPU (4×A100-class), SmolLM2-1.7B or Qwen2.5-Math, fresh trajectory generation.
**Would change:** On confirm, CF-8's deployment recipe must add a training-side lever beyond base-swap; on reject, base-swap is reaffirmed as the dominant lever.
**Blocks:** nothing

---


### CH-11: An observability-proxy-conditioned (warrant) bound restores cross-domain certificate validity
**Priority:** HIGH
**Motivated by:** 2601.00138 + CF-5
**Test:** Add an evidence proxy (prompt length, n_gen_tokens, retrieval/context size) as a conditioning term in the split-conformal cross-domain procedure (warrant bound p <= zeta_hat(e)+eps); re-run MATH->BBH at eps=0.2 and check whether validity exceeds 0.0. Reuses cached cross-domain scores + pinned arrays; ~20-40min CPU.
**Requires:** CPU, no new model; existing cross-domain score arrays and `certify_cross_domain()`.
**Would change:** On confirm, CF-5 ("infeasible with any light head") is too strong — the wall was missing evidence-conditioning, and CH-4 gains a concrete light-head recipe. On reject, CF-5 is reinforced as a property of the signal, not the conditioning.
**Blocks:** CH-4

### CH-12: The free gate's generalization is bounded to covariate/family/scale/domain shift and breaks under information-removal shift
**Priority:** HIGH
**Motivated by:** 2601.00138 + CF-1
**Test:** Construct an information-removal axis (truncate MATH context / drop reasoning scaffold / shrink few-shot) holding the task fixed; measure free-gate, length_only, and logprob_only OOF AUROC and fixed-threshold conditional risk vs the pins (0.810/0.844/0.838). 1-2 days local CPU for fresh degraded generations.
**Requires:** CPU, a 1.5-2B instruct model, fresh generations under degraded prompts (or cached if a truncation sweep already exists).
**Would change:** On confirm (AUROC collapses under information removal but length_only holds), CF-1's "most generalizing" is scoped to tested axes and the deployment recipe must add an observability monitor. On reject, CF-1's generalization claim is strengthened against a new, harder shift type.
**Blocks:** nothing

---


### CH-13: A lexical TF-IDF n-gram readout of the prompt beats the preflight length gate (0.71)
**Priority:** HIGH
**Motivated by:** 2306.03423 + CF-7
**Test:** Fit TF-IDF (1-3 gram) logreg on MATH-500/BBH prompt strings to predict correctness, OOF StratifiedKFold(5); compare AUROC to pinned prompt_length_only 0.7056. ~30min CPU.
**Requires:** CPU, scikit-learn, raw prompt strings (need to recover from gate cache; not in pinned_meta.json).
**Would change:** Confirm -> CF-7 reopened, content-aware preflight gate becomes the new CH-2 baseline; reject -> CF-7's length ceiling hardened, lexical content confirmed inert pre-generation.
**Blocks:** CH-2
```

---

## Historical / abandoned

_New CH-N blocks promoted from triage briefs are inserted directly above this
heading by `research-graph/promote_brief.py` (it is the load-bearing insertion
anchor). Hypotheses that have been refuted, mooted, or superseded are moved down
here with a one-line disposition so the live queue above stays current._

_(none yet)_
