# PAPER_INDEX.md — confgate triaged papers

Papers swept from link-forge, relevance-gated, and triaged, grouped by which
success factor (CF-N) / lever (CH-N) they touch. `promote_brief.py` appends and
updates entries here from each triage brief.

_No papers triaged yet (Phase 0 stub)._

## 2502.02737 — SmolLM2: When Smol Goes Big — Data-Centric Training of a Small Language Model (Ben Allal, Lozhkov, Bakouch et al., HuggingFace, 2025)

**Relevance:** This is the technical report for SmolLM2-1.7B, the base model behind
confgate's pinned SmolLM2 free-gate anchor (OOF AUROC 0.810; length_only 0.781;
logprob_only 0.517). It bears directly on CF-1/CF-2 (the recipe — tokenizer, WSD
schedule, SmolTalk length-control SFT, UltraFeedback DPO — is the hidden variable
behind which scalar carries the gate), CF-8/CH-5 (it is a *generalist* data-centric
recipe that loses to Qwen2.5-1.5B on math, quantifying the gap a domain-specialized
base-swap must close and supplying the open recipe to build one), and CF-3/CH-3 (its
MCF-emergence finding suggests the keep/escalate accuracy gap the cascade monetizes is
a transient of small-model undertraining).

**Key claim we tested:** Data-centric multi-stage curation (FineMath classifier-filter,
annealing-phase math upsampling) produces a SOTA 1.7B base — and, as a side effect,
fixes the base whose free-gate AUROC confgate pins, while length/constraint post-training
reshapes the very signals (n_gen_tokens, logprob) the gate reads.

**Our result:** **CITED ONLY** No confgate experiment has yet measured the
recipe-dependence the paper implies. The four refutations (length-decoupling via
post-training, AUROC-vs-base-capability anti-correlation, classifier-curation reviving the
curation-helps premise, cascade-gap shrink) are real, falsifiable, and cheap, but
unrun — so the paper is logged as the provenance of the SmolLM2 anchor and the trigger
for CG-FE11–208 / CH-7–58, not as a confirmed or contradicted finding.

**Related experiments:** CG-FE11, CG-FE12, CG-FE13, CG-FE14, CH-7, CH-8

**Status:** CITED ONLY

### Methodologies extracted

- **Classifier-based quality filtering (FineWeb-Edu lineage)** — Llama-3.1-70B scores
  pages on a 3-pt then 5-pt scale → train a fastText/StarEncoder classifier on the
  silver labels → keep score≥threshold. The cheap *content-quality* readout that
  refutation #3 pits against the confidence gate as a distillation-curation signal.
  *Replication cost*: classifier inference is CPU-cheap; the LLM-judge labels are the
  cost — but FineMath ships pre-filtered, so we can skip labeling. ~1hr CPU to filter
  a small pool. *We'd plausibly run this*: yes — it is the direct test of CF-8's
  curation clause.
- **Annealing / decay-phase domain upsampling (WSD schedule)** — reserve highest-quality
  math/code (FineMath4+, InfiWebMath3+, AugGSM8K) for the final 10% LR-decay window
  to maximize impact (Blakeney domain-upsampling). The cheapest known lever to *make*
  a domain-specialized small base for the CF-8/CH-5 swap. *Replication cost*: H100-days
  for a real anneal; not local. *We'd plausibly run this*: no (GPU-bound) — capture as
  a recipe, not a runnable.
- **13-gram / 0.6-LCS decontamination against GSM8K, MATH, MMLU** — n-gram + longest-
  common-subsequence overlap test. Directly relevant: confgate evaluates the gate on
  MATH-500; a contaminated base inflates accuracy and *deflates* gate AUROC (fewer
  errors). *Replication cost*: 20min CPU over our eval split. *We'd plausibly run
  this*: yes — a cheap integrity check on the MATH-500 gate eval.
