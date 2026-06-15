# CLAUDE.md — confgate research-graph (agent orientation)

This is the agent-facing guide to confgate's **paper-triage pipeline**. It mirrors
topo-confidence's research-graph but is a *standalone, downstream* graph: confgate
owns no experiments of its own yet — it consumes topo-confidence's pinned results
and asks one question, **"what published work could BEAT the free length+logprob
confidence gate (or sharpen a certificate)?"**

Humans: read [`../SPEC_TRIAGE_PIPELINE_v1.2.md`](../SPEC_TRIAGE_PIPELINE_v1.2.md)
first, then [`STATE.md`](STATE.md) for where the last session left off.

## What this is, in two sentences

A pull-model triage pipeline that sweeps the literature for papers touching
confgate's findings (CF-1…CF-8) or open levers (CH-1…CH-6), groups each paper by
the lever it influences, and emits a ranked queue of `:FutureExperiment` (CG-FE)
candidates — experiments that could beat the free gate and drive confgate v0.2.
**Scope is the grouping MVP**: `sweep → admit → triage → promote → group`.
Script-generation, execution, and the autopilot daemon are a separate v2 spec.

## Source of truth

| File | What it has |
|---|---|
| [`../FINDINGS.md`](../FINDINGS.md) | CF-1…CF-8 — confgate's confirmed findings (pinned from topo SPEC v6/v7/v8) |
| [`../HYPOTHESES.md`](../HYPOTHESES.md) | CH-1…CH-6 — open levers a challenger could win; `Next ID:` line drives renumber-on-promote |
| [`../PAPER_INDEX.md`](../PAPER_INDEX.md) | External papers, classified TO TEST / REPLICATED / CONTRADICTED |
| [`../NEXT_EXPERIMENTS.md`](../NEXT_EXPERIMENTS.md) | Auto-generated CG-FE priority queue (ROI-tiered) |
| [`validate_claims.py`](validate_claims.py) | The `cg-*` claims ledger AND the promote claims-gate (touch it to accept a new claim) |
| [`STATE.md`](STATE.md) | Where the last session left off |

## The graph

A **standalone** Neo4j at `bolt://localhost:7689` (HTTP `:7476`), separate from
both topo (`:7688`) and link-forge (`:7687`). Credentials live in the gitignored
`research-graph/.env` and in the operator's memory — **never commit them**; the
module defaults use the placeholder `confgate_graph_dev`.

```bash
cd ~/confgate
make up        # docker compose up the graph (research-graph/docker-compose.yml)
make schema    # apply schema.cypher (constraints + fulltext indexes)
make seed      # MERGE CF-1…CF-8 :Finding nodes (grouping experiment-side needs these)
make down      # stop it
```

Node/edge model: `:Finding{CF-N}` · `:Hypothesis`-equivalent CH-N lives in
HYPOTHESES.md · `:FutureExperiment{CG-FE-N}` · `:Paper{status}` ·
`:Tag{CF-N|CH-N}` (the grouping seed) · `:Premise` · `:Method` · `:Dataset`.
Edges: `(:Paper)-[:TAGGED]->(:Tag)`, `(:FutureExperiment)-[:DEPENDS_ON_FINDING|WOULD_UPDATE]->(:Finding)`,
`-[:TRIGGERED_BY]->(:Paper)`, `-[:RELIES_ON]->(:Premise)`,
`(:Method|:Dataset)-[:USED_IN]->(:Paper)`, `-[:MOOTED_BY|ANSWERED_BY]->(...)`.

## The pipeline (grouping MVP)

```
research-sweep confgate            # link-forge tool: keyword sweep -> dated JSON
  ↓  ~/link-forge/data/research-sweep-confgate-<date>.json
python admit.py --from-sweep confgate   # relevance gate -> :Paper{pending_triage} + :TAGGED
  ↓
/confgate-triage <arxiv>  (or bash triage_pending.sh)   # deep brief per paper
  ↓  research-graph/briefs/triage-<date>-<arxiv>.md
python promote_brief.py briefs/<brief>  # YAML FE -> graph + HYPOTHESES/PAPER_INDEX + NEXT_EXPERIMENTS
  ↓
python query.py grouped            # papers + experiments grouped by lever
```

### 1. Sweep — discovery

Keyword config is [`../.claude/research-sweep.yaml`](../.claude/research-sweep.yaml),
keyed to CH-1…CH-6 (`llm_calibration_free`, `selective_prediction`,
`preflight_uncertainty`, `cascade_routing`, `conformal_cross_domain`,
`domain_specialized_small_models`, `cross_cutting`). `research-sweep.ts` lives in
link-forge; run it as `npx tsx ~/link-forge/scripts/research-sweep.ts confgate`.
It writes the dated JSON `admit.py` reads.

### 2. Admit — the relevance gate ([`admit.py`](admit.py))

