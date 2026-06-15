# SPEC — confgate Paper-Triage Pipeline (v1, "Grouping MVP")

**Status:** DRAFT — ready for build
**Date:** 2026-06-14
**Owner:** aaron
**Goal:** Stand up a paper-triage pipeline for `~/confgate` that mirrors the
`~/topo-confidence` pattern, so the link-forge corpus can be **swept → relevance-gated
→ triaged → grouped** against confgate's shipped success factors, and emit a ranked
queue of **FutureExperiments that could beat the free gate** (drive a confgate v0.2).

## Locked decisions (from scoping)

| # | Decision | Choice |
|---|---|---|
| 1 | Graph topology | **New standalone Neo4j** — `confgate-research-graph`, `bolt://localhost:7689` / `http://localhost:7476`. Own `CF-`/`CH-`/`CG-FE` namespace. Zero coupling to topo's `:7688`. |
| 2 | Triage goal | **Experiments to beat the gate** — every brief proposes `:FutureExperiment` levers against CF-1…CF-8 (raise AUROC, beat cascade, crack the cross-domain cert wall, better base-swap). |
| 3 | Phase scope | **Grouping MVP first** — sweep → admit → triage → promote → group. **Deferred to a v2 spec:** scriptgen, experiment execution, systemd autopilot, semantic `moot_sweep`. |
| 4 | Code reuse | **Clone & adapt into `confgate/research-graph/`** — copy topo scripts, repoint paths/endpoints/namespace. confgate diverges freely; no edits to the live topo/link-forge pipeline. |

## Non-negotiable invariants

- **Do not touch the shipped package.** `confgate/` (the pip package, `topo-confgate` v0.1.1)
  and its `tests/` stay byte-stable. All new tooling lives in the **sibling** dir
  `confgate/research-graph/` and is excluded from the wheel/sdist. The existing
  `pytest tests/` suite must stay green at every phase boundary.
- **Do not edit link-forge's processor or the topo bridge.** confgate reads link-forge
  (`bolt://localhost:7687`) read-only and writes only its own graph (`:7689`). The
  research-sweep skill is already multi-project; we add a config, not code.
- **Numbers come from `confgate/data/pinned_meta.json`.** The CF-N findings are derived
  verbatim from the pinned anchors — never re-state a number that isn't in that file.
- **Local/CPU only for tooling.** Admission + triage are `claude -p` + Neo4j + MiniLM
  embeddings (CPU). No GPU. (Per `feedback-no-local-gpu-even-rescoring`; experiment
  *execution* is out of scope here anyway.)

---

## Architecture

### Data flow (MVP)

```
confgate/.claude/research-sweep.yaml   (CH-1..CH-6 keyword groups)
        │  research-sweep skill (existing, multi-project)
        ▼
link-forge queue  →  link-forge processor (forage + chunk + MiniLM embed)
        │            writes :Link nodes, tag research-sweep:confgate:<arxiv>
        ▼   (link-forge Neo4j bolt:7687 — shared substrate, read-only to us)
┌──────────────────────────────────────────────────────────────┐
│ confgate/research-graph/admit.py        ← NEW (decoupled gate) │
│  - pull confgate-tagged :Link nodes from link-forge            │
│  - relevance check (claude -p) vs FINDINGS.md (CF) + HYPOTHESES │
│    (CH)  — "could this paper inform a lever to beat the gate?"  │
│  - MERGE :Paper {status:'pending_triage'} into confgate graph  │
└──────────────────────────────────────────────────────────────┘
        ▼   (confgate Neo4j bolt:7689)
/confgate-triage skill  →  briefs/triage-YYYY-MM-DD-<arxiv>.md
        │  (fresh subagent per paper, refutations-first, YAML CFE blocks)
        ▼
confgate/research-graph/promote_brief.py
  - MERGE :FutureExperiment (CG-FE#) + edges TRIGGERED_BY / WOULD_UPDATE(CF) /
    DEPENDS_ON_FINDING / RELIES_ON(premise)
  - (:Method|:Dataset)-[:USED_IN]->(:Paper)
  - bridge.py resolve <arxiv> → link-forge forgeScore/title
  - claims gate (validate_claims.py mtime guard)
  - set :Paper {status:'graphed'}; regenerate NEXT_EXPERIMENTS.md
        ▼
GROUPING OUTPUT:  PAPER_INDEX.md  +  NEXT_EXPERIMENTS.md (ROI-ranked CG-FE queue)
                  papers grouped by which CF-N success-factor they touch
```

