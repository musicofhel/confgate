# FINDINGS.md — confgate success factors (CF-N)

The **success factors** the free confidence gate ships on. Every finding is a
testable claim, stated with its pinned evidence. These are the things a swept
paper must *influence* to be relevant. All numbers are read **verbatim** from
`confgate/data/pinned_meta.json` (SPEC v6 pinned + v7 package + v8 frontier) —
never re-state a number that is not in that file.

**Strength key.**
- **STRONG** — ≥ 3 models/families or benchmarks, controls run, null rejected.
- **MODERATE** — 1–2 models, at least one control passed, not fully replicated.
- **PRELIMINARY** — observed but not yet controlled.

**Numbering continues monotonically. Next ID: CF-9.**

---

### CF-1: The free (n_gen_tokens, mean_logprob) logistic gate is the most generalizing zero-cost correctness readout

**Claim.** A logistic regression on two activation-free scalars — generation
length and mean token logprob — predicts answer correctness with the best
held-out generalization of any readout tested, beating prefill-DoM and matching
or exceeding far more expensive probes.

**Strength:** STRONG (3 held-out families + in-domain LOCO/cross-scale).

**Evidence:** OOF AUROC (StratifiedKFold-5) on three held-out families:
SmolLM2-1.7B 0.810, Gemma-2-2b-it 0.844, OLMo-2-1B 0.838 (all T5_pass_0.70 = true).
In-domain Qwen2.5-1.5B: T1 LOCO 0.845, T3 cross-scale 0.865. Source:
`pinned_meta.json` anchors `t5_heldout_oof`, `in_domain_qwen1.5b`.

**Controls passed:**
- Held-out across three architecture families (near/Llama, far/Gemma, far/OLMo-2).
- Cross-scale within Qwen (1.5B→7B) holds (0.865).
- Generalizes better than activation-based prefill-DoM (the v6 headline).

**Controls not yet run:**
- A zero/low-cost readout that beats it OOF on held-out families (CH-1).
- Families further from the math/instruct cluster than OLMo-2.

**Strongest counterargument:** Length and logprob may be proxies for task
difficulty rather than calibration signal, so the gate could be exploiting a
benchmark-specific correctness-length coupling that won't hold on free-form
generation.

**Would be overturned by:** A held-out family where free length+logprob OOF
AUROC drops below the 0.70 T5 bar while a cheap alternative clears it.

### CF-2: Which scalar carries the gate is family-dependent — pin both

**Claim.** The relative contribution of length vs logprob to the free gate is
not universal; some families ride on length alone, others need both. The shipped
gate must therefore pin both scalars rather than a single canonical one.

**Strength:** MODERATE (3 families, mechanism is descriptive).

**Evidence:** SmolLM2 length-only 0.781 ≈ free 0.810 while logprob-only 0.517
(≈chance) → length carries. Gemma length-only 0.783, logprob-only 0.756 → both
carry. OLMo-2 length-only 0.816 ≈ free 0.838, logprob-only 0.654 → length-led.
Source: `pinned_meta.json` anchor `t5_heldout_oof.*.which_scalar_carries`.

**Controls passed:**
- Single-scalar ablations run per family (length-only, logprob-only AUROC).
- Pattern is consistent within each family across the OOF folds.

**Controls not yet run:**
- Whether a learned per-family scalar weighting beats pin-both at matched cost.

**Strongest counterargument:** Logprob calibration is tokenizer- and
temperature-sensitive; the family dependence may reflect decoding/tokenizer
differences rather than an intrinsic signal split.

**Would be overturned by:** A family where neither length-only nor both-scalar
fits generalize, forcing a third scalar.

### CF-3: The gate-ordered cascade dominates introspection and self-consistency at matched cost

**Claim.** Routing by the free gate (keep cheap-model answers above threshold,
escalate the rest) beats the accuracy/cost hull of self-consistency at the same
budget.

**Strength:** STRONG (significant vs hull; beats K=8).

