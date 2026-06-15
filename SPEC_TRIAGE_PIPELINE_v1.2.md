# SPEC — confgate Paper-Triage Pipeline (v1.2, "Grouping MVP")

**Status:** DRAFT — ready for build (audited ×2)
**Date:** 2026-06-14
**Supersedes:** `SPEC_TRIAGE_PIPELINE_v1.1.md` (v1 + v1.1 kept for history)
**Owner:** aaron
**Goal:** Stand up a paper-triage pipeline for `~/confgate` that mirrors the
`~/topo-confidence` pattern, so the link-forge corpus can be **swept → relevance-gated
→ triaged → grouped** against confgate's shipped success factors, and emit a ranked
queue of **FutureExperiments that could beat the free gate** (drive a confgate v0.2).

> **What changed in v1.2** — a second soup-to-nuts audit on 2026-06-14 cross-checked every
> v1.1 claim against the live topo scripts, the confgate repo, and the skill. v1.1's two
> big corrections held (Phase-2 brief sections match `KNOWN_SECTIONS` byte-for-byte; the
> hatchling/embedding/discovery fixes are right). The audit found **10 gaps** — 5
> load-bearing — fixed here. The biggest: **promote_brief.py's renumber() hard-crashes on
> confgate's `CH-` namespace** because the clone-surgery list never repointed the ID
> regexes. See [§ Changelog v1.1 → v1.2](#changelog-v11--v12) and inline **`[v1.2]`** markers.

## Locked decisions (from scoping)

| # | Decision | Choice |
|---|---|---|
| 1 | Graph topology | **New standalone Neo4j** — `confgate-research-graph`, `bolt://localhost:7689` / `http://localhost:7476`. Own `CF-`/`CH-`/`CG-FE` namespace. Zero coupling to topo's `:7688`. |
| 2 | Triage goal | **Experiments to beat the gate** — every brief proposes `:FutureExperiment` levers against CF-1…CF-8 (raise AUROC, beat cascade, crack the cross-domain cert wall, better base-swap). |
| 3 | Phase scope | **Grouping MVP first** — sweep → admit → triage → promote → group. **Deferred to a v2 spec:** scriptgen, experiment execution, systemd autopilot, semantic `moot_sweep`. |
| 4 | Code reuse | **Clone & adapt into `confgate/research-graph/`** — copy topo scripts, repoint paths/endpoints/namespace. confgate diverges freely; no edits to the live topo/link-forge pipeline. |

## Non-negotiable invariants

- **Do not touch the shipped package.** `confgate/` (the pip package, `topo-confgate` v0.1.1)
  and **its one existing test file `tests/test_confgate.py`** stay byte-stable. All new
  tooling lives in the **sibling** dir `confgate/research-graph/`; all new tests live under
  `tests/research_graph/` (plus the one Docker-free `tests/research_graph/test_packaging.py`).
  Both are excluded from the wheel/sdist. **`[v1.2]` "byte-stable" means the existing file
  is unchanged — adding sibling files under `tests/` is allowed (Gap 9).** The existing
  11-test `tests/test_confgate.py` suite must stay green at every phase boundary.
- **Do not edit link-forge's processor or the topo bridge.** confgate reads link-forge
  (`bolt://localhost:7687`) **read-only** and writes only its own graph (`:7689`). It
  also reads link-forge's **sweep output JSON / `queue.db`** read-only (see Phase 1).
  The research-sweep skill is already multi-project; we add a config, not code.
- **Numbers come from `confgate/data/pinned_meta.json`.** The CF-N findings are derived
  verbatim from the pinned anchors — never re-state a number that isn't in that file.
- **Local/CPU only for tooling.** Admission + triage are `claude -p` + Neo4j + MiniLM
  embeddings (CPU). No GPU. (Per `feedback-no-local-gpu-even-rescoring`; experiment
  *execution* is out of scope here anyway.)
- **`[v1.2]` No secrets in the repo, enforced not assumed.** confgate's current
  `.gitignore` does **not** list `.env` (Gap 2). Phase 0 **adds** `.env` and
  `research-graph/.env` to `.gitignore` as a first deliverable, then commits
  `.env.example` only.

---

## Ground-truth notes (verified by audit ×2, 2026-06-14)

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
  `discord_channel_id = 'research-sweep:<project>'`. **This is why admit.py pulls from the
  sweep output, not a graph tag (Defect 1, v1.1).**
- **link-forge Neo4j:** `bolt://localhost:7687`, user `neo4j`, env
  `LINK_FORGE_BOLT_URL/LINK_FORGE_USER/LINK_FORGE_PASSWORD` (dev default `link_forge_dev`).
- **`research-graph-suggest.ts`** (the topo bridge we are NOT cloning) is hard-wired to
  `~/topo-confidence` (`TOPO_CONFIDENCE_DIR` override) and runs admission **inline,
  push-model, from inside link-forge's processor** — a pattern confgate can't reuse
  without editing link-forge, hence the **pull-model admit.py**.

### topo scripts to clone (contracts confirmed)
- `promote_brief.py <brief> [--dry-run] [--update-existing] [--no-renumber]` — 9-step
  pipeline. FE YAML schema = exactly the `CG-FE` block in Phase 2. **Clone surgery
  required (5 items, see Phase 3 — `[v1.2]` item 5 added):** step 9 publishes to Redis
  `topoconf:research:triaged` (**strip**); step 8b calls
  `backfill_embeddings.embed_node()` (**repoint/disable**); claims gate calls
  `validate_claims.py` by path (**repoint**); bolt/password defaults (**repoint**); and
  **`[v1.2]` every namespace regex** — `renumber()` does
  `re.search(r"Next ID: H-(\d+)", …)` and `raise SystemExit('No "Next ID: H-N" line…')`,
  plus `F-`/`H-`/`P11-FE` ID patterns throughout (**repoint to `CF-`/`CH-`/`CG-FE`**).
  FE field `roi` validated ∈ [1,10] and stored as `fe.roi_score`; `status ∈ {READY,
  TRIGGERED,BLOCKED,COMPLETED,ABANDONED,MOOTED,ANSWERED}`; `priority ∈ {CRITICAL,HIGH,
  MEDIUM,LOW}`. **FE ids renumber by default** to contiguous from the graph-side
  `max(FE id)` (the renumber reads HYPOTHESES' `Next ID:` marker for H-N, and queries the
  graph for the FE max) — `--no-renumber` to keep brief ids verbatim.
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
- **`FINDINGS.md` finding block** the relevance gate greps (verified against topo's live
  file): a `**Strength key.**` preamble + a `**Numbering continues monotonically. Next ID:
  F-N.**` marker, then per finding `### F-N: <claim>` + **`**Claim.** / **Strength:** /
  **Evidence:** / **Controls passed:** / **Controls not yet run:** / **Strongest
  counterargument:** / **Would be overturned by:**`. **`[v1.2]` v1.1's Phase-0 field list
  dropped `Controls passed:`/`Controls not yet run:` and the CF Next-ID marker (Gap 6) —
  restored below.** **`HYPOTHESES.md` block**: a `**Next ID: H-N.**` marker + per
  hypothesis `### H-N:` + `**Priority:** / **Motivated by:** / **Test:** / **Requires:** /
  **Would change:** / **Blocks:**`.
- **`paper-triage` skill** (`~/.claude/skills/paper-triage/`) spawns a **fresh subagent
  per paper** (Ríos-García `2604.18805` confirmation-bias defense), writes Refutations
  **first**, loads only headline one-liners (not full bodies), and **deliberately does
  NOT auto-promote** — it surfaces the brief path + commands. **confgate keeps manual
  promote for the MVP (Defect 4, v1.1).**
- **`research-sweep` skill** (`~/.claude/skills/research-sweep/`) already multi-project:
  `research-sweep <project> [--dry-run]` → `npx tsx ~/link-forge/scripts/research-sweep.ts`
  reads `~/<project>/.claude/research-sweep.yaml`, hits arxiv/Semantic-Scholar/OpenAlex/HF,
  **writes a dated JSON of swept papers** and enqueues them. Cron-able, no MCP/session.

### confgate repo state (verified this session)
- Build backend is **hatchling**, not setuptools:
  `[tool.hatch.build.targets.wheel] packages = ["confgate"]` — an **allowlist**, so a
  sibling `research-graph/` and top-level `FINDINGS.md` are **already excluded**; no
  exclude stanza needed (Defect 2, v1.1).
- **Packaging-guard baseline** = the committed `dist/topo_confgate-0.1.1-py3-none-any.whl`
  — exactly **13 files**: `confgate/{__init__,certify,cli,gate,preflight,route}.py`,
  `confgate/data/{pinned_gates.json,pinned_meta.json}`, and
  `topo_confgate-0.1.1.dist-info/{METADATA,WHEEL,entry_points.txt,licenses/LICENSE,RECORD}`.
  The guard test diffs `unzip -l` names against this set.
- `pyproject.toml` also pins **`[tool.pytest.ini_options] testpaths = ["tests"]`** and a
  repo-wide **`[tool.ruff]`** (`target-version = "py310"`, `line-length = 99`). **`[v1.2]`
  Both matter for CI (Gaps 3 + 10) — see CI/CD.**
- `.gitignore` exists but **does NOT list `.env`** (`[v1.2]` Gap 2). `dev = ["pytest",
  "ruff"]` extra is already declared. 11 pure-unit tests in `tests/test_confgate.py`
  (some skip without `CONFGATE_REPO` caches). **No `.github/workflows/`. No `Makefile`**
  (`[v1.2]` Gap 5). Clean `main`, remote `musicofhel/confgate`.

---

## Architecture

### Data flow (MVP)

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
│    - resolve :Link in link-forge → title/abstract/keyConcepts/        │
│      forgeScore + copy embedding[384]   (match key: see v1.2 below)    │
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
confgate/research-graph/promote_brief.py   (clone, 5-item surgery per v1.2)
  - MERGE :FutureExperiment (CG-FE#) + TRIGGERED_BY / WOULD_UPDATE(CF) /
    DEPENDS_ON_FINDING / RELIES_ON(premise)
  - (:Method|:Dataset)-[:USED_IN]->(:Paper)
  - bridge.py resolve <arxiv> → link-forge forgeScore/title
  - claims gate (validate_claims.py mtime guard; repointed path)
  - set :Paper {status:'graphed'}; regenerate NEXT_EXPERIMENTS.md
  - [STRIPPED] Redis publish; [REPOINTED] embed_node, claims-path, bolt, ID regexes
        ▼
GROUPING OUTPUT:  PAPER_INDEX.md  +  NEXT_EXPERIMENTS.md (ROI-ranked CG-FE queue)
                  papers grouped by which CF-N success-factor they touch
```

**Why a confgate-side `admit.py` (pull) instead of a link-forge bridge (push)?** Topo's
admission runs *inside* link-forge's processor (`research-graph-suggest.ts`), hard-wired
to `~/topo-confidence`. Decision #4 forbids editing it. A standalone confgate admitter
that **reads** link-forge (graph + sweep output) and **writes** the confgate graph keeps
link-forge a shared forager/embedder, gives confgate full ownership of its perimeter, and
is the cleanest tracer-bullet boundary. Because the `research-sweep:*` provenance is in
`queue.db`/sweep-JSON and not on the `:Link` node, the candidate list is read from the
sweep's own output — the authoritative per-project set, carrying arxiv ids for free.
(Swept papers may *also* be admitted to topo by the existing bridge if they also match
topo's perimeter — harmless; the graphs are independent.)

**`[v1.2]` admit.py `:Link` match key (Gap 7).** Discovery yields **arxiv ids**, but
`:Link`'s merge key is **`url`**, and reconstructing `arxiv.org/abs/<id>` may not match the
stored form (`/pdf/` vs `/abs/`, version suffix, http/https). admit.py must therefore
resolve `:Link` by **arxiv-id-normalized match**, not exact-URL equality: run the same
strict `url → arxiv_id` extractor over candidate `:Link.url` values (or `CONTAINS <id>`),
and join on the bare id. Confirm at P1 build whether the sweep JSON carries the canonical
`url` (preferred) — folded into open-Q4.

### Embeddings — provenance (Defect 3, v1.1)

- **Papers:** admit.py **copies** `:Link.embedding` (384-dim) straight into
  `:Paper.embedding`. No re-embedding → Paper vectors are internally consistent and
  exactly match link-forge's space.
- **Findings (CF-N):** if we embed CF `:Finding` nodes for vector search, note that
  link-forge used the **ONNX `Xenova/all-MiniLM-L6-v2`** while a local
  `sentence-transformers all-MiniLM-L6-v2` is the **PyTorch** variant — same architecture,
  **near-identical but not bit-identical** vectors (cosine ≈ 0.999). For the MVP, grouping
  is **tag-based** (`:TAGGED` to CF/CH), not Paper↔Finding kNN, so this drift is inert.
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

> **`[v1.2]` This table is not just documentation — it is a build instruction.** Every
> `F-`/`H-`/`P11-FE`/`topoconf`/`EXP-` literal and regex in the cloned scripts (especially
> `promote_brief.py::renumber()`, `query.py`, `validate_claims.py`,
> `generate_next_experiments.py`) must be repointed, or the scripts hard-fail on the new
> namespace (Gap 1).

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
- **`[v1.2]` `.gitignore` — add `.env` and `research-graph/.env` FIRST (Gap 2).** Confirm
  with `git check-ignore research-graph/.env` before writing any secret.
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
  - `requirements.txt` — `neo4j`, `python-dotenv`, `pyyaml`. **`sentence-transformers` is
    OPTIONAL** (only if we embed Findings; Papers reuse copied link-forge vectors). If
    included, document the ONNX↔PyTorch drift note above.
  - `README.md` — how to bring the graph up, env, ports.
- `confgate/FINDINGS.md` — CF-1…CF-8 bootstrapped from `pinned_meta.json`, in the **full**
  topo block format **`[v1.2]` (Gap 6)**: a `**Strength key.**` preamble + a `**Numbering
  continues monotonically. Next ID: CF-9.**` marker, then per finding `### CF-N: <claim>`
  + `**Claim.** / **Strength:** / **Evidence:** / **Controls passed:** / **Controls not
  yet run:** / **Strongest counterargument:** / **Would be overturned by:**`.
- `confgate/HYPOTHESES.md` — CH-1…CH-6 in the `### CH-N:` block format
  (`**Priority:** / **Motivated by:** / **Test:** / **Requires:** / **Would change:** /
  **Blocks:**`), preceded by a `**Numbering continues monotonically. Next ID: CH-7.**`
  marker (read by the renumberer).
- **`[v1.2]` `confgate/PAPER_INDEX.md` — seed an empty stub (Gap 8).** promote_brief.py
  *appends/updates* PAPER_INDEX.md and `read_text()`s it; seed a header-only file so the
  first promote doesn't crash on a missing path.
- **`[v1.2]` `Makefile` (Gap 5)** — `test` (unit: `pytest -m "not integration" tests/` +
  `ruff check`), `test-int` (spins the ephemeral compose graph + `pytest -m integration
  tests/research_graph/`), `e2e-dry` (zero-network smoke). CI calls the same targets.
- **`pyproject.toml` — confirm-only, no edit.** Backend is **hatchling**; `packages =
  ["confgate"]` already excludes `research-graph/` + top-level `*.md`. **`[v1.2]` Add a
  pytest marker registration only** (`[tool.pytest.ini_options] markers = ["integration:
  needs a live Neo4j"]`) so `-m "not integration"` is clean and `testpaths=["tests"]` does
  not collect Neo4j tests into the unit job (Gap 3). This is config, not a package change;
  the wheel file-set is unaffected (guarded by the test below).

**Architecture notes**
- New password (not topo's `topo_graph_dev`, not link-forge default). Store in memory.
- Vector dim 384 must match link-forge's MiniLM so `admit.py` copies embeddings rather
  than re-embedding.

**Tracer-bullet test (`tests/research_graph/test_phase0_graph.py`, `@pytest.mark.integration`)**
- `docker compose up -d` an ephemeral graph → apply `schema.cypher` → assert all
  constraints/indexes present (`SHOW CONSTRAINTS` count) and node count == 0.
- Parse `FINDINGS.md` → assert CF-1…CF-8 present with non-empty claims **and the
  `Next ID: CF-9` marker**; parse `HYPOTHESES.md` → CH-1…CH-6 + `Next ID: CH-7`.
- **Package-hygiene unit test** (`tests/research_graph/test_packaging.py`, Docker-free,
  **NOT** `@integration`): **`[v1.2]` `hatch build` (or `python -m build`) the wheel into a
  temp dir, `unzip -l`, assert the file-name set == the 13-file v0.1.1 baseline** (6
  modules + 2 data JSON + 5 dist-info; no `research-graph/`, no `FINDINGS.md`/
  `HYPOTHESES.md`/`PAPER_INDEX.md`). Compare names only (ignore dist-info version/hash
  bytes). **`[v1.2]` placed under `tests/research_graph/` to keep `tests/test_confgate.py`
  byte-stable (Gap 9).**

### Phase 1 — Relevance gate (`admit.py`)

**Deliverables**
- `confgate/research-graph/admit.py`
  - **Candidate discovery:** `--from-sweep confgate` reads the **dated sweep JSON**
    `research-sweep.ts` wrote (authoritative arxiv-id list for the project). Fallback
    `--from-queue` joins `queue.db WHERE discord_channel_id='research-sweep:confgate'`.
    Also accepts an explicit `<arxiv-id …>` list. **Not** a graph-tag query (no such tag).
  - **`url → arxiv_id`:** clone the strict extractor from `research-graph-suggest.ts`
    (host must be `arxiv.org`, month ∈ 01–12, boundary-gated; strip version suffix);
    non-arxiv URLs get the `sha1(url)[:16]` synthetic id (mirrors enqueue-research-sweep).
  - **`[v1.2]` Resolve `:Link` by arxiv-id-normalized match, not exact URL (Gap 7):** apply
    the same extractor to `:Link.url` and join on the bare id (or `CONTAINS <id>`) →
    pull title/description/keyConcepts/forgeScore + **copy `embedding[384]`**.
  - Build CF/CH context index from `FINDINGS.md`+`HYPOTHESES.md` (grep `### CF-` / `### CH-`
    headers); run `relevance_check()` via `claude -p` with a lean-inclusive rubric →
    `{relevant: bool, relevance_note, which_CF_or_CH: [...]}`.
  - On admit: `MERGE (:Paper {arxiv_id})` in the confgate graph with
    `status:'pending_triage'`, `relevance_note`, copied `embedding`, `forge_score`, and
    `:TAGGED` edges to each CF/CH it touches (the **grouping seed**).
  - Idempotent (MERGE), re-runnable, `--dry-run`. Graceful-degrade if link-forge or the
    sweep JSON is missing (warn, skip — mirror bridge.py's degradation).
- `confgate/research-graph/bridge.py` — `resolve <arxiv>` → link-forge title+forgeScore
  (cloned, repoint to confgate `.env`; env var names already match).

**Tracer-bullet test (`tests/research_graph/test_phase1_admit.py`, `@integration`)**
- **Fixture mirrors production discovery:** a temp **sweep-JSON fixture** + a
  seeded `:Link {url:'http://arxiv.org/abs/2406.18665', embedding:[…]}` in a
  link-forge-shaped Neo4j (**`[v1.2]` a SECOND neo4j service/container — Community Edition
  has only one user DB, so "second DB" is impossible; Gap 4**) → run `admit.py --from-sweep
  confgate --dry-run` with a **stubbed** relevance fn (no live `claude -p` in CI) → assert a
  `:Paper {arxiv_id:'2406.18665', pending_triage}` with copied embedding and the right
  CF/CH `:TAGGED` edges would be written.
- Unit test (no Neo4j) the `url → arxiv_id` extractor: arxiv abs/pdf/versioned URLs → bare
  id; `arxiv.org.evil.com` → rejected → sha1 fallback. **`[v1.2]` also test the reverse
  match key**: a `:Link.url` of `/pdf/2406.18665v2` resolves to candidate `2406.18665`.
- Unit test the rubric prompt builder: given CF/CH files, the context string contains all
  8 CF + 6 CH one-liners.

### Phase 2 — Triage briefs (`/confgate-triage` skill + paper-triage clone)

**Deliverables**
- `confgate/.claude/skills/confgate-triage/SKILL.md` — cloned from the `paper-triage`
  skill, repointed to `~/confgate/research-graph/briefs/`, CF/CH instead of F/H, and the
  YAML block emits **`CG-FE#`** experiments. Keeps: fresh subagent per paper (confirmation-
  bias defense, Ríos-García `2604.18805`), refutations-first ordering, headlines-only
  default context with explicit on-demand `Read` of CF bodies logged in the footer.
  **Keeps topo's behavior of NOT auto-promoting** — surfaces the brief path + the
  `promote_brief.py` command for human/agent review.
- Brief contract (`briefs/triage-YYYY-MM-DD-<arxiv>.md`) sections — **verified byte-for-byte
  against the topo parser's `KNOWN_SECTIONS` (only F-N/H-N → CF-N/CH-N)**:
  `## Refutations` → `## Direct connections to CF-N / CH-N` →
  `## Methodologies extracted` → `## Approaches & framings` →
  `## Datasets & benchmarks` → `## Implementation details worth capturing` →
  `## Replicable intermediates` → `## Cross-paper signals` →
  `## Proposed FutureExperiments` (YAML CG-FE blocks) →
  `## Proposed HYPOTHESES.md additions` (CH-N) →
  `## Proposed PAPER_INDEX.md classification` → `## New claims` →
  `## Sources consulted`. (Empty sections write `none` — the parser treats a body whose
  first line starts with `none` as empty, so don't invent filler.)
- `CG-FE` YAML block schema (fields the topo parser validates): `id, pathway: CG,
  description, rationale, trigger, status: READY, priority, roi (1–10), cost,
  depends-on:[CF-N], would-update:[CF-N], triggered-by:[arxiv], relies-on:[premise]`.
- `confgate/research-graph/triage_pending.sh` — loop `/confgate-triage` over every
  `pending_triage` paper (parallel-3). **Writes briefs only; promotion is a separate
  explicit step** (`promote_pending.sh` or manual), matching topo. Auto-promote is deferred
  to the v2 autopilot spec.

**Tracer-bullet test (`tests/research_graph/test_phase2_brief.py`, unit — no Neo4j)**
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
  - **Clone surgery (mandatory before first run) — `[v1.2]` now 5 items:**
    1. **Strip step 9** — the Redis publish to `topoconf:research:triaged` (no NGS bridge
       in confgate MVP). Remove the import + call.
    2. **Repoint step 8b** — `backfill_embeddings.embed_node()`. For MVP either disable
       (FE/Paper embeddings not needed for tag-grouping) or repoint to copy from the
       already-stored `:Paper.embedding`. Do **not** introduce a PyTorch embedder here
       silently (drift note).
    3. **Repoint the claims-gate path** — topo's `validate_claims.py` is at repo root;
       confgate's is at `confgate/research-graph/validate_claims.py`. Fix the path constant.
    4. **Repoint bolt/password** — all `bolt://…:7688` / `topo_graph_dev` defaults to the
       confgate `.env`.
    5. **`[v1.2]` Repoint every namespace regex (Gap 1, load-bearing).** `renumber()` does
       `re.search(r"Next ID: H-(\d+)", …)` against `HYPOTHESES.md` and
       `raise SystemExit('No "Next ID: H-N" line…')` if absent → change to `CH-`. Also the
       graph-side FE-max query and any `F-`/`H-`/`P11-FE` ID patterns across
       `promote_brief.py`/`query.py`/`generate_next_experiments.py`/`validate_claims.py` →
       `CF-`/`CH-`/`CG-FE`. **Without this, the first promote crashes.**
- `confgate/research-graph/generate_next_experiments.py` — query READY CG-FE by
  `roi_score` desc → rewrite `confgate/NEXT_EXPERIMENTS.md` (the **grouping deliverable**,
  papers→levers→ranked experiments), ROI-tiered (CRITICAL≥9/HIGH≥7/MEDIUM≥5/LOW<5).
- `confgate/research-graph/premises.py` — seed confgate premises
  (`free-gate-is-ceiling`, `cross-domain-cert-infeasible`, `length-is-the-signal`,
  `curation-helps-distillation` [seed REFUTED — H-R], `preflight-promptlen-ceiling`);
  `refute/confirm` cascade-moots reliant CG-FE. (Deterministic mooting only.)
- `confgate/research-graph/query.py` — `novelty`, `pending`, `status-report`,
  `subgraph <CF>`, `future`, plus a `grouped` view (papers grouped by CF tag). Cloned,
  trimmed, repointed to `.env` (+ namespace regexes per surgery item 5).
- `confgate/research-graph/validate_claims.py` — seed with the 8 CF anchors as
  `kind="external"` REGISTERED entries (verbatim from `pinned_meta.json`); `cg-*` claim
  ids; smoke = all PASS/REGISTERED.
- `confgate/research-graph/update_status.py` — cloned (reverses MOOTED→READY).

**Tracer-bullet test (`tests/research_graph/test_phase3_promote.py`, `@integration`)**
- Apply schema → seed CF-1…CF-8 `:Finding` nodes + premises → `promote_brief.py
  fixtures/triage-sample.md --dry-run` asserts the planned MERGEs; then **live** promote
  against the ephemeral graph → assert `:FutureExperiment{CG-FE1}` exists with edges to
  the right CF, `:Paper.status=='graphed'`, and `NEXT_EXPERIMENTS.md` regenerated
  non-empty. **Also assert no Redis connection is attempted** (surgery item 1) — e.g.
  monkeypatch/assert-not-called.
- **`[v1.2]` Namespace-regression test**: promote against the seeded confgate `CH-`
  `HYPOTHESES.md` succeeds (i.e. the renumber repoint is real — it would `SystemExit` on an
  unported clone).
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
  the MVP boundary, the pull-model discovery, the 5-item clone-surgery list, and what's
  deferred to v2.
- Memory write + a `confgate/research-graph/STATE.md` handoff.

**Tracer-bullet test:** the Phase 4 PR is the integration of all prior tests + the
`make e2e-dry` target that runs discovery(sweep-JSON fixture)→admit(stub)→promote(fixture)
with **zero network**.

---

## CI/CD

Mirror the link-forge two-tier pattern (service-container integration tier proven there,
commit `fb7bbcc`).

- **`.github/workflows/ci.yml`** (new — confgate has none today):
  - **`unit`** job (every push/PR, Docker-free): **`[v1.2]` `make test`** =
    `pytest -m "not integration" tests/` (existing 11-test package suite + the Docker-free
    `test_packaging.py` + Phase-1/2 unit tests) + `ruff check`. The `-m "not integration"`
    selector is **required** because `pyproject` pins `testpaths=["tests"]`, so a bare
    `pytest` would otherwise collect the Neo4j tests (Gap 3).
  - **`integration`** job (every push/PR): GitHub Actions
    `services: { neo4j-main: neo4j:5.26-community, neo4j-linkforge: neo4j:5.26-community }`
    on dynamic ports (env `NEO4J_BOLT_URL` / `LINK_FORGE_BOLT_URL`), runs
    `pytest -m integration tests/research_graph/`. **`[v1.2]` Two SEPARATE neo4j services**
    — Community Edition is single-user-DB, so the link-forge stand-in is its own
    container, never a second DB in one instance (Gap 4). Never binds the dev
    `:7689`/`:7687`.
- **`[v1.2]` ruff scope (Gap 10):** `[tool.ruff]` is repo-wide (`line-length = 99`,
  `py310`). The cloned topo scripts under `research-graph/` **must pass that config** (run
  `ruff check --fix research-graph/` after each clone) or be added to ruff's `exclude`. Do
  this in the same PR that adds each script so the unit job stays green.
- **Branch protection on `main`:** both jobs required green before merge. No direct pushes
  to `main`; one PR per phase (tracer-bullet gate).
- **Local mirror = the same `Makefile` targets** CI calls: `make test` / `make test-int` /
  `make e2e-dry`. Phase N is "done" only when its named test is green both locally and CI.
- **Secrets:** no passwords in the repo. `.env` + `research-graph/.env` gitignored (added
  Phase 0), `.env.example` committed; CI Neo4j uses the workflow-provided service password,
  not the dev one.
- **Packaging guard in CI:** `tests/research_graph/test_packaging.py` fails the build if the
  wheel file list drifts from the 13-file v0.1.1 baseline — protects the shipped package
  from accidental tooling inclusion. hatchling-based (`hatch build`), names-only diff.

---

## Explicitly out of scope (→ v2 spec "confgate autopilot")

- Phase-2/3 **scriptgen** (`generate_recompute.py`) and **experiment execution** — confgate
  experiments need a model harness + likely H100 (RunPod), unlike topo's local-only rule.
- **systemd autopilot** services (`autopilot@{triage,scriptgen,experiment}`), `.autopilot/`
  trigger/budget/pause machinery, the `:9876` stream-deck endpoints, and **auto-promote**
  (MVP keeps manual promote).
- **Semantic `moot_sweep.py`** (MiniLM cosine + `claude -p` adjudication). MVP keeps only
  deterministic premise-cascade mooting.
- A link-forge-side automatic bridge (we use the decoupled `admit.py` pull model instead).
- **Redis / node-graph-substrate bridge** (the `topoconf:research:triaged` publish is
  stripped from the clone).
- Paper↔Finding **semantic search** (would require resolving the ONNX↔PyTorch MiniLM
  drift; MVP grouping is tag-based).

---

## Changelog (v1.1 → v1.2)

Found by the second audit (2026-06-14), each verified against live source.

| # | Sev | v1.1 said / omitted | Reality (audited) | v1.2 fix |
|---|---|---|---|---|
| **G1** | 🔴 | Clone-surgery list = 4 items (Redis, embed_node, claims-path, bolt) | `promote_brief.py::renumber()` reads `re.search(r"Next ID: H-(\d+)")` + `SystemExit('No "Next ID: H-N"…')`, plus `F-/H-/P11-FE` regexes — **hard-crashes on confgate's `CH-`** | **Surgery item 5**: repoint every namespace regex `F-/H-/P11-FE` → `CF-/CH-/CG-FE`; + namespace-regression test |
| **G2** | 🔴 | "`.env` gitignored" (assumed) | confgate `.gitignore` has `.venv/`/`venv/` but **no `.env`** → secret-leak risk | Phase 0 **adds** `.env` + `research-graph/.env` to `.gitignore` first; `git check-ignore` assert |
| **G3** | 🔴 | Two CI jobs named, split mechanism unspecified | `pyproject` pins `testpaths=["tests"]` → bare `pytest` in the unit job collects+fails the Neo4j tests | Register `@pytest.mark.integration`; unit job runs `-m "not integration"` |
| **G4** | 🔴 | Phase-1 fixture / CI "two-DB fixture (or a second DB)" | Neo4j **Community = one user DB**; a second DB in one instance is impossible | link-forge stand-in = a **second neo4j service/container** (two services in CI) |
| **G5** | 🔴 | CI references `make test/test-int/e2e-dry` | confgate has **no Makefile** and no phase creates one | **Add `Makefile`** (Phase 0) with those targets; CI calls the same |
| **G6** | 🟡 | Phase-0 CF block dropped `Controls passed:`; no CF Next-ID | topo finding block has `Controls passed:` + `Controls not yet run:` + a `Next ID: F-N` marker + `Strength key.` preamble | Restore full field set + `Next ID: CF-9` marker |
| **G7** | 🟡 | admit resolves `:Link` "by URL" | discovery yields **arxiv ids**; `arxiv.org/abs/<id>` may not match stored `:Link.url` (pdf/version/scheme) | Resolve by **arxiv-id-normalized match**; confirm sweep-JSON carries `url` (open-Q4) |
| **G8** | 🟡 | PAPER_INDEX.md never bootstrapped | promote appends/updates + `read_text()`s it → crash if absent | Phase 0 seeds an empty `PAPER_INDEX.md` stub |
| **G9** | 🟢 | "`tests/` byte-stable" vs adding test files | shipped suite is one file `tests/test_confgate.py` | Invariant reworded: that file unchanged; new tests under `tests/research_graph/` |
| **G10** | 🟢 | `ruff` in CI, scope unstated | `[tool.ruff]` is repo-wide (line-length 99) → cloned scripts may fail lint | `ruff check --fix research-graph/` per clone, or add to `exclude` |

(For the v1 → v1.1 changes — D1 discovery redesign, D2 hatchling, D3 embedding copy, D4
manual-promote — see `SPEC_TRIAGE_PIPELINE_v1.1.md § Changelog`.)

---

## Build order checklist

- [ ] **P0** `.gitignore` `.env` guard · graph up · schema applied · CF/CH/PAPER_INDEX
      bootstrapped (full field set + Next-IDs) · `Makefile` · pytest `integration` marker ·
      packaging guard (hatchling) green
- [ ] **P1** `admit.py` (sweep-JSON discovery + url→arxiv + id-normalized `:Link` match) +
      `bridge.py` · stubbed-relevance admit test green (two-service fixture)
- [ ] **P2** `/confgate-triage` skill (no auto-promote) · brief parser + golden-fixture test green
- [ ] **P3** `promote_brief.py` (**5-item surgery incl. namespace regexes**) + `premises.py`
      + `query.py` + `validate_claims.py` + `update_status.py` ·
      promote/namespace-regression/claims-gate/cascade tests green
- [ ] **P4** sweep config · live e2e pass · `NEXT_EXPERIMENTS.md` grouped output · docs
- [ ] CI `ci.yml` (unit `-m "not integration"` + integration two-service) green;
      `main` branch protection on

## Open questions for the build session (not blockers)

1. confgate graph password — generate fresh; OK to store in memory like topo's? **(unchanged)**
2. Sweep cadence — one-shot for MVP, or wire a cron later (deferred with autopilot)? **(unchanged)**
3. ~~admit.py copy embeddings vs re-embed~~ — **RESOLVED v1.1: copy `:Link.embedding`.**
   Residual: embed CF `:Finding` nodes for the MVP? Default **no** (grouping is tag-based).
4. **`[v1.2]` expanded:** where does `research-sweep.ts` write the dated sweep JSON
   (`LINK_FORGE_SWEEP_DIR` path/glob) **and does that JSON carry the canonical `url`** (vs
   only arxiv ids)? Needed for both `--from-sweep` discovery and the `:Link` match key
   (Gap 7). Else fall back to `queue.db`. Verify at P1 build time.
