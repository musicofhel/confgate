"""Unit guard for seed_findings.py (pure parse, no graph).

The grouping experiment-side join needs CF :Finding nodes; seed_findings.py
MERGEs one per FINDINGS.md `### CF-N:` header. This checks the parser sees all
eight CF findings with non-empty claims — the graph MERGE itself is exercised by
the live `make seed` step and the e2e tracer's CF_SEED.
"""
from __future__ import annotations

import sys

from tests.research_graph.graphutil import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "research-graph"))

import seed_findings  # noqa: E402  (after the sys.path shim)


def test_parse_findings_covers_cf1_through_cf8():
    findings = seed_findings.parse_findings()
    ids = [fid for fid, _ in findings]
    assert ids == [f"CF-{n}" for n in range(1, 9)], ids
    assert all(claim.strip() for _, claim in findings), "every CF finding has a claim"
