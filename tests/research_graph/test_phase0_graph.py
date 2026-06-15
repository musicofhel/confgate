"""Phase 0 tracer-bullet: schema stands up clean + CF/CH bootstrap parses.

Two tiers:
  - markdown-parse tests (Docker-free, run in the unit job): FINDINGS/HYPOTHESES.
  - schema test (@integration, needs Neo4j): apply schema.cypher, assert the
    constraint/index set is present and the graph is empty.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.research_graph.graphutil import SCHEMA_CYPHER, split_cypher_statements

REPO_ROOT = Path(__file__).resolve().parents[2]
FINDINGS = REPO_ROOT / "FINDINGS.md"
HYPOTHESES = REPO_ROOT / "HYPOTHESES.md"

# Constraints declared in schema.cypher (trimmed clone — no Pathway/Experiment).
EXPECTED_CONSTRAINTS = 7
EXPECTED_VECTOR_INDEXES = {"paper_embedding_idx", "finding_embedding_idx"}
EXPECTED_FULLTEXT_INDEXES = {"finding_claims", "paper_relevance", "future_experiment_search"}


# --------------------------- unit tier (no Docker) ---------------------------

def test_findings_bootstrap_cf1_through_cf8():
    text = FINDINGS.read_text()
    for n in range(1, 9):
        m = re.search(rf"^### CF-{n}: (.+)$", text, re.MULTILINE)
        assert m, f"CF-{n} heading missing from FINDINGS.md"
        assert m.group(1).strip(), f"CF-{n} has an empty claim line"
    # No CF-9 yet, and the monotonic Next-ID marker the renumberer reads.
    assert "Next ID: CF-9" in text, "FINDINGS.md must carry the 'Next ID: CF-9' marker"
    assert "### CF-9:" not in text, "CF-9 should not exist yet"


def test_findings_full_field_set():
    """Each CF block must carry the full topo field set (Gap 6)."""
    text = FINDINGS.read_text()
    blocks = re.split(r"^### CF-\d+:", text, flags=re.MULTILINE)[1:]
    assert len(blocks) == 8
    required = [
        "**Claim.**",
        "**Strength:**",
        "**Evidence:**",
        "**Controls passed:**",
        "**Controls not yet run:**",
        "**Strongest counterargument:**",
        "**Would be overturned by:**",
    ]
    for i, block in enumerate(blocks, start=1):
        for field in required:
            assert field in block, f"CF-{i} missing {field}"


def test_hypotheses_bootstrap_ch1_through_ch6():
    text = HYPOTHESES.read_text()
    for n in range(1, 7):
        assert re.search(rf"^### CH-{n}:", text, re.MULTILINE), f"CH-{n} missing"
    assert "Next ID: CH-7" in text, "HYPOTHESES.md must carry the 'Next ID: CH-7' marker"
    assert "### CH-7:" not in text


def test_schema_file_parses_into_statements():
    stmts = split_cypher_statements(SCHEMA_CYPHER.read_text())
    creates = [s for s in stmts if s.upper().startswith("CREATE")]
    assert len(creates) >= EXPECTED_CONSTRAINTS + 3, "schema lost statements during clone"


# --------------------------- integration tier --------------------------------

@pytest.mark.integration
def test_schema_applies_clean(clean_graph):
    driver = clean_graph
    stmts = split_cypher_statements(SCHEMA_CYPHER.read_text())
    with driver.session() as session:
        for stmt in stmts:
            session.run(stmt)

        n_constraints = session.run(
            "SHOW CONSTRAINTS YIELD name RETURN count(*) AS c"
        ).single()["c"]
        assert n_constraints == EXPECTED_CONSTRAINTS, (
            f"expected {EXPECTED_CONSTRAINTS} constraints, got {n_constraints}"
        )

        index_names = {
            rec["name"] for rec in session.run("SHOW INDEXES YIELD name RETURN name")
        }
        assert EXPECTED_VECTOR_INDEXES <= index_names, "vector indexes missing"
        assert EXPECTED_FULLTEXT_INDEXES <= index_names, "fulltext indexes missing"

        node_count = session.run("MATCH (n) RETURN count(n) AS c").single()["c"]
        assert node_count == 0, "fresh graph must be empty after schema apply"
