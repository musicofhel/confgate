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

The grouping MVP is done. The natural next steps, **all a separate v2 spec**
(do NOT start without one):

1. **Drain the backlog**: 5 papers admitted but only 1 triaged — `bash triage_pending.sh`
   to brief the rest, then `promote_brief.py` each. (Or admit a bigger slice of the
   857-record sweep first.)
2. **v2 pipeline**: script generation → execution → 3-phase autopilot daemon →
   semantic mooting (`moot_sweep.py`). Mirror topo's autopilot, scoped to local CPU.
3. **Act on the queue**: once CG-FEs accumulate, the highest-ROI ones are the
   candidate experiments to actually run against the free gate (confgate v0.2).

## Constraints (unchanged, always in force)

Local/CPU only, no GPU. Numbers only from `confgate/data/pinned_meta.json`.
Don't touch the shipped `confgate/` package or `tests/test_confgate.py`.
link-forge `:7687` + `queue.db` are READ-ONLY. No secrets in the repo.