- **MCF vs cloze likelihood evaluation** — answer by emitting the letter ('A'..'D')
  vs scoring per-option likelihood. The two are different confidence readouts; SmolLM2
  finds long training flips small models from cloze-only to MCF-capable. *Replication
  cost*: 20min CPU, eval-harness toggle. *We'd plausibly run this*: yes — a cheap probe
  of whether logprob_only's collapse for SmolLM2 is a readout-formulation artifact.
- **DPO (UltraFeedback, β=0.5, lr 1e-6, 2 epochs)** — preference learning known to
  reshape logprob calibration. The likely culprit behind SmolLM2's logprob_only 0.517
  vs Gemma's 0.756. *Replication cost*: comparison is free if base vs instruct logprobs
  are cached. *We'd plausibly run this*: yes — base-vs-instruct logprob-AUROC delta.
- **ArmoRM reward scoring + gte-large embedding dedup** — cheap quality/novelty readouts
  used for SFT data selection. Candidate auxiliary signals for CH-1 stacking.
  *Replication cost*: ArmoRM is a GPU reward model; gte-large embeds on CPU. Mixed.
  *We'd plausibly run this*: no — heavier than the free gate, violates the zero-cost framing.

### Approaches & framings

- **Data quality as the dominant small-model lever** — reframes "raise the matched-cost
  ceiling" (CH-5) from an inference-time routing problem into a pretraining-data
  problem; intersects CF-8 by arguing the base-swap target is *manufacturable*, not just
  selectable.
- **Emergent capability from extended (anti-Chinchilla) training** — small models acquire
  large-model abilities (MCF) after ~10T tokens; intersects CF-3/CH-3 by suggesting the
  keep/escalate gap the cascade monetizes is a transient of undertraining.
- **Online multi-stage mixing instead of from-scratch sweeps** — performance-driven mid-run
  rebalancing as a cheaper search; tangential to confgate but a framing for how a
  base-swap candidate gets tuned without N full runs.

### Datasets & benchmarks

- **FineMath (FineMath4+ 10B / FineMath3+ 34B tokens)** — HF (HuggingFaceTB/finemath),
  open, decontaminated vs GSM8K/MATH/MMLU. Applicable? yes — fine-tune/curation pool for
  the CF-8 curation-vs-gate test and for building a math-specialized small base.
- **Stack-Edu (~125B tokens, 15 languages)** — HF, open. Applicable? no — code domain,
  outside the MATH-500/BBH gate regime.
- **SmolTalk / smol-smoltalk (incl. Smol-Constraint, Smol-Rewrite, Smol-Summarization)** —
  HF, open. Applicable? yes — the length-control datasets central to refutation #1; the
  test set for whether post-training decouples length from difficulty.
- **MATH / GSM8K / MMLU-STEM / MMLU-Pro / AugGSM8K** — standard, open. Applicable? yes —
  MATH overlaps confgate's MATH-500; the decontamination + base-accuracy cross-checks ride
  on these.
- **HELMET / NIAH long-context, IFEval, MT-Bench, OpenRewrite-Eval** — open. Applicable?
  no — instruction/long-context evals, off the confidence-gate axis.

### Implementation details worth capturing

- Architecture: 1.7B, Llama-2 layout; 135M/360M variants add Grouped-Query Attention.
  Tokenizer 49,152 vocab (SmolLM tokenizer), trained 70% FW-Edu / 15% Cosmopedia-v2 /
  8% OWM / 5% StarCoderData / 2% StackOverflow.
- Pretraining: 11T tokens, 256×H100, nanotron; AdamW (0.9, 0.95); WSD schedule, 2k-step
  warmup, peak LR 5e-4, decay-to-zero over final 10% of steps.
- Four stages: web-only (0–6T) → +code/OWM (6–8T) → +InfiMM-WebMath/Stack-Edu, FW/DCLM
  flipped to 40/60 (8–10T) → decay-phase FineMath4+/InfiWebMath3+/AugGSM8K upsample
  (10–11T). Math content peaks at 14% only in the final decay window.
- Context extension: 2k→8k via RoPE θ=130k on an intermediate stage-4 checkpoint, 40%
  long-doc mixture (Dolma books / FW-Edu / DCLM).
