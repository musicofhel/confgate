# STATE.md — confgate research-graph

Where the last session left off. Read [`CLAUDE.md`](CLAUDE.md) for the full
orientation and [`../SPEC_TRIAGE_PIPELINE_v1.2.md`](../SPEC_TRIAGE_PIPELINE_v1.2.md)
for the design.

## Status: grouping MVP COMPLETE (Phases 0–4)

The full pipeline — `sweep → admit → triage → promote → group` — is built, tested,
and validated end-to-end against live services on local CPU.

| Phase | What | Merged |
|---|---|---|
| 0 | scaffolding + standalone Neo4j (`:7689`) + two-tier CI | `fbb4277` |
| 1 | `admit.py` pull-model relevance gate + `bridge.py` | `d0b8a66` |
| 2 | `/confgate-triage` skill + shared `brief_parser.py` | `95bbb93` |
| 3 | `promote_brief.py` + premises/query/validate/update/generate | `a567c85` |
| 4 | `research-sweep.yaml` + e2e tracer + docs + live validation | (this PR) |

## Test surface

- `make test` — unit (Docker-free): pytest `-m "not integration"` + ruff. 38 pass.
- `make test-int` — integration (two ephemeral graphs): 8 pass (incl. the e2e).
- `make e2e-dry` — zero-network `sweep→admit→promote→grouped` tracer
  (`tests/research_graph/test_phase4_e2e.py`, marked `integration` + `e2e_dry`).
- `python validate_claims.py` — 12 `cg-*` external anchors, all REGISTERED, exit 0.
- Shipped `confgate/` package + `tests/test_confgate.py` are byte-stable (untouched).

## Live e2e validation (2026-06-14, local CPU)

- **Sweep**: `npx tsx ~/link-forge/scripts/research-sweep.ts confgate` →
  857 records → `~/link-forge/data/research-sweep-confgate-2026-06-14.json`.
- **Admit**: a 6-record diverse slice through `admit.py --from-sweep confgate`
  with the live `claude -p` gate → **5 admitted** across CF-3…CF-8 / CH-2…CH-6;
  the off-topic *Cascade R-CNN* (object detection) was correctly **rejected**.
  link-forge had no matching `:Link` for these new arxiv ids, so embeddings were
  not copied (graceful degrade — expected).
- **Triage + promote**: one paper deep-triaged and promoted (see graph for the
  resulting CG-FE nodes and `NEXT_EXPERIMENTS.md`).

Papers admitted to the dev graph (`:7689`):

| arxiv | levers (tags) | title |
|---|---|---|
| 2305.18404 | CF-4/5/6, CH-4/6 | Conformal Prediction with LLMs for Multi-Choice QA |
| 2306.03423 | CF-7, CH-2 | Predicting Prompt Refusal in Black-Box LMs |
| 2402.11651 | CF-8, CH-5 | Learning From Failure (negative examples in fine-tuning) |
| 2502.02737 | CF-8, CH-5 | SmolLM2: data-centric training of a small LM |
| 2601.00138 | CF-3/5, CH-3/4 | Explicit Abstention Knobs for Predictable Reliability |

## Dev graph contents (`bolt://localhost:7689`)

- `:Finding` CF-1…CF-8 (seeded), `:Premise` ×6 (one REFUTED: `curation-helps-distillation`).
- `:Paper` admitted above + `:Tag` grouping seeds + any `:FutureExperiment` from the promote.
- Inspect: `python query.py grouped` · `python query.py pending` · `python query.py premises`.

## Next session — where to go

**Update 2026-06-16 (promotion DONE):** all 4 deep-triaged briefs are now PROMOTED.
The CG-FE queue is live — `python query.py future CG` shows **24 experiments**, CH
ledger advanced to `Next ID: CH-14`, pending-triage drained to **0**. Promotion
notes: the SmolLM2 + refusal briefs each had one curation-flavoured FE (CG-FE13,
CG-FE24) **born MOOTED** against the refuted `curation-helps-distillation` premise
(working as intended); the 2306.03423 external `cg-reuter-prompt-refusal-acc` claim
was **dropped** at promote (refusal-task number, not a confgate measurement) so the
claims-gate passed. One promote (2601.00138) hit a non-fatal link-forge
AuthenticationRateLimit in `bridge.py` step 6 (stale `LINK_FORGE_PASSWORD`) — graph
writes still completed. See [`HANDOFF_2026-06-16.md`](HANDOFF_2026-06-16.md) for the
triage timings and the experiment rationale.

1. **Run a cheap CF-1-threatening test.** Top READY candidates from the live queue
   (all re-score *cached* generations, ~20–30 min CPU, not mooted, not closure):
   - **CG-FE11** [ROI 8] — base vs Instruct SmolLM2-1.7B length-only AUROC vs pinned
     0.781. Tests whether "length carries the gate" is a post-training artifact. **The
     cleanest cheap CF-1 stressor — start here.**
   - **CG-FE22** [ROI 8] — TF-IDF (1–3 gram) lexical preflight readout vs the 0.7056
     prompt-length ceiling (CF-7 never tested lexical content). Snag: needs raw prompt
     strings recovered from the gate cache.
   - **CG-FE4 / CG-FE9** [ROI 6] — LAC softmax-margin answer-token readout vs the free
     baseline on SmolLM2/Gemma/OLMo-2.
   Lower value: CG-FE18 (information-removal, ROI 9 but 1–2 days, fresh generations);
   CG-FE19 (observability-conditioned conformal — rhymes with the proven cross-domain
   wall, run only to close the proxy angle).
2. **v2 pipeline** (separate spec, do NOT start without one): script generation →
   execution → 3-phase autopilot daemon → semantic mooting (`moot_sweep.py`). Mirror
   topo's autopilot, scoped to local CPU.

Caveat from project memory: several queue items rhyme with lines already run+refuted in
topo v6–v8 (esp. the conformal cross-domain wall and the already-REFUTED
`curation-helps-distillation` premise — which auto-mooted CG-FE13/CG-FE24). CG-FE11 is
the strongest genuinely-novel cheap probe.

## Constraints (unchanged, always in force)

Local/CPU only, no GPU. Numbers only from `confgate/data/pinned_meta.json`.
Don't touch the shipped `confgate/` package or `tests/test_confgate.py`.
link-forge `:7687` + `queue.db` are READ-ONLY. No secrets in the repo.
