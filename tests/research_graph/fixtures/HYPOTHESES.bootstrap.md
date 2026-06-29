# HYPOTHESES.md — confgate levers (CH-N)

The **relevance perimeter**: a swept paper is admitted iff it could plausibly
corroborate/contradict a CF-N **or** inform one of these levers. Each lever is a
concrete way a paper could help **beat the free gate**. Lean inclusive on
admission — a false-positive admit is far cheaper than a false-negative miss.

**Priority key.** HIGH | MEDIUM | LOW | PARKED.

**Numbering continues monotonically. Next ID: CH-7.**

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

## Historical / abandoned

_New CH-N blocks promoted from triage briefs are inserted directly above this
heading by `research-graph/promote_brief.py` (it is the load-bearing insertion
anchor). Hypotheses that have been refuted, mooted, or superseded are moved down
here with a one-line disposition so the live queue above stays current._

_(none yet)_