- SFT: 2 epochs, batch 128, seqlen 8192, LR 3e-4. DPO: UltraFeedback, 2 epochs, LR 1e-6,
  β=0.5, batch 128, seqlen 1024.
- Loss spike in stage 3 persisted after data-skip rewind; cause undetermined — a recipe
  gotcha.
- Code/data released: nanotron, datatrove, lighteval; FineMath/Stack-Edu/SmolTalk on HF.

### Replicable intermediates

- **`confgate` free-gate eval on base vs Instruct SmolLM2-1.7B** — run the shipped gate
  (length_only + logprob_only + free) on cached MATH-500 generations from both checkpoints;
  compare length_only AUROC delta against the pinned 0.781. The direct test of refutation #1.
- **Base-accuracy vs gate-AUROC scatter from pinned_meta.json** — we already hold free /
  length_only / logprob_only AUROC for SmolLM2 (0.810), Gemma-2-2B (0.844), OLMo-2-1B
  (0.838); join against published GSM8K/MATH accuracy for each to test refutation #2's
  "AUROC falls as base accuracy rises" with zero new compute (the AUROC side is pinned;
  only the accuracy axis is external).
- **13-gram decontamination pass over the MATH-500 gate split** — cheap integrity check
  that the pinned 0.810 was not measured on contaminated items.
- None of these *change* a pinned number — they are external-validity cross-checks on the
  existing anchors.

### Cross-paper signals

- 2406.03476 — NOT in graph; recommend admission. Blakeney "Does your data spark joy?
  domain upsampling at end of training" — the decay-phase upsampling method SmolLM2 uses;
  the runnable recipe for building a CF-8/CH-5 base-swap candidate.
- 2402.03300 — NOT in graph; recommend admission. DeepSeekMath — the domain-specialized
  math-small-model archetype CF-8 invokes; InfiMM-WebMath is benchmarked against it.
- 2408.10914 — NOT in graph; recommend admission (weaker). Aryabumi "To code, or not to
  code?" — code-in-pretraining improves reasoning; bears on whether the keep-model
  accuracy gap (CF-3) is a data-mix artifact.
- 2305.16264 — NOT in graph; recommend admission (weaker). Muennighoff "Scaling
  data-constrained LMs" — the 4–5 epoch repetition ceiling SmolLM2 respects; context for
  base-swap data budgets.
- Qwen2.5 / Gemma-2 / OLMo-2 / Llama-3.2 technical reports — the base models confgate
  actually pins (Gemma-2-2B 0.844, OLMo-2-1B 0.838) trace to these; worth admitting the
  Qwen2.5 and OLMo-2 reports if a base-provenance audit is ever run. IDs not asserted here
  to avoid mis-citation.

## 2402.11651 — Learning From Failure: Integrating Negative Examples when Fine-tuning Large Language Models as Agents (Wang, Li, Han, Zhang, Baldwin, 2024)

**Relevance:** Adjacent. The paper's subject is agent fine-tuning data efficiency, not confidence
estimation, so it does not directly test any CF claim. It touches confgate at three points: CF-8
(it is a distillation/trajectory-data-usage method for small-model agents — "don't discard the
negatives" mirrors confgate's "don't curate"), CF-1/CH-1 (its correct/incorrect prefix conditioning
seeds a candidate contrastive-logprob readout), and CF-3/CH-3 (prompt-contrast as a cheap
introspection/routing signal).

**Key claim we tested:** That a model's correct-vs-incorrect knowledge, exposed by NAT-style prefix
conditioning, can be turned into a cheap correctness readout / routing signal that beats the free
length+logprob gate — and that negative-aware training of the base raises the deployment ceiling
CF-8 attributes to base-swap.

**Our result:** **CITED ONLY** Not yet tested. The paper itself makes no confidence/calibration
claim against ours; the connection is the contrastive-readout and anti-curation ideas it unlocks,
captured as CG-FE15/153/154 and CH-9/58. The zero-training contrastive-logprob check (CG-FE15)
is the cheapest path to upgrading this to a real test.

