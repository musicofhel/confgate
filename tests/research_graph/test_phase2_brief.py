"""Phase 2 tracer test — the triage-brief parser (UNIT, no Neo4j).

Exercises `research-graph/brief_parser.py`, the parser shared with Phase 3's
`promote_brief.py`. The golden fixture is a realistic RouteLLM `2406.18665` brief.

Asserts the parser:
  - extracts ≥1 valid CG-FE block with every required field,
  - validates `roi ∈ [1,10]`, status/priority vocab, and CG-FE id shape,
  - confirms each `depends-on` references an existing CF-N (from FINDINGS.md),
  - reads the byte-for-byte section order (CF/CH namespace), the CH-N hypothesis
    block, the PAPER_INDEX entry, and treats a `none` body as empty.

Pure-Python: imports only `brief_parser` (+ pyyaml). No graph deps, so it runs in
the Docker-free unit tier.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "research-graph"))

import brief_parser  # noqa: E402

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "triage-sample.md"


def test_fixture_exists():
    assert FIXTURE.exists(), f"golden fixture missing at {FIXTURE}"


def test_known_finding_ids_cover_cf1_to_cf8():
    ids = brief_parser.known_finding_ids()
    assert {f"CF-{n}" for n in range(1, 9)} <= ids


def test_parse_extracts_sections_in_namespace():
    parsed = brief_parser.parse_brief(FIXTURE)
    sections = parsed["sections"]
    # Byte-for-byte CF/CH-namespaced headings are present.
    assert "## Refutations" in sections
    assert "## Direct connections to CF-N / CH-N" in sections
    assert "## Proposed FutureExperiments" in sections
    # An embedded `## 2406.18665 — …` inside the PAPER_INDEX body is NOT split
    # into a new top-level section.
    assert "2406.18665" in parsed["paper_index_entry"]


def test_extracts_two_valid_cg_fe_blocks():
    parsed = brief_parser.parse_brief(FIXTURE)
    fes = parsed["future_experiments"]
    assert len(fes) >= 1, "expected at least one CG-FE block"
    assert len(fes) == 2, f"fixture declares two CG-FE blocks, got {len(fes)}"

    known = brief_parser.known_finding_ids()
    for fe in fes:
        errors = brief_parser.validate_future_experiment(fe, known_findings=known)
        assert not errors, f"CG-FE {fe.get('id')} invalid: {errors}"
        assert fe["pathway"] == "CG"
        assert 1 <= int(fe["roi"]) <= 10
        for dep in fe.get("depends-on", []):
            assert dep in known, f"depends-on {dep} not an existing CF-N"


def test_cg_fe_ids_are_well_formed():
    parsed = brief_parser.parse_brief(FIXTURE)
    ids = {fe["id"] for fe in parsed["future_experiments"]}
    assert ids == {"CG-FE57", "CG-FE58"}
    for fe_id in ids:
        assert brief_parser.FE_ID_RE.match(fe_id)


def test_hypothesis_block_and_methods_parsed():
    parsed = brief_parser.parse_brief(FIXTURE)
    assert len(parsed["hypotheses_blocks"]) == 1
    assert parsed["hypotheses_blocks"][0].startswith("### CH-57:")
    # Named-bullet method extraction (used by Phase 3's :Method edges).
    assert "Matrix-factorization router" in parsed["method_names"]


def test_none_section_treated_as_empty():
    parsed = brief_parser.parse_brief(FIXTURE)
    # "## New claims" body is literally "none" → no claim lines.
    assert parsed["new_claims_lines"] == []
    # "## Cross-paper signals" is "none worth flagging" → not a deep subsection.
    assert "### Cross-paper signals" not in parsed["deep_subsections"]


def test_validate_rejects_bad_roi_and_unknown_cf():
    bad = {
        "id": "CG-FE99",
        "pathway": "CG",
        "description": "x",
        "roi": 42,
        "depends-on": ["CF-99"],
    }
    errors = brief_parser.validate_future_experiment(
        bad, known_findings={"CF-1", "CF-2"}
    )
    assert any("roi out of [1,10]" in e for e in errors)
    assert any("unknown finding 'CF-99'" in e for e in errors)


def test_validate_rejects_wrong_pathway_and_status():
    bad = {
        "id": "CG-FE100",
        "pathway": "P11",
        "description": "x",
        "roi": 5,
        "status": "BOGUS",
        "priority": "URGENT",
    }
    errors = brief_parser.validate_future_experiment(bad)
    assert any("pathway must be 'CG'" in e for e in errors)
    assert any("invalid status" in e for e in errors)
    assert any("invalid priority" in e for e in errors)