**Evidence:** HYBRID gate cascade is +3.38pp over the hull (boot SE 0.96pp,
significant); best point pct_kept 0.30 → accuracy 0.692 @ cost_rel 0.76 vs hull
0.658. Beats self-consistency K=8 (7B 0.732 vs 0.554). Source: `pinned_meta.json`
anchor `cascade`. (Note: the +3.38pp anchor used the v6 HYBRID gate; the shipped
frontier is the activation-free FreeGate.)

**Controls passed:**
- Matched-cost comparison against the self-consistency Pareto hull.
- Bootstrap significance on the gap.

**Controls not yet run:**
- A routing/cascade policy that beats gate-ordering at matched cost (CH-3).

**Strongest counterargument:** The +3.38pp anchor is the HYBRID (activation-
using) gate; the shipped activation-free gate's matched-cost margin over the hull
is what actually deploys and may be smaller.

**Would be overturned by:** A learned router or self-consistency variant that
clears the same cost budget at higher accuracy than gate-ordering.

### CF-4: Cross-scale zero-shot conformal certificates are valid

**Claim.** A split-conformal certificate fit on a small model transfers
zero-shot to a larger model in the same domain with formal validity.

**Strength:** MODERATE (one scale pair, one domain).

**Evidence:** MATH 1.5B→7B at ε=0.2: k=0 feasible_frac 1.0, validity 1.0, mean
coverage 0.60. k-label recalibration is feasibility-restoring only past k≥32,
never coverage-improving. Source: `pinned_meta.json`
anchor `conformal.cross_scale_math1.5b_to_7b_eps0.2`.

**Controls passed:**
- Validity measured over R=200 splits at the target risk ε=0.2, δ=0.1.
- k-budget sweep (0/8/16/32/64) confirms k=0 is the supported certificate.

**Controls not yet run:**
- More than one (scale pair × domain) combination.

**Strongest counterargument:** 0.60 coverage at validity 1.0 means the cert
abstains on 40% — a high-abstention regime that may not be useful in deployment.

**Would be overturned by:** A scale pair where the zero-shot cert's empirical
risk exceeds ε.

### CF-5: Cross-domain conformal certificates are infeasible with any light head

**Claim.** No light recalibration head delivers a valid cross-domain certificate
(MATH→BBH); the wall is fundamental, not a tuning failure. `certify_cross_domain()`
refuses by design.

**Strength:** STRONG (validity 0.0 ∀ feasible k; corroborated by the conformal sweep).

**Evidence:** MATH→BBH at ε=0.2: validity 0.0 at every feasible k (k=0 cov 0.704
but validity 0.0; k=32 validity 0.0; k=64 validity 0.0). Source: `pinned_meta.json`
anchor `conformal.cross_domain_math_to_bbh_eps0.2`; verdict string
"cross-domain certificates are infeasible with any light head".

**Controls passed:**
- Static + weighted + online-ACI + Mondrian all fail validity at ε=0.2 (C1 sweep).
- Failure persists under a shuffled stationary control (distributional hardness,
  not drift — C2).

**Controls not yet run:**
- A heavier (non-light) adaptation that still respects the matched-cost budget (CH-4).

**Strongest counterargument:** The wall is measured at ε=0.2 with BBH base
accuracy 0.241; a different target risk or a higher-accuracy target task might
admit a feasible cert, so "infeasible" is ε- and task-conditioned.

**Would be overturned by:** A light head delivering validity ≥ 1−δ cross-domain
at a deployment-relevant ε.

### CF-6: In-domain Mondrian group-conditional certificates are valid but low-coverage

**Claim.** Group-conditional (Mondrian) split-conformal certs are valid for
high-accuracy in-domain MATH categories, but at very low coverage and only with
a per-group label budget; marginal CP hides a large cross-category coverage gap.

**Strength:** MODERATE (2 certifiable categories of 7).