**Related experiments:** CG-FE15, CG-FE16, CG-FE17, CH-9, CH-10

**Status:** CITED ONLY

### Methodologies extracted

- **Negative-aware reformatting (NAT prefix/suffix)** — append "Please generate a solution that
  correctly/incorrectly answers the question" to label each training trajectory; at inference use
  only the positive prefix.
  *Replication cost*: fine-tuning a small base — "H100 day" (4×A100, DeepSpeed ZeRO-3, 2 epochs).
  The *zero-training* re-scoring variant (apply both prefixes to cached generations) is "~30min CPU".
  *We'd plausibly run this*: yes — the zero-training contrastive-logprob readout is a direct CH-1 shot.
- **Answer-match trajectory labeling** — label a trajectory positive/negative by comparing its
  predicted answer to ground truth (no learned verifier).
  *Replication cost*: trivial, "minutes CPU" given cached generations + gold answers.
  *We'd plausibly run this*: yes — it is exactly how confgate's correctness labels are already formed.
- **Multi-temperature trajectory sampling (0.2 / 0.5 / 0.7)** — generate 3× per seed question at
  different temperatures to diversify positive/negative yield.
  *Replication cost*: "GPU hours" for fresh generation; free if reusing cached MATH-500 generations.
  *We'd plausibly run this*: no — confgate's generations are pinned single-temperature; not needed for the gate.
- **Negative-quality stratification (NAT-2)** — split negatives into 2 classes by source quality
  (GPT-3.5 high vs fine-tuned-7B low) and use a distinct prefix per class.
  *Replication cost*: "minutes CPU" once a quality proxy exists.
  *We'd plausibly run this*: no — interesting but orthogonal to the gate; parks as a CH idea.
- **ReAct trajectory framework + SymPy calculator tool** — Thought/Action/Observation loop with a
  SymPy-backed calculator for math and a Serper+MPNet/DPR re-ranked search tool for QA.
  *Replication cost*: "hours" to wire; tooling not needed for confgate's single-shot gate.
  *We'd plausibly run this*: no — confgate is single-turn, not tool-using agents.

### Approaches & framings

- **"Failure carries signal" framing** — the central reframe: a *wrong* trajectory is not noise to be
  filtered but a labeled contrast example. Intersects CF-8: confgate's "don't curate distillation
  data" and NAT's "don't discard negatives" are two faces of the same anti-aggressive-filtering claim.
- **Conditioning-as-control** — steering generation correctness by a natural-language prefix rather
  than by a scalar head. Intersects CH-1: suggests a readout that lives in the model's own
  instruction-conditioned likelihood rather than in length/logprob features.
- **Data-quantity/quality trade-off curves** — NAT shows negative-sample benefit plateaus (~11k) and
  diminishes as positives grow; a framing for "how much labeled contrast is worth it," relevant if
  confgate ever trains a light head on contrast features.

### Datasets & benchmarks

- **GSM8K** — ~8.5k grade-school math, HF, open. Applicable? yes — math-reasoning, adjacent to MATH-500;
  usable as an out-of-distribution family for gate generalization tests.
- **ASDiv / SVAMP / MultiArith** — small arithmetic-word-problem test sets, HF, open. Applicable? yes —
  cheap extra math families to probe free-gate cross-family AUROC.
- **HotpotQA** — multi-hop QA, HF, open. Applicable? no — retrieval-QA, off the math/BBH small-model regime.
- **StrategyQA** — implicit-reasoning boolean QA, HF, open. Applicable? no — not the confgate regime.

### Implementation details worth capturing

- Base models: **LLaMA-2-Chat 7B / 13B**; 2 epochs, batch size 64, cosine schedule, 3% warmup,
  max LR 5e-5, 4×A100, DeepSpeed ZeRO-3. Loss computed only on model-generated tokens (chat-style masking).
