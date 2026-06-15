# confgate research-graph

Standalone paper-triage pipeline for confgate, mirroring the topo-confidence
pattern: **sweep → admit → triage → promote → group**. Emits a ranked queue of
**FutureExperiments that could beat the free confidence gate** (drives confgate v0.2).

This tree is **sibling tooling** — it is NOT part of the `topo-confgate` pip
package (hatchling `packages = ["confgate"]` excludes it). See
`../SPEC_TRIAGE_PIPELINE_v1.2.md` for the full design.

## Graph

- **confgate's own graph:** standalone Neo4j, `bolt://localhost:7689` /
  `http://localhost:7476`. Zero coupling to topo's `:7688`.
- **link-forge substrate:** read `bolt://localhost:7687` **read-only** (papers,
  embeddings, forgeScore). We never write it.

## Bring it up

```bash
cd research-graph
cp .env.example .env          # then edit NEO4J_PASSWORD (a fresh one is already set on dev)
docker compose up -d          # neo4j:5.26-community on 7689/7476
# wait for healthy, then apply the schema:
cypher-shell -u neo4j -p "$NEO4J_PASSWORD" -a bolt://localhost:7689 -f schema.cypher
```

`.env` is **gitignored**; only `.env.example` is committed. No secrets in the repo.

## Namespace

| Concept | confgate |
|---|---|
| Findings (success factors) | `CF-N`  (`../FINDINGS.md`) |
| Hypotheses (levers) | `CH-N`  (`../HYPOTHESES.md`) |
| FutureExperiments | `CG-FE#` (pseudo-pathway `CG`) |
| Claims | `cg-*` |

## Status

Phase 0 (scaffolding + graph standup) — this commit. Phases 1–4 (admit, triage,
promote, e2e) per the SPEC.
