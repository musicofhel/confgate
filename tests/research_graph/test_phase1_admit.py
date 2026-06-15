"""Phase 1 tracer-bullet: the relevance gate (admit.py).

Two tiers:
  - unit (Docker-free, no neo4j): the strict url->arxiv extractor, the Gap-7
    reverse match key, sweep-JSON discovery (newest-wins), the CF/CH context
    builder, and the rubric prompt builder.
  - integration (@integration, two neo4j containers — Gap 4): seed a
    link-forge-shaped :Link in the link-forge stand-in + a temp sweep-JSON
    fixture, run admit() with a STUBBED relevance fn (no live `claude -p`),
    and assert the right :Paper / :TAGGED plan — first --dry-run (writes
    nothing), then a real write (idempotent).
"""
from __future__ import annotations

import json
import sys

import pytest

from tests.research_graph.graphutil import REPO_ROOT

# research-graph/ is a flat script dir, not a package. Put it on sys.path so we
# can import admit (which itself imports bridge from the same dir).
sys.path.insert(0, str(REPO_ROOT / "research-graph"))

import admit  # noqa: E402  (after the sys.path shim above)

ARXIV = "2406.18665"
ARXIV_URL = "https://arxiv.org/abs/2406.18665"


# --------------------------- unit tier (no Docker) ---------------------------

def test_extract_arxiv_id_variants():
    assert admit.extract_arxiv_id("https://arxiv.org/abs/2406.18665") == ARXIV
    assert admit.extract_arxiv_id("http://arxiv.org/pdf/2406.18665") == ARXIV
    assert admit.extract_arxiv_id("http://arxiv.org/pdf/2406.18665v2") == ARXIV  # version stripped
    assert admit.extract_arxiv_id("https://export.arxiv.org/abs/2406.18665") == ARXIV  # subdomain ok
    # host gate: arxiv-shaped substring on a non-arxiv host is rejected.
    assert admit.extract_arxiv_id("https://arxiv.org.evil.com/abs/2406.18665") is None
    assert admit.extract_arxiv_id("https://example.com/papers/2406.18665.html") is None
    # invalid month (13) rejected.
    assert admit.extract_arxiv_id("https://arxiv.org/abs/2413.18665") is None


def test_synthetic_id_for_non_arxiv():
    url = "https://openreview.net/forum?id=abc"
    assert admit.extract_arxiv_id(url) is None
    sid = admit.candidate_id(url)
    assert len(sid) == 16 and sid.isalnum()


def test_link_matches_candidate_reverse_key():
    # Gap 7: a stored /pdf/<id>v2 url resolves to the bare candidate id.
    assert admit.link_matches_candidate("http://arxiv.org/pdf/2406.18665v2", ARXIV)
    assert admit.link_matches_candidate("http://arxiv.org/abs/2406.18665", ARXIV)
    # a different (longer) id must NOT match.
    assert not admit.link_matches_candidate("http://arxiv.org/abs/2406.186650", ARXIV)
    # non-arxiv host never matches.
    assert not admit.link_matches_candidate("https://example.com/2406.18665", ARXIV)


def test_discover_from_sweep_newest_wins_and_extracts_ids(tmp_path):
    newest = [
        {"url": ARXIV_URL, "title": "RouteLLM", "abstract": "cascade", "year": 2024},
        {"url": "https://example.com/not-arxiv", "title": "junk", "year": 2024},
    ]
    (tmp_path / "research-sweep-confgate-2026-06-14.json").write_text(json.dumps(newest))
    # an OLDER file with different content — must be ignored (newest wins).
    (tmp_path / "research-sweep-confgate-2026-01-01.json").write_text(json.dumps([]))
    # a DIFFERENT project — must not leak in.
    (tmp_path / "research-sweep-other-2026-06-14.json").write_text(json.dumps([{"url": ARXIV_URL}]))

    cands = admit.discover_from_sweep("confgate", str(tmp_path))
    assert len(cands) == 2
    assert cands[0].arxiv_id == ARXIV and cands[0].is_arxiv
    assert not cands[1].is_arxiv and len(cands[1].arxiv_id) == 16


def test_discover_from_sweep_missing_dir_is_graceful(tmp_path):
    assert admit.discover_from_sweep("confgate", str(tmp_path / "nope")) == []


def test_context_builder_has_all_cf_and_ch():
    ctx = admit.build_cf_ch_context()
    for n in range(1, 9):
        assert f"CF-{n}:" in ctx, f"CF-{n} missing from context"
    for n in range(1, 7):
        assert f"CH-{n}:" in ctx, f"CH-{n} missing from context"


