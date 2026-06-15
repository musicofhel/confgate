// =====================================================================
// confgate research graph schema (cloned + trimmed from topo, SPEC v1.2 P0)
// =====================================================================
// Run: cypher-shell -u neo4j -p <pw> -a bolt://localhost:7689 -f schema.cypher
//
// Dropped vs topo: Pathway / Experiment / Artifact timeline constraints+indexes
// (out of scope for the grouping MVP). Kept: the paper-triage + grouping core.
// Namespace: Findings=CF-N, Hypotheses=CH-N, FutureExperiments=CG-FE#.
// =====================================================================

// ---- Node uniqueness constraints ------------------------------------

CREATE CONSTRAINT finding_id IF NOT EXISTS
  FOR (f:Finding) REQUIRE f.id IS UNIQUE;

CREATE CONSTRAINT paper_arxiv IF NOT EXISTS
  FOR (p:Paper) REQUIRE p.arxiv_id IS UNIQUE;

CREATE CONSTRAINT tag_name IF NOT EXISTS
  FOR (t:Tag) REQUIRE t.name IS UNIQUE;

CREATE CONSTRAINT future_experiment_id IF NOT EXISTS
  FOR (fe:FutureExperiment) REQUIRE fe.id IS UNIQUE;

CREATE CONSTRAINT premise_id IF NOT EXISTS
  FOR (p:Premise) REQUIRE p.id IS UNIQUE;

CREATE CONSTRAINT method_key IF NOT EXISTS
  FOR (m:Method) REQUIRE m.key IS UNIQUE;

CREATE CONSTRAINT dataset_key IF NOT EXISTS
  FOR (d:Dataset) REQUIRE d.key IS UNIQUE;

// ---- Lookup indexes -------------------------------------------------

CREATE INDEX future_experiment_status IF NOT EXISTS
  FOR (fe:FutureExperiment) ON (fe.status);

CREATE INDEX future_experiment_roi IF NOT EXISTS
  FOR (fe:FutureExperiment) ON (fe.roi_score);

CREATE INDEX premise_status IF NOT EXISTS
  FOR (p:Premise) ON (p.status);

CREATE INDEX finding_status IF NOT EXISTS
  FOR (f:Finding) ON (f.status);

CREATE INDEX paper_year IF NOT EXISTS
  FOR (p:Paper) ON (p.year);

CREATE INDEX paper_status IF NOT EXISTS
  FOR (p:Paper) ON (p.status);

// ---- Vector indexes (384-dim all-MiniLM-L6-v2, matches link-forge) -

CREATE VECTOR INDEX paper_embedding_idx IF NOT EXISTS
  FOR (p:Paper) ON (p.embedding)
  OPTIONS {indexConfig: {
    `vector.dimensions`: 384,
    `vector.similarity_function`: 'cosine'
  }};

CREATE VECTOR INDEX finding_embedding_idx IF NOT EXISTS
  FOR (f:Finding) ON (f.embedding)
  OPTIONS {indexConfig: {
    `vector.dimensions`: 384,
    `vector.similarity_function`: 'cosine'
  }};

// ---- Fulltext indexes for RAG --------------------------------------

CREATE FULLTEXT INDEX finding_claims IF NOT EXISTS
  FOR (f:Finding) ON EACH [f.claim, f.strongest_counterargument];

CREATE FULLTEXT INDEX paper_relevance IF NOT EXISTS
  FOR (p:Paper) ON EACH [p.relevance_note, p.title];

CREATE FULLTEXT INDEX future_experiment_search IF NOT EXISTS
  FOR (fe:FutureExperiment) ON EACH [fe.description, fe.trigger, fe.rationale];

// =====================================================================
// Relationship vocabulary (documentation only — Neo4j is schema-free for
// relationships, so these are MERGE'd at write time by the tooling).
// =====================================================================
//
// Tagging (the GROUPING SEED — admit.py writes these):
//   (Paper)-[:TAGGED]->(Tag)         tag name = CF-N or CH-N it touches
//   (Finding)-[:TAGGED]->(Tag)
//
// Paper-to-finding relations (the value of the graph):
//   (Finding)-[:CORROBORATED_BY {their_model, their_benchmark, note}]->(Paper)
//   (Finding)-[:CONTRADICTED_BY {why, resolution}]->(Paper)
//   (Finding)-[:EXTENDED_BY {experiment_idea, actionable}]->(Paper)
//
// Future experiments (forward-looking levers to beat the gate):
//   (FutureExperiment)-[:TRIGGERED_BY {reason, their_method, their_result,
//     our_method, same, differs}]->(Paper)
//   (FutureExperiment)-[:DEPENDS_ON_FINDING {why}]->(Finding)
//   (FutureExperiment)-[:WOULD_UPDATE {if_positive, if_negative}]->(Finding)
//   (FutureExperiment)-[:BLOCKED_BY_EXPERIMENT]->(FutureExperiment)
//
// Methods / datasets extracted from papers:
//   (Method)-[:USED_IN]->(Paper)
//   (Dataset)-[:USED_IN]->(Paper)
//
// Premises + closure-by-adjacency (premises.py — deterministic moot only):
//   (:Premise {id, statement, status, refuted_by, reason, created_date,
//              status_date})  status: LIVE | REFUTED | CONFIRMED
//   (FutureExperiment)-[:RELIES_ON]->(Premise)
//     Refuting a premise cascade-MOOTs every open reliant FE (reversible:
//     update_status.py <id> READY).
//   (FutureExperiment)-[:MOOTED_BY {reason, date}]->(Premise|FutureExperiment)
//   (FutureExperiment)-[:ANSWERED_BY {reason, date}]->(Premise|FutureExperiment)
// =====================================================================