- Trajectory data from **GPT-3.5-1106** at temps 0.2/0.5/0.7 (not GPT-4 — cost).
- Inference always uses the **positive** prefix; negatives are training-only.
- Code + data: https://github.com/Reason-Wang/NAT (the prompts used are noted to be slightly more
  complex than the paper's simplified "correct/incorrect" strings).
- Reported NAT gains: +8.74% (7B, 2k pos) down to +0.52% (13B, 5k pos) on math; +8pp on StrategyQA.

### Replicable intermediates

- **Zero-training contrastive-logprob cross-check** — re-score the cached MATH-500 generations under a
  "generate a correct solution" prefix and an "generate an incorrect solution" prefix using the shipped
  small models; compute Δ = mean_logprob(correct) − mean_logprob(incorrect) per generation; feed Δ into
  the same OOF logistic protocol (`phase3_heldout.py::eval_free_baseline` analog) and compare AUROC to
  the pinned free baselines (0.810 / 0.844 / 0.838). This is the smallest direct test of Refutation #2.
- **Anti-curation sanity check against CF-8** — no fine-tuning needed: confirm from `pinned_meta.json`
  that the free gate's AUROC does not depend on having filtered training data (it is OOF on the base's
  own generations), which is the confgate-side analog of NAT's "negatives aren't poison" claim.

### Cross-paper signals

- 2210.03629 — NOT in graph; recommend admission only if confgate ever does tool-use cascades. ReAct
  (the trajectory format NAT builds on). Weak relevance to single-shot gate.
- 2303.11366 — NOT in graph; recommend admission. Reflexion (Shinn et al.) — verbal self-reflection /
  introspection from failure; directly relevant to CF-3's introspection-vs-gate comparison.
- 2303.17651 — NOT in graph; recommend admission. Self-Refine (Madaan et al.) — iterative self-correction;
  another introspection baseline confgate's CF-3 implicitly competes with.
- 2311.05657 — NOT in graph; low priority. Lumos (agent-tuning baseline NAT compares to in Table 1).

## 2601.00138 — Explicit Abstention Knobs for Predictable Reliability in Video Question Answering (Jorge Ortiz, 2025)

**Relevance:** Direct external stress test of the same construct confgate ships — a confidence scalar swept into a risk-coverage / abstention curve (CF-1, CF-3) — including the logprob-derived readout (CF-2). It isolates an *information-removal* shift axis (18->6 video frames) orthogonal to confgate's tested family/scale/domain shifts, and offers a warrant bound `p <= zeta(e)+eps` as a candidate mechanism and light-head fix for the cross-domain certificate wall (CF-5, CH-4).

**Key claim we tested:** A confidence gate (self-reported OR logprob-derived) gives clean in-distribution risk-coverage but is non-epistemic under evidence loss — confidence, and especially logprob `p_max`, fails to contract when information is removed (logprob `p_max` 0.870->0.876 *up* under a 67% evidence cut).

**Our result:** **CITED ONLY** Cross-modality (video VLM, Gemini, multiple-choice) so no direct replication against MATH-500/BBH yet; the paper supplies a borrowable information-removal stress protocol and an observability-conditioning idea that motivate four FEs (CG-FE18–64) and two hypotheses (CH-11, CH-12). Reclassify to TO TEST once CG-FE18 runs.

**Related experiments:** CG-FE18, CG-FE19, CG-FE20, CG-FE21, CH-11, CH-12

**Status:** CITED ONLY

### Methodologies extracted

- **System-level abstention (threshold ε on a confidence scalar, model's own `abstain` flag logged but not used for gating)** — decouples the gate from the model's alignment-driven refusal; exactly confgate's posture (gate is the system, not the model's introspection).
  *Replication cost*: trivial — confgate already does this.
  *We'd plausibly run this*: yes — it is the existing free-gate sweep; cited only for methodological alignment.