def test_rubric_prompt_includes_context_and_paper():
    cand = admit.Candidate(arxiv_id=ARXIV, url=ARXIV_URL, title="RouteLLM", abstract="cascade routing")
    prompt = admit.build_rubric_prompt(cand, admit.build_cf_ch_context())
    assert "CF-1:" in prompt and "CH-6:" in prompt
    assert "RouteLLM" in prompt
    assert "Lean INCLUSIVE" in prompt  # the lean-inclusive instruction is present


def test_known_tag_ids_namespace():
    ids = admit.known_tag_ids()
    assert {"CF-1", "CF-8", "CH-1", "CH-6"} <= ids
    assert "CF-9" not in ids and "CH-7" not in ids


# --------------------------- integration tier --------------------------------

_EMBEDDING = [round(0.001 * i, 4) for i in range(384)]


def _seed_linkforge(driver, url=ARXIV_URL, forge=7.5):
    with driver.session() as s:
        s.run(
            "CREATE (l:Link {url:$url, title:$t, forgeScore:$f, embedding:$e})",
            url=url, t="RouteLLM: cascade routing", f=forge, e=_EMBEDDING,
        )


def _stub_relevance(cand, _ctx):
    """Admit arxiv papers (tag CF-3/CH-3 + a bogus tag to test filtering); reject the rest."""
    if cand.is_arxiv:
        return {"relevant": True, "relevance_note": "cascade routing touches the gate-ordered cascade",
                "which_CF_or_CH": ["CF-3", "ch-3", "BOGUS-9"]}
    return {"relevant": False, "relevance_note": "not on-topic", "which_CF_or_CH": []}


def _sweep_fixture(tmp_path):
    sweep = [
        {"url": ARXIV_URL, "title": "RouteLLM", "abstract": "cascade", "year": 2024},
        {"url": "https://example.com/not-arxiv", "title": "junk", "year": 2024},
    ]
    (tmp_path / "research-sweep-confgate-2026-06-14.json").write_text(json.dumps(sweep))
    return admit.discover_from_sweep("confgate", str(tmp_path))


@pytest.mark.integration
def test_admit_dry_run_plans_paper_with_embedding(clean_graph, clean_linkforge, tmp_path):
    _seed_linkforge(clean_linkforge)
    cands = _sweep_fixture(tmp_path)

    plans = admit.admit(
        cands, relevance_fn=_stub_relevance,
        rg_driver=clean_graph, lf_driver=clean_linkforge, dry_run=True,
    )

    admitted = [p for p in plans if p.action == "admit"]
    assert len(admitted) == 1, "only the arxiv paper should be admitted"
    p = admitted[0]
    assert p.arxiv_id == ARXIV
    assert p.tags == ["CF-3", "CH-3"], "bogus tag filtered, ch-3 upper-cased, sorted"
    assert p.forge_score == 7.5
    assert p.has_embedding and len(p.embedding) == 384 and p.embedding[:3] == _EMBEDDING[:3]
    assert p.written is False  # dry-run writes nothing

    # confgate graph stays empty under --dry-run.
    with clean_graph.session() as s:
        assert s.run("MATCH (n) RETURN count(n) AS c").single()["c"] == 0


@pytest.mark.integration
def test_admit_writes_paper_tags_and_is_idempotent(clean_graph, clean_linkforge, tmp_path):
    _seed_linkforge(clean_linkforge)
    cands = _sweep_fixture(tmp_path)

    # run twice — MERGE must keep exactly one Paper + its two TAGGED edges.
    for _ in range(2):
        admit.admit(cands, relevance_fn=_stub_relevance,
                    rg_driver=clean_graph, lf_driver=clean_linkforge, dry_run=False)

    with clean_graph.session() as s:
        rec = s.run(
            """
            MATCH (p:Paper {arxiv_id:$a})
            OPTIONAL MATCH (p)-[:TAGGED]->(t:Tag)
            RETURN p.status AS status, p.forge_score AS forge,
                   size(p.embedding) AS dim,
                   collect(t.name) AS tags,
                   count(p) AS n_paper
            """,
            a=ARXIV,
        ).single()
        assert rec["status"] == "pending_triage"
        assert rec["forge"] == 7.5
        assert rec["dim"] == 384
        assert sorted(rec["tags"]) == ["CF-3", "CH-3"]

        total_papers = s.run("MATCH (p:Paper) RETURN count(p) AS c").single()["c"]
        assert total_papers == 1, "idempotent: re-run must not duplicate the Paper"
        tag_edges = s.run("MATCH (:Paper)-[r:TAGGED]->(:Tag) RETURN count(r) AS c").single()["c"]
        assert tag_edges == 2, "idempotent: re-run must not duplicate TAGGED edges"
