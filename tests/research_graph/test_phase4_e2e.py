"""Phase 4 tracer-bullet: the whole grouping MVP, end-to-end, ZERO network.

This is the integration of every prior phase into one hermetic chain:

    discover (sweep-JSON fixture)  →  Phase 1 admit.py
    admit    (STUB relevance fn)   →  :Paper{pending_triage} + :TAGGED CF/CH
    promote  (fixtures/triage-sample.md) → Phase 3 promote_brief.py
    group    (query.grouped_by_lever)    → RouteLLM under its CF/CH levers

No live `claude -p` (relevance is stubbed), no link-forge bolt (lf_driver=None,
resolve_papers monkeypatched to a no-op), no arxiv — the only running service is
the ephemeral Neo4j test container the integration tier already provides. So the
test is marked BOTH `integration` (it needs that graph) and `e2e_dry` (the
`make e2e-dry` smoke target selects it).

Repo writes (HYPOTHESES.md / PAPER_INDEX.md / NEXT_EXPERIMENTS.md) are redirected
to a throwaway $CONFGATE_REPO_ROOT, exactly like Phase 3, so a run never dirties
the real repo.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from tests.research_graph.graphutil import (
    REPO_ROOT,
    SCHEMA_CYPHER,
    split_cypher_statements,
)

RG = REPO_ROOT / "research-graph"
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "triage-sample.md"
ARXIV = "2406.18665"
ARXIV_URL = "https://arxiv.org/abs/2406.18665"

# Point the cloned scripts (admit, promote_brief, query, and the
# generate_next_experiments subprocess promote spawns) at the ephemeral TEST
# graph — never the dev :7689. Harmless when CONFGATE_TEST_* is unset (unit
# collection); done at import so query.py reads the right BOLT at its module top.
for _src, _dst in (
    ("CONFGATE_TEST_BOLT_URL", "NEO4J_BOLT_URL"),
    ("CONFGATE_TEST_USER", "NEO4J_USER"),
    ("CONFGATE_TEST_PASSWORD", "NEO4J_PASSWORD"),
):
    if os.environ.get(_src):
        os.environ[_dst] = os.environ[_src]

sys.path.insert(0, str(RG))


# --------------------------------------------------------------------------- #
# Stubs (the only things standing in for the network)                          #
# --------------------------------------------------------------------------- #

def _stub_relevance(cand, _ctx):
    """Stand in for the lean-inclusive `claude -p` gate. The RouteLLM brief names
    CF-3/CH-3 (the cascade) and CF-7/CF-1 (the pre-generation/generalization
    levers), so a lean-inclusive verdict tags all four (+ a bogus tag the gate
    filters); reject anything non-arxiv. No `claude -p` is ever spawned."""
    if cand.is_arxiv:
        return {
            "relevant": True,
            "relevance_note": "learned router touches the gate-ordered cascade",
            "which_CF_or_CH": ["CF-3", "ch-3", "CF-7", "CF-1", "BOGUS-9"],
        }
    return {"relevant": False, "relevance_note": "off-topic", "which_CF_or_CH": []}


def _write_sweep_fixture(tmp_path: Path) -> Path:
    """A dated sweep JSON exactly as research-sweep.ts would emit it."""
    sweep = [
        {"url": ARXIV_URL, "title": "RouteLLM", "abstract": "preference-learned cascade router", "year": 2024},
        {"url": "https://example.com/not-arxiv", "title": "junk", "year": 2024},
    ]
    (tmp_path / "research-sweep-confgate-2026-06-14.json").write_text(json.dumps(sweep))
    return tmp_path


def _repo_copy(tmp_path: Path) -> Path:
    for name in ("HYPOTHESES.md", "PAPER_INDEX.md"):
        (tmp_path / name).write_text((REPO_ROOT / name).read_text())
    return tmp_path


# --------------------------------------------------------------------------- #
# Graph bootstrap                                                              #
# --------------------------------------------------------------------------- #

CF_SEED = """
UNWIND range(1, 8) AS n
MERGE (f:Finding {id: 'CF-' + toString(n)})
SET f.claim = 'confgate finding CF-' + toString(n),
    f.strength = 'strong', f.status = 'ACTIVE'