- **Evidence-degradation as a controlled intervention (frame count 18→6; temporal early-half/late-half ablation; JPEG-quality control arm).** A clean recipe for an *information-removal* stress axis distinct from covariate/domain shift, with a paired control (compression) that isolates information content from surface corruption.
  *Replication cost*: 1–2 days local — needs fresh generations under truncated/degraded text prompts on MATH-500; no GPU if reusing a 1.5–2B model on CPU or cached if generations exist.
  *We'd plausibly run this*: yes — this is the core borrowable method; it gives confgate a 4th shift axis to test CF-1's generalization claim.

- **Logprob-derived confidence triplet: renormalized-softmax `p_max`, margin (`p_max − p_second`), normalized entropy `H(p)/log K`, computed over only the answer-option tokens from the top-20 logprobs.** A cheap, decoder-level confidence readout that needs no extra forward pass.
  *Replication cost*: 20min CPU — confgate already extracts logprobs; margin + normalized entropy are two new scalars over existing data.
  *We'd plausibly run this*: yes — margin/entropy are unexplored confgate features; could feed CH-1 (beat free-gate AUROC) and CF-2 (which scalar carries).

- **Observability-sensitivity diagnostic: `Pr(conf ≥ τ | ζ̂=0)` vs `Pr(conf ≥ τ | ζ̂=1)` plus quartile/IQR comparison of the confidence distribution across evidence regimes.** A one-number test of whether a confidence signal contracts under shift.
  *Replication cost*: 20min CPU on existing score arrays.
  *We'd plausibly run this*: yes — directly applicable to confgate's cross-domain (MATH vs BBH) score arrays to *quantify* CF-5's failure rather than just refuse.

- **Threshold-transfer test (solve ε* on source regime by interpolation, evaluate same ε* on target regime, both directions).** Quantifies how badly an in-distribution threshold mis-transfers under shift.
  *Replication cost*: 20min CPU on existing risk-coverage tables.
  *We'd plausibly run this*: yes — gives confgate a deployment-honest number for "free-gate threshold tuned on MATH, applied to BBH."

- **Warrant constraint `p ≤ ζ(e) + ε` with ζ(e) = Bayes-optimal predictability given evidence view e (proposed, not implemented).** A conformal-adjacent per-instance bound conditioned on observability rather than marginal exchangeability.
  *Replication cost*: needs a ζ estimator — research-grade; an observability-proxy lower bound is the cheap first cut.
  *We'd plausibly run this*: yes (the cheap proxy version) — candidate light-head fix for CH-4 cross-domain validity.

### Approaches & framings

- **Information-removal shift vs covariate/corruption/domain shift.** Reframes "distribution shift" as an intervention on *observability* (how much the evidence can support the claim) rather than on the input marginal — a fourth axis orthogonal to confgate's tested family/scale/domain shifts and a direct probe of CF-1's "generalizing" claim.
- **Mechanistic control ≠ epistemic validity.** A confidence knob can produce a clean, monotone, well-calibrated (ECE 0.018) in-distribution risk-coverage curve and *still* be non-epistemic under shift. This severs "the gate works on the held-out fold" from "the gate is safe under deployment shift" — exactly the gap between confgate's OOF AUROC story and a deployment guarantee.
- **Representational vs behavioral overconfidence.** Because the logprob signal fails *harder* than self-report, the defect is in the model's representation, not the reporting interface — undercutting any "just read the logits instead of asking the model" remedy, which is precisely confgate's logprob component.
- **Warrant as an epistemic contract (vs marginal conformal coverage).** Confidence should be bounded by evidence-conditioned knowability `ζ(e)`, giving a *per-instance* bound where conformal gives only *marginal* coverage — a conceptual route at CF-5/CH-4's cross-domain wall.

### Datasets & benchmarks

- **NExT-QA** — multiple-choice video QA, temporal/causal/descriptive splits; the paper uses 300 frozen validation items (100/type), license CC (academic), accessible (HF / project page). Applicable? no — video VLM modality, not the MATH-500/BBH text small-model regime; useful only as a methodological template, not as data confgate would ingest.

### Implementation details worth capturing

