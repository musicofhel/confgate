# SPEC — confgate Paper-Triage Pipeline (v1.1, "Grouping MVP")

**Status:** DRAFT — ready for build (audited)
**Date:** 2026-06-14
**Supersedes:** `SPEC_TRIAGE_PIPELINE_v1.md` (v1 kept for history)
**Owner:** aaron
**Goal:** Stand up a paper-triage pipeline for `~/confgate` that mirrors the
`~/topo-confidence` pattern, so the link-forge corpus can be **swept → relevance-gated
→ triaged → grouped** against confgate's shipped success factors, and emit a ranked
queue of **FutureExperiments that could beat the free gate** (drive a confgate v0.2).

> **What changed in v1.1** — a soup-to-nuts audit on 2026-06-14 verified every cloned
> script's real contract and dry-ran a paper (RouteLLM `2406.18665`) end-to-end. Four
> defects in v1 are fixed here; see [§ Changelog](#changelog-v1--v11) and the inline
> **`[v1.1]`** markers. The big one: **link-forge has no graph-side `research-sweep:*`
> tag to query**, so admit.py's candidate discovery is redesigned around the sweep's
> authoritative output.

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
  `pytest tests/` suite (11 tests, pure-unit) must stay green at every phase boundary.
- **Do not edit link-forge's processor or the topo bridge.** confgate reads link-forge
  (`bolt://localhost:7687`) **read-only** and writes only its own graph (`:7689`). It
  also reads link-forge's **sweep output JSON / `queue.db`** read-only (see Phase 1).
  The research-sweep skill is already multi-project; we add a config, not code.
- **Numbers come from `confgate/data/pinned_meta.json`.** The CF-N findings are derived
  verbatim from the pinned anchors — never re-state a number that isn't in that file.
- **Local/CPU only for tooling.** Admission + triage are `claude -p` + Neo4j + MiniLM
  embeddings (CPU). No GPU. (Per `feedback-no-local-gpu-even-rescoring`; experiment
  *execution* is out of scope here anyway.)

---

## Ground-truth notes (verified by audit, 2026-06-14)

These are the facts the build session must not re-discover the hard way. Every claim
below was confirmed by reading the actual source this session.

### link-forge data model (read-only substrate)
- **`:Link` node properties** (merge key `url`): `url, title, description, content,
  embedding (number[384]), domain, savedAt, updatedAt, forgeScore, contentType,
  quality, keyConcepts (string[]), authors (string[]), keyTakeaways (string[]),
  source ("arxiv"|"semantic-scholar"|"openalex"|"huggingface"|"user"), displayUrl`.
- **No `arxiv`/`arxivId` property on `:Link`.** arxiv id is resolved from the URL at
  ingest, never stored. **admit.py must extract arxiv from `Link.url`.**
- **Embedding IS on the node** — `:Link.embedding` is a **384-dim** vector from
  **`Xenova/all-MiniLM-L6-v2` (transformers.js / ONNX)**, mean-pooled + unit-normalized.
  There is also `(:Link)-[:HAS_CHUNK]->(:Chunk {embedding[384]})` for chunk-level RAG.
- **Tags are `:Tag` nodes** via `(:Link)-[:TAGGED_WITH]->(:Tag)` — **the
  `research-sweep:<project>:<id>` string is NOT one of them.** That string lives in
  `~/link-forge/data/queue.db` (SQLite) as `discord_message_id`, with
  `discord_channel_id = 'research-sweep:<project>'`. **`[v1.1]` this is why admit.py
  pulls from the sweep output, not a graph tag (Defect 1 fix).**
- **link-forge Neo4j:** `bolt://localhost:7687`, user `neo4j`, env
  `LINK_FORGE_BOLT_URL/LINK_FORGE_USER/LINK_FORGE_PASSWORD` (dev default `link_forge_dev`).
- **`research-graph-suggest.ts`** (the topo bridge we are NOT cloning) is hard-wired to
  `~/topo-confidence` (`TOPO_CONFIDENCE_DIR` override) and runs admission **inline,
  push-model, from inside link-forge's processor** — a pattern confgate can't reuse
  without editing link-forge, hence the **pull-model admit.py**.

### topo scripts to clone (contracts confirmed)
- `promote_brief.py <brief> [--dry-run] [--update-existing] [--no-renumber]` — 9-step
  pipeline. FE YAML schema = exactly the `CG-FE` block in Phase 2. **`[v1.1]` clone
  surgery required:** step 9 publishes to Redis `topoconf:research:triaged` (**strip**);
  step 8b calls `backfill_embeddings.embed_node()` (**repoint/disable**, see embeddings
  note); claims gate calls `validate_claims.py` by path (**repoint**). FE field `roi`
  validated ∈ [1,10]; `status ∈ {READY,TRIGGERED,BLOCKED,COMPLETED,ABANDONED,MOOTED,
  ANSWERED}`; `priority ∈ {CRITICAL,HIGH,MEDIUM,LOW}`.
- `premises.py {seed,list,link,refute,confirm}` — deterministic cascade-moot: refuting a
  premise MOOTs every `READY|TRIGGERED|BLOCKED` FE that `RELIES_ON` it; reversible.
- `bridge.py {resolve,enrich,ungraphed}` — dual-driver, link-forge read-only, env vars
  already match our `.env`. `resolve <arxiv>` → title/forgeScore/url/quality/concepts.
- `query.py` — `pending, future, novelty, status-report, subgraph, paper, premises,
  highest-roi, impact, promote, reject, …` (importable lib fns too).
- `validate_claims.py` lives at **topo repo root**, not under `research-graph/`. Claim
  states: `PASS` (back-checked), `REGISTERED` (external/paper-cited), `PENDING_FE`
  (forward-looking threshold). mtime gate is load-bearing.
- `generate_next_experiments.py` (no args) → rewrites `NEXT_EXPERIMENTS.md`, ROI-desc,
  tiered (CRITICAL≥9/HIGH≥7/MEDIUM≥5/LOW<5). `update_status.py <FE> <status>` reverses
  MOOTED→READY.
- **`FINDINGS.md` block** the relevance gate greps: `### F-N: <claim>` + `**Claim.**`,
  `**Strength:**`, `**Evidence:**`, `**Controls passed:**`, `**Strongest
  counterargument:**`, `**Would be overturned by:**`. **`HYPOTHESES.md` block**:
  `### H-N:` + `**Priority:** / **Motivated by:** / **Test:** / **Requires:** /
  **Would change:** / **Blocks:**`.
- **`paper-triage` skill** (`~/.claude/skills/paper-triage/`) spawns a **fresh subagent
  per paper** (Ríos-García `2604.18805` confirmation-bias defense), writes Refutations
  **first**, loads only headline one-liners (not full bodies), and **deliberately does
  NOT auto-promote** — it surfaces the brief path + commands. **`[v1.1]` confgate keeps
  manual promote for the MVP (Defect 4).**
- **`research-sweep` skill** (`~/.claude/skills/research-sweep/`) already multi-project:
  `research-sweep <project> [--dry-run]` → `npx tsx ~/link-forge/scripts/research-sweep.ts`
  reads `~/<project>/.claude/research-sweep.yaml`, hits arxiv/Semantic-Scholar/OpenAlex/HF,
  **writes a dated JSON of swept papers** and enqueues them. Cron-able, no MCP/session.

### confgate repo state
- Build backend is **hatchling**, not setuptools:
  `[tool.hatch.build.targets.wheel] packages = ["confgate"]` — an **allowlist**, so a
  sibling `research-graph/` and top-level `FINDINGS.md` are **already excluded**; no
  exclude stanza needed. **`[v1.1]` Defect 2 fix.**
- **Packaging-guard baseline** = the committed `dist/topo_confgate-0.1.1-py3-none-any.whl`
  — exactly **13 files** (6 modules + `data/pinned_gates.json` + `data/pinned_meta.json`
  + 5 dist-info). The guard test diffs `unzip -l` against this set.
- 11 pure-unit tests in `tests/test_confgate.py` (some skip without `CONFGATE_REPO`
  caches). **No `.github/workflows/`.** Clean `main`, remote `musicofhel/confgate`.

---

## Architecture

### Data flow (MVP) — `[v1.1]` admit.py discovery redesigned

```
confgate/.claude/research-sweep.yaml   (CH-1..CH-6 keyword groups)
        │  research-sweep skill (existing, multi-project)
        ▼
~/link-forge/scripts/research-sweep.ts
        │  writes dated sweep JSON (arxiv ids per project) + enqueues to queue.db
        │  (discord_channel_id='research-sweep:confgate', message_id=
        │   'research-sweep:confgate:<arxiv|sha1-16>')
        ▼
link-forge processor (forage + chunk + MiniLM/ONNX embed)
        │  writes :Link {url, embedding[384], forgeScore, keyConcepts, ...}
        ▼   (link-forge Neo4j bolt:7687 — shared substrate, READ-ONLY to us)
┌──────────────────────────────────────────────────────────────────────┐
│ confgate/research-graph/admit.py            ← NEW (decoupled, PULL)    │
│  candidate list = sweep JSON for `confgate`  (NOT a graph tag — v1.1)  │
│    └─ fallback: queue.db WHERE discord_channel_id='research-sweep:     │
│       confgate'                                                        │
│  for each candidate:                                                   │
│    - url → arxiv_id via cloned strict extractor (sha1-16 fallback)     │
│    - resolve :Link by URL in link-forge → title/abstract/keyConcepts/  │
│      forgeScore + copy embedding[384]                                  │
│    - relevance check (claude -p) vs FINDINGS.md (CF)+HYPOTHESES.md (CH) │
│      "could this paper inform a lever to beat the gate?" (lean-incl.)  │
│    - MERGE :Paper {arxiv_id, status:'pending_triage', embedding,       │
│      forge_score, relevance_note} + :TAGGED edges to CF/CH it touches  │
└──────────────────────────────────────────────────────────────────────┘
        ▼   (confgate Neo4j bolt:7689)
/confgate-triage skill  →  briefs/triage-YYYY-MM-DD-<arxiv>.md
        │  (fresh subagent per paper, refutations-first, YAML CG-FE blocks)
        │  surfaces brief + promote command — does NOT auto-promote (v1.1)
        ▼
confgate/research-graph/promote_brief.py   (clone, surgery per v1.1 checklist)
  - MERGE :FutureExperiment (CG-FE#) + TRIGGERED_BY / WOULD_UPDATE(CF) /
    DEPENDS_ON_FINDING / RELIES_ON(premise)
  - (:Method|:Dataset)-[:USED_IN]->(:Paper)
  - bridge.py resolve <arxiv> → link-forge forgeScore/title
  - claims gate (validate_claims.py mtime guard; repointed path)
  - set :Paper {status:'graphed'}; regenerate NEXT_EXPERIMENTS.md
  - [STRIPPED v1.1] Redis publish; [REPOINTED v1.1] embed_node
        ▼
GROUPING OUTPUT:  PAPER_INDEX.md  +  NEXT_EXPERIMENTS.md (ROI-ranked CG-FE queue)
                  papers grouped by which CF-N success-factor they touch
```

**Why a confgate-side `admit.py` (pull) instead of a link-forge bridge (push)?** Topo's
admission runs *inside* link-forge's processor (`research-graph-suggest.ts`), hard-wired
to `~/topo-confidence`. Decision #4 forbids editing it. A standalone confgate admitter
that **reads** link-forge (graph + sweep output) and **writes** the confgate graph keeps
link-forge a shared forager/embedder, gives confgate full ownership of its perimeter, and
is the cleanest tracer-bullet boundary. **`[v1.1]` Because the `research-sweep:*` provenance
is in `queue.db`/sweep-JSON and not on the `:Link` node, the candidate list is read from
the sweep's own output — this is the authoritative per-project set and carries arxiv ids
for free.** (Swept papers may *also* be admitted to topo by the existing bridge if they
also match topo's perimeter — harmless; the graphs are independent.)

### Embeddings — `[v1.1]` provenance correction (Defect 3)

- **Papers:** admit.py **copies** `:Link.embedding` (384-dim) straight into
  `:Paper.embedding`. No re-embedding → Paper vectors are internally consistent and
  exactly match link-forge's space. (Resolves v1 open-question #3 → **copy**.)
- **Findings (CF-N):** if we embed CF `:Finding` nodes for vector search, note that
  link-forge used the **ONNX `Xenova/all-MiniLM-L6-v2`** while a local
  `sentence-transformers all-MiniLM-L6-v2` is the **PyTorch** variant — same architecture,
  **near-identical but not bit-identical** vectors (cosine ≈ 0.999). For the MVP, grouping
  is **tag-based** (`:TAGGED` to CF/CH), not Paper↔Finding kNN, so this drift is inert.
  If/when we add semantic Finding↔Paper search, either embed Findings through link-forge's
  embedder or accept and **document** the drift.
- **There is NO sha256 model-hash gate in link-forge's embedding path.** The
  `759c3cd2…` hash referenced in memory is link-forge's **sync-peer** gate (NUC), not the
  embedder — do **not** add a hash-assert in admit.py.

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
    `LINK_FORGE_USER=neo4j`, `LINK_FORGE_PASSWORD=<link-forge pw>`,
    `LINK_FORGE_QUEUE_DB=~/link-forge/data/queue.db`,
    `LINK_FORGE_SWEEP_DIR=<dir research-sweep.ts writes dated JSON to>`. **gitignored**;
    commit `.env.example`.
  - `schema.cypher` — cloned from topo, dropped Pathway-timeline constraints, kept:
    `:Paper(arxiv_id UNIQUE, status, year, embedding)`, `:Finding(id UNIQUE)`,
    `:FutureExperiment(id UNIQUE, status, roi_score)`, `:Premise(id UNIQUE, status)`,
    `:Method(key)`, `:Dataset(key)`, `:Tag(name)`, the 384-dim vector indexes on
    `Paper.embedding`/`Finding.embedding`, and the fulltext indexes.
  - `requirements.txt` — `neo4j`, `python-dotenv`, `pyyaml`. **`[v1.1]`
    `sentence-transformers` is OPTIONAL** (only if we embed Findings; Papers reuse copied
    link-forge vectors). If included, document the ONNX↔PyTorch drift note above.
  - `README.md` — how to bring the graph up, env, ports.
- `confgate/FINDINGS.md` — CF-1…CF-8 bootstrapped from `pinned_meta.json`, in the topo
  `### CF-N: <claim>` block format (`**Claim.** / **Strength:** / **Evidence:** /
  **Strongest counterargument:** / **Would be overturned by:**`).
- `confgate/HYPOTHESES.md` — CH-1…CH-6 in the `### CH-N:` block format
  (`**Priority:** / **Motivated by:** / **Test:** / **Requires:** / **Would change:** /
  **Blocks:**`), plus a `Next ID: CH-7` marker for the renumberer.
- **`[v1.1]` `pyproject.toml` — confirm-only, no edit.** Backend is **hatchling**;
  `packages = ["confgate"]` already excludes `research-graph/` + top-level `*.md`. Do
  **not** add a `[tool.setuptools…]` block (wrong backend). The guard is the test below.

**Architecture notes**
- New password (not topo's `topo_graph_dev`, not link-forge default). Store in memory.
- Vector dim 384 must match link-forge's MiniLM so `admit.py` copies embeddings rather
  than re-embedding.

**Tracer-bullet test (`tests/research_graph/test_phase0_graph.py`, integration tier)**
- `docker compose up -d` an ephemeral graph → apply `schema.cypher` → assert all
  constraints/indexes present (`SHOW CONSTRAINTS` count) and node count == 0.
- Parse `FINDINGS.md` → assert CF-1…CF-8 present with non-empty claims; parse
  `HYPOTHESES.md` → CH-1…CH-6 present.
- **Package-hygiene unit test** (`tests/test_packaging.py`, Docker-free): **`[v1.1]`
  `hatch build` (or `python -m build`) the wheel into a temp dir, `unzip -l`, assert the
  file set == the 13-file v0.1.1 baseline** (6 modules + 2 data JSON + 5 dist-info; no
  `research-graph/`, no `FINDINGS.md`/`HYPOTHESES.md`). Compare names only (ignore the
  dist-info version/hash bytes).

### Phase 1 — Relevance gate (`admit.py`) — `[v1.1]` discovery redesigned

**Deliverables**
- `confgate/research-graph/admit.py`
  - **Candidate discovery (v1.1):** `--from-sweep confgate` reads the **dated sweep JSON**
    `research-sweep.ts` wrote (authoritative arxiv-id list for the project). Fallback
    `--from-queue` joins `queue.db WHERE discord_channel_id='research-sweep:confgate'`.
    Also accepts an explicit `<arxiv-id …>` list. **Not** a graph-tag query (no such tag).
  - **`url → arxiv_id`:** clone the strict extractor from `research-graph-suggest.ts`
    (host must be `arxiv.org`, month ∈ 01–12, boundary-gated; strip version suffix);
    non-arxiv URLs get the `sha1(url)[:16]` synthetic id (mirrors enqueue-research-sweep).
  - For each candidate: resolve the `:Link` in link-forge **by URL** → pull
    title/description/keyConcepts/forgeScore + **copy `embedding[384]`**. Build CF/CH
    context index from `FINDINGS.md`+`HYPOTHESES.md` (grep `### CF-` / `### CH-` headers);
    run `relevance_check()` via `claude -p` with a lean-inclusive rubric →
    `{relevant: bool, relevance_note, which_CF_or_CH: [...]}`.
  - On admit: `MERGE (:Paper {arxiv_id})` in the confgate graph with
    `status:'pending_triage'`, `relevance_note`, copied `embedding`, `forge_score`, and
    `:TAGGED` edges to each CF/CH it touches (the **grouping seed**).
  - Idempotent (MERGE), re-runnable, `--dry-run`. Graceful-degrade if link-forge or the
    sweep JSON is missing (warn, skip — mirror bridge.py's degradation).
- `confgate/research-graph/bridge.py` — `resolve <arxiv>` → link-forge title+forgeScore
  (cloned, repoint to confgate `.env`; env var names already match).

**Tracer-bullet test (`tests/research_graph/test_phase1_admit.py`)**
- **`[v1.1]` fixture mirrors production discovery:** a temp **sweep-JSON fixture** + a
  seeded `:Link {url:'http://arxiv.org/abs/2406.18665', embedding:[…]}` in the ephemeral
  link-forge-shaped Neo4j (two-DB fixture) → run `admit.py --from-sweep confgate --dry-run`
  with a **stubbed** relevance fn (no live `claude -p` in CI) → assert a
  `:Paper {arxiv_id:'2406.18665', pending_triage}` with copied embedding and the right
  CF/CH `:TAGGED` edges would be written.
- Unit test the `url → arxiv_id` extractor: arxiv abs/pdf/versioned URLs → bare id;
  `arxiv.org.evil.com` → rejected → sha1 fallback.
- Unit test the rubric prompt builder: given CF/CH files, the context string contains all
  8 CF + 6 CH one-liners.

### Phase 2 — Triage briefs (`/confgate-triage` skill + paper-triage clone)

**Deliverables**
- `confgate/.claude/skills/confgate-triage/SKILL.md` — cloned from the `paper-triage`
  skill, repointed to `~/confgate/research-graph/briefs/`, CF/CH instead of F/H, and the
  YAML block emits **`CG-FE#`** experiments. Keeps: fresh subagent per paper (confirmation-
  bias defense, Ríos-García `2604.18805`), refutations-first ordering, headlines-only
  default context with explicit on-demand `Read` of CF bodies logged in the footer.
  **`[v1.1]` Keeps topo's behavior of NOT auto-promoting** — surfaces the brief path +
  the `promote_brief.py` command for human/agent review.
- Brief contract (`briefs/triage-YYYY-MM-DD-<arxiv>.md`) sections (matching the topo
  parser's `KNOWN_SECTIONS`):
  `## Refutations` → `## Direct connections to CF-N / CH-N` →
  `## Methodologies extracted` → `## Approaches & framings` →
  `## Datasets & benchmarks` → `## Implementation details worth capturing` →
  `## Replicable intermediates` → `## Cross-paper signals` →
  `## Proposed FutureExperiments` (YAML CG-FE blocks) →
  `## Proposed HYPOTHESES.md additions` (CH-N) →
  `## Proposed PAPER_INDEX.md classification` → `## New claims` →
  `## Sources consulted`.
- `CG-FE` YAML block schema (fields the topo parser validates): `id, pathway: CG,
  description, rationale, trigger, status: READY, priority, roi (1–10), cost,
  depends-on:[CF-N], would-update:[CF-N], triggered-by:[arxiv], relies-on:[premise]`.
- `confgate/research-graph/triage_pending.sh` — loop `/confgate-triage` over every
  `pending_triage` paper (parallel-3). **`[v1.1]` writes briefs only; promotion is a
  separate explicit step** (`promote_pending.sh` or manual), matching topo. Auto-promote
  is deferred to the v2 autopilot spec.

**Tracer-bullet test (`tests/research_graph/test_phase2_brief.py`, unit)**
- Golden-fixture brief (`tests/research_graph/fixtures/triage-sample.md`, the RouteLLM
  `2406.18665` dry-run from the audit) → assert the brief parser (shared with Phase 3)
  extracts ≥1 valid CG-FE block with all required fields, that `roi ∈ [1,10]`, and that
  `depends-on` references an existing CF-N.

### Phase 3 — Promotion + grouping (`promote_brief.py`, `premises.py`, `query.py`, `validate_claims.py`)

**Deliverables**
- `confgate/research-graph/promote_brief.py` — cloned. Parses YAML CG-FE → MERGE
  `:FutureExperiment` + `DEPENDS_ON_FINDING`/`WOULD_UPDATE`(→CF)/`TRIGGERED_BY`(→Paper)/
  `RELIES_ON`(→Premise) edges; inserts CH-N into `HYPOTHESES.md`; folds the deep-extraction
  subsections under a `PAPER_INDEX.md` entry; writes `(:Method|:Dataset)-[:USED_IN]->(:Paper)`;
  calls `bridge.py resolve`; **claims gate** (refuse if brief declares new `cg-*` claims and
  `validate_claims.py` mtime ≤ brief mtime); sets `:Paper{status:'graphed'}`; calls
  `generate_next_experiments.py`. Flags: `--dry-run`, `--update-existing`, `--no-renumber`.
  - **`[v1.1]` Clone surgery (mandatory before first run):**
    1. **Strip step 9** — the Redis publish to `topoconf:research:triaged` (no NGS bridge
       in confgate MVP). Remove the import + call.
    2. **Repoint step 8b** — `backfill_embeddings.embed_node()`. For MVP either disable
       (FE/Paper embeddings not needed for tag-grouping) or repoint to copy from the
       already-stored `:Paper.embedding`. Do **not** introduce a PyTorch embedder here
       silently (drift note).
    3. **Repoint the claims-gate path** — topo's `validate_claims.py` is at repo root;
       confgate's is at `confgate/research-graph/validate_claims.py`. Fix the path constant.
    4. Repoint all `bolt://…:7688` / `topo_graph_dev` defaults to the confgate `.env`.
- `confgate/research-graph/generate_next_experiments.py` — query READY CG-FE by
  `roi_score` desc → rewrite `confgate/NEXT_EXPERIMENTS.md` (the **grouping deliverable**,
  papers→levers→ranked experiments), ROI-tiered (CRITICAL≥9/HIGH≥7/MEDIUM≥5/LOW<5).
- `confgate/research-graph/premises.py` — seed confgate premises
  (`free-gate-is-ceiling`, `cross-domain-cert-infeasible`, `length-is-the-signal`,
  `curation-helps-distillation` [seed REFUTED — H-R], `preflight-promptlen-ceiling`);
  `refute/confirm` cascade-moots reliant CG-FE. (Deterministic mooting only.)
- `confgate/research-graph/query.py` — `novelty`, `pending`, `status-report`,
  `subgraph <CF>`, `future`, plus a `grouped` view (papers grouped by CF tag). Cloned,
  trimmed, repointed to `.env`.
- `confgate/research-graph/validate_claims.py` — seed with the 8 CF anchors as
  `kind="external"` REGISTERED entries (verbatim from `pinned_meta.json`); `cg-*` claim
  ids; smoke = all PASS/REGISTERED.
- `confgate/research-graph/update_status.py` — cloned (reverses MOOTED→READY).

**Tracer-bullet test (`tests/research_graph/test_phase3_promote.py`, integration)**
- Apply schema → seed CF-1…CF-8 `:Finding` nodes + premises → `promote_brief.py
  fixtures/triage-sample.md --dry-run` asserts the planned MERGEs; then **live** promote
  against the ephemeral graph → assert `:FutureExperiment{CG-FE1}` exists with edges to
  the right CF, `:Paper.status=='graphed'`, and `NEXT_EXPERIMENTS.md` regenerated
  non-empty. **`[v1.1]` also assert no Redis connection is attempted** (the surgery
  removed it) — e.g. monkeypatch/assert-not-called.
- Claims-gate negative test: a brief with a new `cg-*` claim and a stale
  `validate_claims.py` mtime → promote **refuses**.
- Premise cascade test: `premises.py refute free-gate-is-ceiling` → a CG-FE that
  `RELIES_ON` it flips to MOOTED; `update_status.py CG-FE1 READY` reverses it.

### Phase 4 — End-to-end grouping run + docs

**Deliverables**
- `confgate/.claude/research-sweep.yaml` — keyword groups keyed to CH-1…CH-6
  (`selective_prediction`, `llm_calibration_free`, `conformal_cross_domain`,
  `cascade_routing`, `domain_specialized_small_models`, `preflight_uncertainty`).
- One real end-to-end pass on local CPU: `research-sweep confgate` → `admit.py
  --from-sweep confgate` (live `claude -p`) → triage a small batch → promote → inspect
  `NEXT_EXPERIMENTS.md` + `query.py grouped`.
- `confgate/research-graph/CLAUDE.md` — agent orientation (mirror topo's), documenting
  the MVP boundary, the pull-model discovery, the clone-surgery list, and what's deferred
  to v2.
- Memory write + a `confgate/research-graph/STATE.md` handoff.

**Tracer-bullet test:** the Phase 4 PR is the integration of all prior tests + a smoke
`make e2e-dry` target that runs discovery(sweep-JSON fixture)→admit(stub)→promote(fixture)
with **zero network**.

---

## CI/CD

Mirror the link-forge two-tier pattern (service-container integration tier proven there,
commit `fb7bbcc`).

- **`.github/workflows/ci.yml`** (new — confgate has none today):
  - **`unit`** job (every push/PR, Docker-free): `pytest tests/` (existing 11-test package
    suite — must stay green) + `tests/test_packaging.py` + the Phase-1/2 unit tests +
    `ruff`.
  - **`integration`** job (every push/PR): GitHub Actions `services: neo4j:5.26-community`
    on dynamic port (env `NEO4J_BOLT_URL`), runs `tests/research_graph/` (Phases 0/1/3
    integration tests). Never binds the dev `:7689`/`:7687`. The Phase-1 two-DB fixture
    spins a **second** neo4j service (or a second DB) to stand in for link-forge.
- **Branch protection on `main`:** both jobs required green before merge. No direct pushes
  to `main`; one PR per phase (tracer-bullet gate).
- **Local mirror:** `make test` (unit) / `make test-int` (spins ephemeral compose graph) /
  `make e2e-dry`. Phase N is "done" only when its named test is green both locally and CI.
- **Secrets:** no passwords in the repo. `.env` gitignored, `.env.example` committed;
  CI Neo4j uses the workflow-provided service password, not the dev one.
- **Packaging guard in CI:** `test_packaging.py` fails the build if the wheel file list
  drifts from the 13-file v0.1.1 baseline — protects the shipped package from accidental
  tooling inclusion. **`[v1.1]` hatchling-based (`hatch build`), names-only diff.**

---

## Explicitly out of scope (→ v2 spec "confgate autopilot")

- Phase-2/3 **scriptgen** (`generate_recompute.py`) and **experiment execution** — confgate
  experiments need a model harness + likely H100 (RunPod), unlike topo's local-only rule.
- **systemd autopilot** services (`autopilot@{triage,scriptgen,experiment}`), `.autopilot/`
  trigger/budget/pause machinery, the `:9876` stream-deck endpoints, and **auto-promote**
  (`[v1.1]` MVP keeps manual promote).
- **Semantic `moot_sweep.py`** (MiniLM cosine + `claude -p` adjudication). MVP keeps only
  deterministic premise-cascade mooting.
- A link-forge-side automatic bridge (we use the decoupled `admit.py` pull model instead).
- **Redis / node-graph-substrate bridge** (`[v1.1]` the `topoconf:research:triaged`
  publish is stripped from the clone).
- Paper↔Finding **semantic search** (would require resolving the ONNX↔PyTorch MiniLM
  drift; MVP grouping is tag-based).

---

## Changelog (v1 → v1.1)

| # | v1 said | Reality (audited 2026-06-14) | v1.1 fix |
|---|---|---|---|
| **D1** | admit.py queries link-forge for `:Link` tagged `research-sweep:confgate:*` | No such tag on the graph node; provenance is in `queue.db`/sweep-JSON; `:Link` has no `arxiv` prop | Discovery reads the **sweep JSON** (or `queue.db`), clones the strict **url→arxiv** extractor, resolves `:Link` by URL |
| **D2** | Add `tool.setuptools.packages.find` exclude to keep tooling out of the wheel | Backend is **hatchling**; `packages=["confgate"]` is an allowlist that already excludes everything else | No `pyproject` edit; keep only the `unzip -l` guard test (hatchling build) |
| **D3** | requirements pins `sentence-transformers`; copy link-forge embeddings, hash-assert `759c3cd2…` | link-forge embeds via **ONNX `Xenova/...`** (PyTorch ST ≈0.999, not identical); the `759c3cd2` hash is a **sync-peer** gate, not the embedder | Papers **copy** link-forge vectors; ST optional + drift-noted; **no hash-assert** |
| **D4** | `triage_pending.sh` workers **auto-promote** inline | topo's skill deliberately separates triage from promote (human review) | MVP keeps **manual promote**; auto-promote deferred to v2 |
| **D4b** | clone `promote_brief.py` as-is | step 9 Redis-publishes; step 8b `embed_node()`; claims-gate path is repo-root | **Clone surgery**: strip Redis, repoint embed_node, repoint `validate_claims.py` path |

---

## Build order checklist

- [ ] **P0** graph up · schema applied · CF/CH bootstrapped · packaging guard (hatchling) green
- [ ] **P1** `admit.py` (sweep-JSON discovery + url→arxiv) + `bridge.py` · stubbed-relevance admit test green
- [ ] **P2** `/confgate-triage` skill (no auto-promote) · brief parser + golden-fixture test green
- [ ] **P3** `promote_brief.py` (surgery done) + `premises.py` + `query.py` + `validate_claims.py` + `update_status.py` ·
      promote/claims-gate/cascade tests green
- [ ] **P4** sweep config · live e2e pass · `NEXT_EXPERIMENTS.md` grouped output · docs
- [ ] CI `ci.yml` (unit + integration) green; `main` branch protection on

## Open questions for the build session (not blockers)

1. confgate graph password — generate fresh; OK to store in memory like topo's? **(unchanged)**
2. Sweep cadence — one-shot for MVP, or wire a cron later (deferred with autopilot)? **(unchanged)**
3. ~~admit.py copy embeddings vs re-embed~~ — **RESOLVED v1.1: copy `:Link.embedding` (no
   re-embed, no hash gate).** New residual: do we embed CF `:Finding` nodes at all for the
   MVP? Default **no** (grouping is tag-based); revisit if we add semantic search.
4. **`[v1.1]` new:** where exactly does `research-sweep.ts` write the dated sweep JSON?
   Confirm the path/glob for admit.py `--from-sweep` (else fall back to `queue.db`). Verify
   at P1 build time.