Pull-model admitter (we do **not** edit link-forge's push bridge). It discovers
candidates from the sweep JSON (`--from-sweep`), falls back to `queue.db`
READ-ONLY (`--from-queue`) or explicit ids; extracts a strict arxiv id (host must
be `arxiv.org`); resolves the matching link-forge `:Link` READ-ONLY to **copy**
its 384-dim MiniLM embedding + forgeScore (no re-embedding); runs a
**lean-inclusive** `claude -p` relevance check against the CF/CH one-liners; and
on admit MERGEs `:Paper{pending_triage}` + `:TAGGED` grouping edges into the
confgate graph. `--dry-run` plans and writes nothing.

### 3. Triage — the deep brief (`/confgate-triage` skill)

A fresh subagent per paper (per-paper context isolation, headlines-only default)
writes a structured brief to `briefs/`. Unlike topo, triage does **not**
auto-promote — briefs are written, then promoted explicitly.

### 4. Promote ([`promote_brief.py`](promote_brief.py))

Parses the brief's YAML FE blocks (via the shared [`brief_parser.py`](brief_parser.py)
— **not** re-derived), renumbers CG-FE/CH ids contiguously from the graph max +
`Next ID:`, MERGEs `:FutureExperiment` with its edges, inserts the CH-N
hypothesis + PAPER_INDEX entry (folding deep-extraction subsections), writes
`:Method`/`:Dataset` edges, resolves the trigger paper via `bridge.py`, regenerates
`NEXT_EXPERIMENTS.md`, and sets the paper `status='graphed'`. **Refuses** if the
brief declares new `cg-*` claims and `validate_claims.py` is older than the brief.

### 5. Group / query ([`query.py`](query.py))

```bash
python query.py grouped        # papers + CG-FE experiments per CF/CH lever  ← the MVP payload
python query.py pending        # pending_triage papers (--ids-only feeds triage_pending.sh)
python query.py future CG      # the CG-FE queue
python query.py novelty "<claim>"   # fulltext over findings + papers
python query.py premises       # premise vocabulary + reliant-FE counts
python query.py mooted         # FEs closed by adjacency (for review/resurrection)
```

## Premises + closure by adjacency ([`premises.py`](premises.py))

A `:Premise` is a falsifiable assumption many FEs share. When a verdict refutes
one, every FE that `RELIES_ON` it is closed **MOOTED** (reversible via
`update_status.py <id> READY`). Seeded premises: `free-gate-is-ceiling`,
`length-is-the-signal`, `cross-domain-cert-infeasible`,
`escalation-beats-introspection`, `curation-helps-distillation` (seeded REFUTED
per topo H-R), `preflight-promptlen-ceiling`. The **deterministic** layer only —
the semantic `moot_sweep.py` (MiniLM + `claude -p` adjudication) is deferred to v2.

```bash
python premises.py list
python premises.py refute free-gate-is-ceiling --by CG-FE12 --reason "..."   # cascades moots
python update_status.py CG-FE3 READY    # resurrect a mooted FE
```

## The 5-item clone surgery (why these scripts differ from topo's)

Every script cloned from topo-confidence carries exactly five deliberate edits,
each guarded by a unit test in `tests/research_graph/test_phase3_promote.py`:

1. **NGS/Redis publish stripped** — no `topoconf:research:*` channel, no `import redis`.
2. **Embedding-backfill disabled** — no PyTorch embedder; grouping is tag-based, not vector.
3. **Claims-gate path → local** `research-graph/validate_claims.py` (ROOT, not REPO).
4. **Bolt/pw defaults → confgate** `.env` (`:7689`, `confgate_graph_dev`).
5. **Namespace regexes → CF/CH/CG-FE** (renumber reads `Next ID: CH-N`; FE pathway pseudo-id `CG`).

## Smoke test

```bash
python validate_claims.py    # 12 cg-* external anchors, all REGISTERED, exit 0
make test                    # unit tier (Docker-free): pytest + ruff
make test-int                # integration tier: spins two ephemeral graphs
make e2e-dry                 # zero-network sweep→admit→promote→grouped tracer
```

## Constraints (always in force)

- **Local / CPU only. No GPU, no cloud** — even for "cheap" rescoring.
- Numbers come ONLY from `confgate/data/pinned_meta.json` (via `validate_claims.py`).
- Do **not** edit the shipped `confgate/` package or `tests/test_confgate.py`.
- link-forge `bolt:7687` + `queue.db` are **READ-ONLY** to us. We never edit
  link-forge's processor/bridge — admit is a pull-model consumer.
- No secrets in the repo (`.env` is gitignored).

## Deferred to v2 (NOT in this MVP)

Script generation · experiment execution · the 3-phase autopilot daemon ·
semantic mooting (`moot_sweep.py`) · the NGS/Redis research channel ·
auto-promote-on-triage. The MVP stops at a ranked, grouped CG-FE queue for a
human to act on.