"""


def _bootstrap(driver):
    with driver.session() as s:
        for stmt in split_cypher_statements(SCHEMA_CYPHER.read_text()):
            s.run(stmt)
        s.run(CF_SEED)


# --------------------------------------------------------------------------- #
# The end-to-end tracer                                                        #
# --------------------------------------------------------------------------- #

@pytest.mark.integration
@pytest.mark.e2e_dry
def test_sweep_to_grouped_end_to_end(clean_graph, tmp_path, monkeypatch):
    _bootstrap(clean_graph)
    repo = _repo_copy(tmp_path)
    sweep_dir = _write_sweep_fixture(tmp_path)
    monkeypatch.setenv("CONFGATE_REPO_ROOT", str(repo))

    import importlib

    import admit
    import promote_brief
    import query

    # promote_brief binds REPO from CONFGATE_REPO_ROOT at import time; an earlier
    # test in the suite may have imported it already (module cache), so reload to
    # re-read the env we just set — otherwise its writes leak into a stale tmp.
    importlib.reload(promote_brief)

    # --- stage 1: discovery (sweep JSON fixture, no link-forge) ---------------
    cands = admit.discover_from_sweep("confgate", str(sweep_dir))
    assert [c.arxiv_id for c in cands if c.is_arxiv] == [ARXIV]

    # --- stage 2: admit with a STUB relevance fn; lf_driver=None => no network -
    plans = admit.admit(
        cands, relevance_fn=_stub_relevance,
        rg_driver=clean_graph, lf_driver=None, dry_run=False,
    )
    admitted = [p for p in plans if p.action == "admit"]
    # bogus tag filtered, ch-3 upper-cased, sorted; non-arxiv row rejected.
    assert len(admitted) == 1 and admitted[0].tags == ["CF-1", "CF-3", "CF-7", "CH-3"]

    with clean_graph.session() as s:
        st = s.run("MATCH (p:Paper {arxiv_id:$a}) RETURN p.status AS st", a=ARXIV).single()
        assert st and st["st"] == "pending_triage"

    # --- stage 3: promote the triage brief (no bridge/link-forge resolve) ------
    monkeypatch.setattr(promote_brief, "resolve_papers", lambda *a, **k: None)
    brief = tmp_path / f"triage-2026-06-14-{ARXIV}.md"
    brief.write_text(FIXTURE.read_text())
    monkeypatch.setattr(sys, "argv", ["promote_brief.py", str(brief)])
    promote_brief.main()

    with clean_graph.session() as s:
        fe_ids = sorted(r["id"] for r in s.run(
            "MATCH (fe:FutureExperiment) RETURN fe.id AS id"))
        assert fe_ids == ["CG-FE1", "CG-FE2"], fe_ids
        # the admitted paper is the SAME node promote flipped to graphed.
        st = s.run("MATCH (p:Paper {arxiv_id:$a}) RETURN p.status AS st", a=ARXIV).single()
        assert st["st"] == "graphed"

    # --- stage 4: the grouping view the whole pipeline exists to produce -------
    rows = query.grouped_by_lever()
    by_lever = {r["lever"]: r for r in rows}

    # CF-3: RouteLLM tagged here AND the renumbered CG-FE1 depends on it.
    assert "CF-3" in by_lever, sorted(by_lever)
    cf3 = by_lever["CF-3"]
    assert ARXIV in [p["arxiv_id"] for p in cf3["papers"]]
    assert "CG-FE1" in [e["id"] for e in cf3["experiments"]]

    # CH-3: the paper is grouped under its open-lever tag too.
    assert "CH-3" in by_lever
    assert ARXIV in [p["arxiv_id"] for p in by_lever["CH-3"]["papers"]]

    # CF-1 / CF-7: CG-FE2 lands under the levers it would update.
    assert "CG-FE2" in [e["id"] for e in by_lever.get("CF-1", {"experiments": []})["experiments"]]
    assert "CG-FE2" in [e["id"] for e in by_lever.get("CF-7", {"experiments": []})["experiments"]]

    # NEXT_EXPERIMENTS.md was regenerated from the graph and names the FE.
    nxt = (repo / "NEXT_EXPERIMENTS.md").read_text()
    assert "CG-FE1" in nxt