- Gemini 2.0 Flash, **temperature 0** for determinism, max 256 output tokens — confidence read from a structured JSON field (`choice`, `confidence∈[0,1]`, `abstain`, `evidence_span`).
- Logprob path uses a **separate, simpler prompt** (single letter A–E, no JSON) with `response_logprobs=True, logprobs=20`; extract A–E token logprobs from the *first generated token*, assign −100 to any option absent from top-20, then softmax-renormalize over the five options only. Cross-interface *accuracy* is not comparable (different prompts) — only *within-interface deltas across shift* are.
- Statistical-power gate: mark risk-coverage points with `|A_ε| < 50` accepted predictions as NaN and omit (confgate's certify code should adopt the same min-n guard for sweep tables).
- Frozen `item_ids.json` + per-frame SHA256 manifest for exact reproducibility across shift conditions — a clean pattern for confgate's paired in-distribution / degraded runs.
- Compression control (JPEG q85→q30) had ~0pp effect, isolating *information content* from *surface fidelity* — the text analog is "paraphrase/noise the prompt (surface) vs truncate context (information)."

### Replicable intermediates

- **Observability-sensitivity diagnostic on the shipped cross-domain arrays.** Run `Pr(score ≥ τ | domain=BBH)` vs `Pr(score ≥ τ | domain=MATH)` over the free-gate scores behind `conformal.cross_domain_math_to_bbh_eps0.2` — quantifies *how much* the free-gate confidence fails to contract MATH→BBH, turning CF-5's binary "validity 0.0" into a contraction number, using only `pinned_meta.json` + `certify_cross_domain()`.
- **Margin + normalized-entropy scalars over existing generations.** Recompute `p_max − p_second` and `H/log K` from confgate's already-logged option/token logprobs and check their OOF AUROC against the pinned `logprob_only` (0.756 Gemma / 0.517 SmolLM2) — zero new generations, just new readouts.
- **Threshold-transfer number for the free gate.** Solve ε* for a target risk on the MATH risk-coverage table, apply to BBH, report the coverage gap — directly comparable to the paper's Table 6, using confgate's existing sweep CSVs.

### Cross-paper signals

- 2505.15008 — NOT in graph; recommend admission. Heng & Soh, "Know when to abstain: optimal selective classification with likelihood ratios" — Neyman-Pearson optimal acceptance rule (likelihood-ratio test) combining distance-from-training-data with logits, evaluated under covariate shift. Direct CH-1/CH-3 challenger: a principled selection score that could beat the free gate's logistic readout, especially under shift.
- 2512.12844 — NOT in graph; recommend admission. Xu, Guo & Wei, "Selective Conformal Risk Control (SCRC)" — two-stage filter-then-conformalize. Direct CF-3/CF-5/CH-4 relevance: couples selective prediction with conformal risk control, the exact machinery behind confgate's cascade + certificate.
- (Non-arxiv, flag-only) Kamath et al. 2020 "Selective QA under domain shift" and Whitehead et al. 2022 "Reliable VQA: abstain rather than answer incorrectly" — canonical risk-coverage-under-shift priors; worth a citation pointer if confgate writes up the shift-robustness story, but no arxiv id to admit.

## 2306.03423 — I'm Afraid I Can't Do That: Predicting Prompt Refusal in Black-Box Generative Language Models (Reuter & Schulze, 2023)

**Relevance:** Touches CF-7 (preflight prompt-side gate), CH-2 (cheap pre-generation signal beats prompt-length 0.71), CF-1 (most-generalizing zero-cost readout), and CF-8 (anti-curation stance). The paper predicts a downstream black-box model behavior (refusal) from prompt text alone using TF-IDF 1-3-gram classifiers, demonstrating a *lexical* pre-generation feature class that confgate's preflight work (length + prompt-cloud eigenspectrum) never tested.

**Key claim we tested:** In confgate terms — a cheap, CPU-only, content-aware text readout of the prompt predicts the model's downstream behavior pre-generation (~76% accuracy from prompt alone), a feature class orthogonal to length and logprob.

**Our result:** **TO TEST** Different target (refusal, not correctness) means no direct claim test; the borrowable hypothesis — lexical n-gram prompt features beat the preflight length-only ceiling 0.7056 and/or add over the free gate — is queued as CG-FE22/52/53 and CH-13. Status is provisional pending those CPU runs.

**Related experiments:** CG-FE22, CG-FE23, CG-FE24, CH-13

**Status:** TO TEST

### Methodologies extracted

- **TF-IDF n-gram (1≤n≤3) + logistic regression / random forest readout** — vectorize prompt text with TF-IDF over uni/bi/tri-grams, fit a linear or tree classifier to predict a downstream binary model behavior. *Replication cost*: ~30min CPU (scikit-learn on MATH-500/BBH prompt strings). *We'd plausibly run this*: yes — it is the cheapest possible content-aware pre-generation readout and directly tests CF-7/CH-2.
- **BERT fine-tune as a behavior-from-text classifier** — fine-tune `bert-base` to predict the same binary from prompt text (paper: 75.9% prompt-only, 96.5% response). *Replication cost*: H100-light but GPU; a few GPU-hours. *We'd plausibly run this*: no — violates the local/CPU-only constraint and the TF-IDF logreg variant captures most of the headline (73.9% LR vs 75.9% BERT, ~2pp gap).
- **Two-stage weak-label bootstrap** — train classifier A on a small hand-labeled set; use A to auto-label a large unlabeled pool; train downstream classifier B on the noisy labels; evaluate B on held-out hand labels. *Replication cost*: ~1hr CPU given a free-gate labeler and an unlabeled prompt pool. *We'd plausibly run this*: yes — it is a clean test of CF-8's anti-curation stance on correctness data.
- **Predictive-n-gram inspection** — rank n-grams by class-discriminativeness (compliance vs refusal) to interpret what drives the prediction. *Replication cost*: trivial, folds into the TF-IDF fit. *We'd plausibly run this*: yes — would tell us *which* lexical features (operators, topic words) carry correctness signal length misses.

### Approaches & framings

- **"Predict the model's downstream behavior from the input text alone, black-box."** This reframes the preflight gate as a *text-classification* problem rather than a *scalar-feature* problem — confgate's CF-7 lives entirely in the scalar (length) and geometric (eigenspectrum) regime and never crosses into lexical text classification. The framing intersects CH-2/CF-7 directly: it says the pre-generation signal space is larger than confgate has searched.
- **Weak supervision / label bootstrapping as a first-class data move.** Treating a cheap classifier's outputs as training labels for a downstream model reframes CF-8's "curation hurts" as one negative datapoint, not a law — intersects CF-8 and the `curation-helps-distillation` premise.

### Datasets & benchmarks

- **Quora Insincere Questions (Kaggle)** — 10,000 auto-labeled prompts (bootstrap training) + 985 hand-labeled (test). Public via Kaggle competition. Applicable? no — it is a toxicity/insincerity corpus, wrong domain for the MATH-500 / BBH correctness regime; only the *method* transfers, not the data.
- **Authors' hand-labeled refusal set (`maxwellreuter/chatgpt-refusals`)** — n=1,706 total (21 NY Post + 700 political-figure + 985 Quora prompts), public on GitHub, no explicit license. Applicable? no — refusal labels, not correctness labels; not the small-model open-weight regime.

### Implementation details worth capturing

- Code + data: https://github.com/maxwellreuter/chatgpt-refusals
- TF-IDF vectorizer configured for n-grams with 1≤n≤3 (uni/bi/tri-grams); same vectorizer used for both response and prompt classifiers.
- Three model families compared (BERT, logistic regression, random forest); the LR variant is within ~2–3pp of BERT on the prompt task (73.9% vs 75.9%) — supports a CPU-only logreg replication with little headline loss.
- Bootstrap split is clean: machine labels → train, hand labels → test (no label leakage between the 985 hand-labeled and the 10k auto-labeled).
- Refusal is detected via shared surface expressions ("cannot", "sorry", "AI language model") — a reminder that the *response* classifier is largely lexical-surface, not semantic.