**Why a confgate-side `admit.py` instead of a link-forge bridge?** Topo's admission
runs *inside* link-forge's processor (`research-graph-suggest.ts`) and is hard-wired to
`~/topo-confidence`. Decision #4 says don't edit that. A standalone confgate admitter
that **reads** link-forge and **writes** the confgate graph keeps link-forge a shared
forager/embedder, gives confgate full ownership of its perimeter, and is the cleanest
tracer-bullet boundary. (Swept papers may *also* be admitted to topo by the existing
bridge — harmless; the graphs are independent.)

### Namespace

| Concept | topo | confgate |
|---|---|---|
| Findings (success factors) | `F-N` | **`CF-N`** |
| Hypotheses (levers) | `H-N` | **`CH-N`** |
| FutureExperiments | `P11-FE#` | **`CG-FE#`** (single pseudo-pathway `CG`) |
| Completed experiments | `EXP-NNN` | **`CEXP-NNN`** (reserved; v2) |
| Claims (validate_claims) | `edge-v8-*` | **`cg-*`** |
| Premises | `dom-causal-lever` | `free-gate-is-ceiling`, … |

### The success factors → `FINDINGS.md` (CF-N), derived from `pinned_meta.json`

These are the **things papers must influence**. Bootstrapped once in Phase 0.

| ID | Claim (one-liner) | Pinned anchor |
|---|---|---|
| **CF-1** | Free `(n_gen_tokens, mean_logprob)` logistic gate is the most generalizing zero-cost correctness readout. | OOF AUROC SmolLM2 0.810 / Gemma 0.844 / OLMo-2 0.838; in-domain Qwen-1.5B LOCO 0.845 |
| **CF-2** | Which scalar carries is family-dependent → pin both. | length-only (SmolLM2) / both (Gemma) / length-led (OLMo-2) |
| **CF-3** | Gate-ordered cascade dominates introspection & self-consistency at matched cost. | +3.38pp vs hull (p=0.0025); beats K=8 (0.732 vs 0.554) |
| **CF-4** | Cross-scale zero-shot conformal certs are valid. | 1.5B→7B k=0 validity 1.0 @ 0.60 cov, ε=0.2 |
| **CF-5** | Cross-domain conformal certs are infeasible with any light head. | MATH→BBH validity 0.0 ∀ feasible k; `certify_cross_domain()` refuses |
| **CF-6** | In-domain Mondrian group-conditional certs are valid but low-coverage. | algebra/prealgebra validity 1.0, coverage ≤5.4%, k≈16–32 |
| **CF-7** | Preflight prompt-length-only gate ~0.71; prompt-cloud eigenspectrum adds nothing. | 0.706 OOF; H-E refuted (Δ−0.0096, p=0.42) |
| **CF-8** | Deployment recipe: swap base to a domain-specialized small model; do NOT use the gate to curate distillation data. | Qwen2.5-Math-1.5B +9.2pp @ ¼ cost; curation H-R refuted (0.494 < 0.500) |

### The levers → `HYPOTHESES.md` (CH-N) = the relevance perimeter

A paper is **admitted** iff it could plausibly corroborate/contradict a CF-N **or**
inform a CH-N lever. (Lean inclusive — false-positive admit ≫ false-negative miss, per
`feedback-relevance-prompts-lean-inclusive`.)

| ID | Lever (what would beat the gate) |
|---|---|
| **CH-1** | A zero/low-cost readout beats free length+logprob OOF AUROC on held-out families. |
| **CH-2** | A cheap **pre-generation** signal beats prompt-length 0.71 (improves CF-7). |
| **CH-3** | A routing/cascade policy beats gate-ordered cascade at matched cost (improves CF-3). |
| **CH-4** | A light-head method delivers **valid cross-domain certs** — cracks the CF-5 wall. |
| **CH-5** | A better escalation target / base-swap raises the matched-cost ceiling (extends CF-8). |
| **CH-6** | Group-conditional / adaptive conformal raises Mondrian in-domain coverage (improves CF-6). |

---

## Phase plan (tracer-bullet: each slice ships a passing test before the next starts)

Each phase = one PR off `main` → CI green → merge. The **tracer-bullet test** named in
each phase is the gate; no phase N+1 work begins until phase N's test is green in CI.

### Phase 0 — Scaffolding + standalone graph standup