**Evidence:** algebra validity 1.0 (k=64, cov 0.0053), prealgebra validity 1.0
(k=32, cov 0.0535); marginal coverage gap 0.383 across categories, 2/7 categories
over budget. Source: `pinned_meta.json`
anchor `conformal.group_conditional_in_domain_math_eps0.2`. Shipped as
`confgate.certify_grouped`.

**Controls passed:**
- 5-fold OOF, R=200, per-group validity measured.
- Marginal-vs-group coverage gap quantified (0.383).

**Controls not yet run:**
- Group-conditional / adaptive conformal that raises in-domain coverage (CH-6).
- Any cross-domain (BBH) group-conditional cert (does not deliver).

**Strongest counterargument:** Coverage ≤5.4% means the cert fires on a tiny
slice; the "validity 1.0" is over a regime so narrow it may be operationally
negligible.

**Would be overturned by:** A method that raises Mondrian in-domain coverage
materially while holding validity.

### CF-7: The preflight prompt-length-only gate is ~0.71; the prompt-cloud eigenspectrum adds nothing

**Claim.** A pre-generation signal — prompt length alone — predicts correctness
at ~0.71 OOF, and the prompt-cloud eigenspectrum (a richer pre-gen geometry) does
not improve on it.

**Strength:** MODERATE (one arm, refutation is clean).

**Evidence:** prompt-length-only OOF AUROC 0.706; H-E (prompt-cloud) refuted,
Δ −0.0096, p=0.42. Source: `pinned_meta.json` anchor `preflight`. Shipped as
`confgate.preflight`.

**Controls passed:**
- Frozen-fold OOF protocol.
- Direct prompt-cloud vs prompt-length comparison with a p-value (n.s.).

**Controls not yet run:**
- A cheap pre-generation signal that beats prompt-length 0.71 (CH-2).

**Strongest counterargument:** 0.706 is well below the post-generation free gate
(~0.81–0.84); the preflight gate's value is purely the it-runs-before-generation
property, and a stronger pre-gen feature might exist outside the prompt cloud.

**Would be overturned by:** Any cheap pre-generation feature clearing OOF AUROC
materially above 0.706.

### CF-8: Deployment recipe — swap the base to a domain-specialized small model; do NOT use the gate to curate distillation data

**Claim.** The biggest matched-cost lever is swapping the base model for a
domain-specialized small model, not curating training data. Using the gate as a
zero-label distillation-data filter does not beat unfiltered at matched N.

**Strength:** STRONG (base-swap confirmed + curation refuted).

**Evidence:** Qwen2.5-Math-1.5B-Instruct standalone MATH-500 acc 0.74,
+9.2pp vs budget-matched cascade at ¼ cost, free-gate OOF AUROC 0.863 (H-P+H-Q
confirmed). Escalation target Qwen2.5-Math-7B cascade 0.69 (+4.2pp over generic
7B, p=0.0025, H-N confirmed). Curation refuted: gate-filtered 0.494 < unfiltered
0.500 < skyline 0.504 (matched N=3065, H-R refuted). Source: `pinned_meta.json`
keys `v8_frontier.{base_swap_product, pinned_escalation_target,
confidence_curated_distillation_LIMIT}`.

**Controls passed:**
- Matched-N curation comparison incl. length-control and ground-truth skyline.
- Budget-matched cost accounting (token-FLOPs) for the base swap.
- R1-Distill-1.5B refused (intrinsic reasoning length blows the budget).

**Controls not yet run:**
- A better escalation target / base swap that raises the matched-cost ceiling (CH-5).

**Strongest counterargument:** The base-swap win is MATH-specific (Qwen2.5-Math);
MATH-only SFT forgets BBH (base BBH 0.267 → best arm 0.208), so the recipe may
not generalize beyond a single specialized domain.

**Would be overturned by:** A confidence-curated distillation arm beating
unfiltered at matched N, or a generic (non-domain-specialized) base swap matching
Qwen2.5-Math's lift.
