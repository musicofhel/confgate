# Triage brief — 2406.18665 — RouteLLM: Learning to Route LLMs with Preference Data

Source: https://arxiv.org/abs/2406.18665
Triaged: 2026-06-14

## Refutations

1. **CF-3 (gate-ordered cascade dominates at matched cost).** RouteLLM trains a
   learned router on preference data that, at the same call budget, claims to beat
   a fixed quality threshold. If a learned router beats our gate-ordered cascade's
   +3.38pp on the same MATH-500 split at matched cost, CF-3's "dominates" claim is
   refuted. Fires via: train their matrix-factorization router on (prompt → which
   tier) and compare the answered-accuracy/cost frontier head-to-head.
2. **CH-3 (a routing policy beats gate-ordered cascade).** This paper is the
   canonical CH-3 challenger — its win would *confirm* CH-3 and thereby refute the
   CF-3 finding it negates. Falsifiable by the same head-to-head.
3. **CF-1 (free length+logprob is the most generalizing readout).** RouteLLM's
   router consumes only the prompt (pre-generation), so if its prompt-only score
   out-AUROCs free length+logprob on a held-out family, CF-1's "most generalizing"
   superlative weakens. Fires via: score their router as a binary correctness gate
   and compare OOF AUROC on SmolLM2 / Gemma / OLMo-2.

## Direct connections to CF-N / CH-N

- **CF-3 / CH-3** — RouteLLM's win-rate-vs-cost curve is exactly the matched-cost
  frontier CF-3 measures (cascade +3.38pp vs hull, p=0.0025). Direct competitor.
- **CF-7** — their router is a pre-generation signal, the same regime as the
  preflight prompt-length gate (~0.706 OOF); a prompt-only router that clears 0.71
  would improve CF-7.

## Methodologies extracted

- **Matrix-factorization router** — learns a bilinear (prompt, model) preference
  score from Chatbot-Arena battles; routes to the strong model above a threshold.
  *Replication cost*: 30min CPU on cached prompt embeddings.
  *We'd plausibly run this*: yes — it's a drop-in alternative gate for the cascade.
- **BERT-classifier router** — fine-tuned encoder predicting win probability.
  *Replication cost*: H100 hours (fine-tune).
  *We'd plausibly run this*: no — GPU, out of MVP scope.

## Approaches & framings

- Recasts confidence routing as a *preference-learning* problem over model pairs
  rather than a calibration problem — orthogonal lens to our correctness-gate framing.

## Datasets & benchmarks

- **Chatbot Arena preference data** — ~55k human battles, public (HF). Applicable?
  partially — pairwise preferences, not MATH correctness labels; would need adaptation.
- **MT-Bench / MMLU eval** — standard, HF. Applicable? yes — overlaps our held-out eval style.

## Implementation details worth capturing

- Router augmentation with an LLM judge to densify sparse preference labels.
- Threshold calibration is done post-hoc on a held-out split — same protocol as our cascade.

## Replicable intermediates

- Score RouteLLM's released router checkpoint as a binary gate over our pinned
  MATH-500 split and compare AUROC against the free-gate anchor (0.845 in-domain).

## Cross-paper signals

none worth flagging

## Proposed FutureExperiments

```yaml
- id: CG-FE57
  pathway: CG
  description: "Train RouteLLM's matrix-factorization router on cached prompt embeddings and benchmark its answered-accuracy/cost frontier against the gate-ordered cascade at matched budget."
  rationale: "Directly tests CH-3 against CF-3 — the canonical learned-router challenger to the free cascade."
  trigger: "RouteLLM reports matched-cost wins over fixed-threshold routing."
  status: READY
  priority: HIGH
  roi: 8
  cost: "30min CPU"
  depends-on: [CF-3]
  would-update: [CF-3]
  triggered-by: ["2406.18665"]
  relies-on: []
- id: CG-FE58
  pathway: CG
  description: "Score the released RouteLLM router as a pre-generation correctness gate and compare OOF AUROC against free length+logprob on SmolLM2/Gemma/OLMo-2."
  rationale: "A prompt-only router beating 0.71 would improve CF-7 and dent CF-1's generalization superlative."
  trigger: "Router consumes only the prompt — a pre-generation signal."
  status: READY
  priority: MEDIUM
  roi: 6
  cost: "20min CPU"
  depends-on: [CF-1, CF-7]
  would-update: [CF-7]
  triggered-by: ["2406.18665"]
  relies-on: []
```

## Proposed HYPOTHESES.md additions

### CH-57: A preference-learned router beats the gate-ordered cascade at matched cost
**Priority:** HIGH
**Motivated by:** 2406.18665 + CF-3
**Test:** Train RouteLLM matrix-factorization router on cached embeddings; compare cost/accuracy frontier vs cascade on MATH-500. ~30min CPU.
**Requires:** CPU, cached prompt embeddings, released RouteLLM router.
**Would change:** Confirms CH-3 / refutes CF-3 "dominates" if it wins; else hardens CF-3.
**Blocks:** nothing

## Proposed PAPER_INDEX.md classification

## 2406.18665 — RouteLLM: Learning to Route LLMs with Preference Data (Ong et al., 2024)

**Relevance:** The canonical learned-router challenger to CF-3 / CH-3 — routes
between a weak and strong model using a preference-trained score at matched cost.

**Key claim we tested:** A learned router beats fixed-threshold routing on the
cost/quality frontier.

**Our result:** **TO TEST** — head-to-head against the gate-ordered cascade not yet run.

**Related experiments:** CG-FE57, CG-FE58, CH-57

**Status:** TO TEST

## New claims

none

## Sources consulted

- ~/confgate/FINDINGS.md — read CF-3 body to confirm the +3.38pp matched-cost anchor.