**Deliverables**
- `confgate/research-graph/` tree:
  - `docker-compose.yml` — `neo4j:5.26-community`, container `confgate-research-graph`,
    ports `7689:7687` / `7476:7474`, APOC, `restart: unless-stopped`, named volume.
  - `.env` — `NEO4J_BOLT_URL=bolt://localhost:7689`, `NEO4J_USER=neo4j`,
    `NEO4J_PASSWORD=<new pw>`, `LINK_FORGE_BOLT_URL=bolt://localhost:7687`,
    `LINK_FORGE_USER`, `LINK_FORGE_PASSWORD`. **gitignored**; commit `.env.example`.
  - `schema.cypher` — cloned from topo, dropped Pathway-specific timeline constraints,
    kept: `:Paper(arxiv_id UNIQUE, status, year, embedding)`, `:Finding(id UNIQUE)`,
    `:FutureExperiment(id UNIQUE, status, roi_score)`, `:Premise(id UNIQUE, status)`,
    `:Method(key)`, `:Dataset(key)`, `:Tag(name)`, the 384-dim vector indexes on
    `Paper.embedding`/`Finding.embedding`, and the fulltext indexes.
  - `requirements.txt` — `neo4j`, `python-dotenv`, `sentence-transformers` (MiniLM,
    pin same model hash as link-forge: `all-MiniLM-L6-v2`), `pyyaml`.
  - `README.md` — how to bring the graph up, env, ports.
- `confgate/FINDINGS.md` — CF-1…CF-8 bootstrapped from `pinned_meta.json` (table above,
  expanded to the topo `### CF-N: <claim>` block format the parser reads).
- `confgate/HYPOTHESES.md` — CH-1…CH-6.
- `pyproject.toml` — confirm `research-graph/`, `FINDINGS.md`, `HYPOTHESES.md` are **not**
  packaged (add explicit `exclude`/`tool.setuptools.packages.find` guard); re-build wheel
  and diff `unzip -l` against the v0.1.1 wheel to prove zero new files shipped.

**Architecture notes**
- New password (not topo's `topo_graph_dev`, not link-forge default). Store in memory.
- Vector dim 384 must match link-forge's MiniLM so `admit.py` can copy embeddings over
  rather than re-embedding. Reuse link-forge's canonical model
  (`models/all-MiniLM-L6-v2`, sha `759c3cd2…`).

**Tracer-bullet test (`tests/research_graph/test_phase0_graph.py`, integration tier)**
- `docker compose up -d` an ephemeral graph → apply `schema.cypher` → assert all
  constraints/indexes present (`SHOW CONSTRAINTS` count) and node count == 0.
- Parse `FINDINGS.md` → assert CF-1…CF-8 present with non-empty claims.
- **Package-hygiene unit test** (`tests/test_packaging.py`, Docker-free): build wheel,
  assert file list == v0.1.1 file list (no `research-graph/`, no `FINDINGS.md`).

### Phase 1 — Relevance gate (`admit.py`)

**Deliverables**
- `confgate/research-graph/admit.py`
  - Inputs: list of arxiv IDs **or** `--from-sweep confgate` (query link-forge for
    `:Link` nodes tagged `research-sweep:confgate:*`).
  - For each candidate: pull title/abstract/keyConcepts/forgeScore + embedding from
    link-forge; build CF/CH context index from `FINDINGS.md`+`HYPOTHESES.md`; run
    `relevance_check()` via `claude -p` with a lean-inclusive rubric →
    `{relevant: bool, relevance_note, which_CF_or_CH: [...]}`.
  - On admit: `MERGE (:Paper {arxiv_id})` in confgate graph with
    `status:'pending_triage'`, `relevance_note`, copied `embedding`, `forge_score`,
    and `:TAGGED` edges to the CF/CH it touches (this is the **grouping seed**).
  - Idempotent (MERGE), re-runnable, `--dry-run`.
- `confgate/research-graph/bridge.py` — `resolve <arxiv>` → link-forge title+forgeScore
  (cloned, repoint to confgate `.env`).

**Tracer-bullet test (`tests/research_graph/test_phase1_admit.py`)**
- Seed a fake link-forge `:Link` (in the ephemeral integration Neo4j, two-DB fixture)
  → run `admit.py --dry-run` with a **stubbed** relevance fn (no live `claude -p` in CI)
  → assert a `:Paper {pending_triage}` would be written with the right CF/CH tags.
- Unit test the rubric prompt builder: given CF/CH files, the context string contains all
  8 CF + 6 CH one-liners.

### Phase 2 — Triage briefs (`/confgate-triage` skill + paper-triage clone)

**Deliverables**
- `confgate/.claude/skills/confgate-triage/SKILL.md` — cloned from the `paper-triage`
  skill, repointed to `~/confgate/research-graph/briefs/`, CF/CH instead of F/H, and the
  YAML block emits **`CG-FE#`** experiments. Keeps: fresh subagent per paper (confirmation-
  bias defense, Ríos-García `2604.18805`), refutations-first ordering, headlines-only
  default context with explicit on-demand `Read` of CF bodies logged in the footer.
- Brief contract (`briefs/triage-YYYY-MM-DD-<arxiv>.md`) sections:
  `## Refutations` → `## Direct connections to CF-N / CH-N` → `## Methodologies` →
  `## Approaches` → `## Datasets & benchmarks` → `## Implementation details` →
  `## Replicable intermediates` → `## Cross-paper signals` →
  `## Proposed FutureExperiments` (YAML CG-FE blocks) →
  `## Proposed HYPOTHESES.md additions` (CH-N) → `## PAPER_INDEX classification` →
  `## New claims` → `## Sources consulted`.
- `CG-FE` YAML block schema: `id, pathway: CG, description, rationale, trigger, status:
  READY, priority, roi, cost, depends-on:[CF-N], would-update:[CF-N], triggered-by:[arxiv],
  relies-on:[premise]`.
- `confgate/research-graph/triage_pending.sh` — loop `/confgate-triage` over every
  `pending_triage` paper (parallel-3), each worker auto-promotes inline (flock-serialized).

**Tracer-bullet test (`tests/research_graph/test_phase2_brief.py`, unit)**
- Golden-fixture brief (`tests/research_graph/fixtures/triage-sample.md`) → assert the
  brief parser (shared with Phase 3) extracts ≥1 valid CG-FE block with all required
  fields and that `depends-on` references an existing CF-N.

### Phase 3 — Promotion + grouping (`promote_brief.py`, `premises.py`, `query.py`, `validate_claims.py`)

**Deliverables**
- `confgate/research-graph/promote_brief.py` — cloned. Parses YAML CG-FE → MERGE
  `:FutureExperiment` + `DEPENDS_ON_FINDING`/`WOULD_UPDATE`(→CF)/`TRIGGERED_BY`(→Paper)/
  `RELIES_ON`(→Premise) edges; inserts CH-N into `HYPOTHESES.md`; folds the deep-extraction
  subsections under a `PAPER_INDEX.md` entry; writes `(:Method|:Dataset)-[:USED_IN]->(:Paper)`;
  calls `bridge.py resolve`; **claims gate** (refuse if brief declares new quantitative
  claims and `validate_claims.py` mtime ≤ brief mtime); sets `:Paper{status:'graphed'}`;
  calls `generate_next_experiments.py`. Flags: `--dry-run`, `--update-existing`.
- `confgate/research-graph/generate_next_experiments.py` — query READY CG-FE by
  `roi_score` desc → rewrite `confgate/NEXT_EXPERIMENTS.md` (the **grouping deliverable**,
  papers→levers→ranked experiments).
- `confgate/research-graph/premises.py` — seed confgate premises
  (`free-gate-is-ceiling`, `cross-domain-cert-infeasible`, `length-is-the-signal`,
  `curation-helps-distillation` [born REFUTED — H-R], `preflight-promptlen-ceiling`);
  `refute/confirm` cascade-moots reliant CG-FE. (Deterministic mooting only.)
- `confgate/research-graph/query.py` — `novelty`, `pending`, `status-report`,
  `subgraph <CF>`, `future CG`, `grouped` (papers grouped by CF tag). Cloned, trimmed.
- `confgate/research-graph/validate_claims.py` — seed with the 8 CF anchors as
  `kind="external"`/pinned entries; `cg-*` claim ids; smoke = all PASS/REGISTERED.

**Tracer-bullet test (`tests/research_graph/test_phase3_promote.py`, integration)**
- Apply schema → seed CF-1…CF-8 `:Finding` nodes + premises → `promote_brief.py
  fixtures/triage-sample.md --dry-run` asserts the planned MERGEs; then **live** promote
  against the ephemeral graph → assert `:FutureExperiment` exists with edges to the right
  CF, `:Paper.status=='graphed'`, and `NEXT_EXPERIMENTS.md` regenerated non-empty.
- Claims-gate negative test: a brief with a new `cg-*` claim and a stale
  `validate_claims.py` mtime → promote **refuses**.
- Premise cascade test: `premises.py refute free-gate-is-ceiling` → a CG-FE that
  `RELIES_ON` it flips to MOOTED; `update_status.py … READY` reverses it.

### Phase 4 — End-to-end grouping run + docs

**Deliverables**
- `confgate/.claude/research-sweep.yaml` — keyword groups keyed to CH-1…CH-6
  (e.g. `selective_prediction`, `llm_calibration_free`, `conformal_cross_domain`,
  `cascade_routing`, `domain_specialized_small_models`, `preflight_uncertainty`).
- One real end-to-end pass on local CPU: sweep → admit (live `claude -p`) → triage a
  small batch → promote → inspect `NEXT_EXPERIMENTS.md` + `query.py grouped`.
- `confgate/research-graph/CLAUDE.md` — agent orientation (mirror topo's), documenting
  the MVP boundary and what's deferred to v2.
- Memory write + a `confgate/research-graph/STATE.md` handoff.

**Tracer-bullet test:** the Phase 4 PR is the integration of all prior tests + a smoke
`make e2e-dry` target that runs sweep(0 net)→admit(stub)→promote(fixture) without network.

---

## CI/CD

Mirror the link-forge two-tier pattern (Testcontainers/service-container integration tier
already proven there, commit `fb7bbcc`).

- **`.github/workflows/ci.yml`** (new — confgate has none today):
  - **`unit`** job (every push/PR, Docker-free): `pytest tests/` (existing package suite —
    must stay green) + `tests/test_packaging.py` + the Phase-1/2 unit tests + `ruff`.
  - **`integration`** job (every push/PR): GitHub Actions `services: neo4j:5.26-community`
    on dynamic port (env `NEO4J_BOLT_URL`), runs `tests/research_graph/` (Phases 0/1/3
    integration tests). Never binds the dev `:7689`/`:7687`.
- **Branch protection on `main`:** both jobs required green before merge. No direct pushes
  to `main`; one PR per phase (tracer-bullet gate).
- **Local mirror:** `make test` (unit) / `make test-int` (spins ephemeral compose graph) /
  `make e2e-dry`. Phase N is "done" only when its named test is green both locally and in CI.
- **Secrets:** no passwords in the repo. `.env` gitignored, `.env.example` committed;
  CI Neo4j uses the workflow-provided service password, not the dev one.
- **Packaging guard in CI:** `test_packaging.py` fails the build if the wheel file list
  drifts from v0.1.1 — protects the shipped package from accidental tooling inclusion.

---

## Explicitly out of scope (→ v2 spec "confgate autopilot")

- Phase-2/3 **scriptgen** (`generate_recompute.py`) and **experiment execution** — confgate
  experiments need a model harness + likely H100 (RunPod), unlike topo's local-only rule.
- **systemd autopilot** services (`autopilot@{triage,scriptgen,experiment}`), `.autopilot/`
  trigger/budget/pause machinery, the `:9876` stream-deck endpoints.
- **Semantic `moot_sweep.py`** (MiniLM cosine + `claude -p` adjudication). MVP keeps only
  deterministic premise-cascade mooting.
- A link-forge-side automatic bridge (we use the decoupled `admit.py` pull model instead).

---

## Build order checklist

- [ ] **P0** graph up · schema applied · CF/CH bootstrapped · packaging guard green
- [ ] **P1** `admit.py` + `bridge.py` · stubbed-relevance admit test green
- [ ] **P2** `/confgate-triage` skill · brief parser + golden-fixture test green
- [ ] **P3** `promote_brief.py` + `premises.py` + `query.py` + `validate_claims.py` ·
      promote/claims-gate/cascade tests green
- [ ] **P4** sweep config · live e2e pass · `NEXT_EXPERIMENTS.md` grouped output · docs
- [ ] CI `ci.yml` (unit + integration) green; `main` branch protection on

## Open questions for the build session (not blockers)

1. confgate graph password — generate fresh; OK to store in memory like topo's?
2. Sweep cadence — one-shot for MVP, or wire a cron later (deferred with autopilot)?
3. Should `admit.py` copy link-forge embeddings (fast, requires hash match) or re-embed
   locally (slower, self-contained)? Recommend copy + hash-assert.
