"""Phase 3 tracer-bullet: brief promotion + grouping (promote_brief.py & friends).

Two tiers:
  - unit (Docker-free): static guards that the 5-item clone surgery actually
    happened — no Redis publish, no PyTorch embedder, the claims-gate path points
    at research-graph/validate_claims.py, and the namespace is CF/CH/CG-FE.
  - integration (@integration, one neo4j container): apply schema -> seed CF-1..8
    :Finding + a premise -> dry-run promote (writes nothing) -> live promote ->
    assert the renumbered :FutureExperiment{CG-FE1} with edges to the right CF,
    the :Paper graphed, the CH-7 hypothesis inserted, NEXT_EXPERIMENTS.md
    regenerated; plus the namespace-regression, claims-gate, and premise-cascade
    behaviors.

promote_brief.py imports neo4j at top level (it is graph tooling), so every test
that imports it is @integration and imports it *inside* the test — the module
must stay importable during unit-tier collection, which it does because we never
import it at module top here.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.research_graph.graphutil import (
    REPO_ROOT,
    SCHEMA_CYPHER,
    bootstrap_repo,
    split_cypher_statements,
)

RG = REPO_ROOT / "research-graph"
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "triage-sample.md"
ARXIV = "2406.18665"

# Point the cloned scripts (and the generate_next_experiments subprocess they
# spawn) at the ephemeral TEST graph, never the dev :7689. Harmless in unit runs
# where CONFGATE_TEST_* is unset. Done at import so promote_brief reads the right
# BOLT when a test first imports it.
for _src, _dst in (
    ("CONFGATE_TEST_BOLT_URL", "NEO4J_BOLT_URL"),
    ("CONFGATE_TEST_USER", "NEO4J_USER"),
    ("CONFGATE_TEST_PASSWORD", "NEO4J_PASSWORD"),
):
    if os.environ.get(_src):
        os.environ[_dst] = os.environ[_src]
# bridge.py resolve (step 6) reads link-forge; point it at the same fast test
# graph so it connects instantly, finds nothing, and degrades gracefully.
if os.environ.get("NEO4J_BOLT_URL"):
    os.environ.setdefault("LINK_FORGE_BOLT_URL", os.environ["NEO4J_BOLT_URL"])
    os.environ.setdefault("LINK_FORGE_USER", os.environ.get("NEO4J_USER", "neo4j"))
    os.environ.setdefault("LINK_FORGE_PASSWORD", os.environ.get("NEO4J_PASSWORD", ""))

sys.path.insert(0, str(RG))


# =========================== unit tier (no Docker) ===========================

def test_redis_publish_stripped():
    """Surgery #1: no NGS/Redis publish survives in the confgate clone."""
    src = (RG / "promote_brief.py").read_text()
    assert "topoconf:research:triaged" not in src
    assert "import redis" not in src
    assert "pipeline.publisher" not in src
    assert "init_redis_publisher" not in src


def test_no_pytorch_embedder():
    """Surgery #2: step-8b embed_node() is disabled, no PyTorch embedder added."""
    src = (RG / "promote_brief.py").read_text()
    assert "backfill_embeddings" not in src
    assert "embed_node(" not in src


def test_claims_gate_path_is_local():
    """Surgery #3: the claims gate points at research-graph/validate_claims.py."""
    src = (RG / "promote_brief.py").read_text()
    assert 'ROOT / "validate_claims.py"' in src


def test_namespace_is_confgate():
    """Surgery #5: the namespace regexes are CF/CH/CG-FE, not F/H/P11-FE."""
    src = (RG / "promote_brief.py").read_text()
    assert "Next ID: CH-" in src
    assert "CG-FE" in src or "CG}-FE" in src
    assert "Next ID: H-" not in src


def test_promote_imports_shared_parser():
    """promote_brief reuses the Phase-2 parser instead of re-deriving it."""
    src = (RG / "promote_brief.py").read_text()
    assert "from brief_parser import" in src
    assert "def parse_brief" not in src  # not redefined locally


# =========================== integration tier ================================

CF_SEED = """
UNWIND range(1, 8) AS n
MERGE (f:Finding {id: 'CF-' + toString(n)})
SET f.claim = 'confgate finding CF-' + toString(n),
    f.strength = 'strong', f.status = 'ACTIVE'
"""


def _apply_schema(driver):
    with driver.session() as s:
        for stmt in split_cypher_statements(SCHEMA_CYPHER.read_text()):
            s.run(stmt)


def _seed_findings(driver):
    with driver.session() as s:
        s.run(CF_SEED)


def _repo_copy(tmp_path: Path) -> Path:
    """A throwaway repo root seeded with the frozen Phase-0 bootstrap of the
    markdown files promote mutates. Hermetic by design — see graphutil.bootstrap_repo
    (copying the live canonical files would break the renumber assertions every
    time the pipeline promotes a real brief)."""
    return bootstrap_repo(tmp_path)


def _brief_copy(tmp_path: Path) -> Path:
    brief = tmp_path / f"triage-2026-06-14-{ARXIV}.md"
    brief.write_text(FIXTURE.read_text())
    return brief


@pytest.mark.integration
def test_dry_run_then_live_promote(clean_graph, tmp_path, monkeypatch):
    _apply_schema(clean_graph)
    _seed_findings(clean_graph)
    repo = _repo_copy(tmp_path)
    brief = _brief_copy(tmp_path)
    monkeypatch.setenv("CONFGATE_REPO_ROOT", str(repo))

    import promote_brief
    # Avoid the bridge.py subprocess hitting link-forge during the test.
    monkeypatch.setattr(promote_brief, "resolve_papers", lambda *a, **k: None)

    # --- dry-run writes nothing ---
    monkeypatch.setattr(sys, "argv", ["promote_brief.py", str(brief), "--dry-run"])
    promote_brief.main()
    with clean_graph.session() as s:
        n_fe = s.run("MATCH (fe:FutureExperiment) RETURN count(fe) AS c").single()["c"]
    assert n_fe == 0, "dry-run must not write any FutureExperiment"

    # --- live promote ---
    monkeypatch.setattr(sys, "argv", ["promote_brief.py", str(brief)])
    promote_brief.main()

    with clean_graph.session() as s:
        # CG-FE57 -> CG-FE1, CG-FE58 -> CG-FE2 (renumbered from empty graph).
        ids = sorted(r["id"] for r in s.run(
            "MATCH (fe:FutureExperiment) RETURN fe.id AS id"))
        assert ids == ["CG-FE1", "CG-FE2"], ids

        dep = sorted(r["cf"] for r in s.run(
            "MATCH (:FutureExperiment {id:'CG-FE1'})-[:DEPENDS_ON_FINDING]->(f:Finding) "
            "RETURN f.id AS cf"))
        assert dep == ["CF-3"], "CG-FE1 depends-on CF-3 (from the fixture)"

        dep2 = sorted(r["cf"] for r in s.run(
            "MATCH (:FutureExperiment {id:'CG-FE2'})-[:DEPENDS_ON_FINDING]->(f:Finding) "
            "RETURN f.id AS cf"))
        assert dep2 == ["CF-1", "CF-7"]

        rec = s.run("MATCH (p:Paper {arxiv_id:$a}) RETURN p.status AS st",
                    a=ARXIV).single()
        assert rec and rec["st"] == "graphed"

        # TRIGGERED_BY edge wired to the source paper.
        trig = s.run(
            "MATCH (:FutureExperiment {id:'CG-FE1'})-[:TRIGGERED_BY]->(p:Paper) "
            "RETURN p.arxiv_id AS a").single()
        assert trig and trig["a"] == ARXIV

        # Methods extracted -> :Method node.
        meth = [r["d"] for r in s.run("MATCH (m:Method) RETURN m.display_name AS d")]
        assert "Matrix-factorization router" in meth

    # HYPOTHESES.md got CH-57 -> CH-7 inserted, Next ID bumped to CH-8.
    hyp = (repo / "HYPOTHESES.md").read_text()
    assert "### CH-7:" in hyp
    assert "Next ID: CH-8" in hyp

    # NEXT_EXPERIMENTS.md regenerated, non-empty, mentions the renumbered FE.
    nxt = repo / "NEXT_EXPERIMENTS.md"
    assert nxt.exists()
    body = nxt.read_text()
    assert body.strip()
    assert "CG-FE1" in body


@pytest.mark.integration
def test_namespace_regression_renumber_uses_ch(clean_graph, tmp_path, monkeypatch):
    """renumber() reads 'Next ID: CH-N' from the confgate HYPOTHESES.md — an
    unported clone (looking for 'Next ID: H-N') would SystemExit here."""
    _apply_schema(clean_graph)
    repo = _repo_copy(tmp_path)
    monkeypatch.setenv("CONFGATE_REPO_ROOT", str(repo))

    import importlib

    import promote_brief
    importlib.reload(promote_brief)  # re-read REPO from the patched env

    parsed = promote_brief.parse_brief(FIXTURE)
    remaps = promote_brief.renumber(parsed)  # must NOT raise
    assert remaps["h_remap"].get("CH-57") == "CH-7"
    assert remaps["fe_remap"].get("CG-FE57") == "CG-FE1"


@pytest.mark.integration
def test_claims_gate_refuses_stale(tmp_path, monkeypatch):
    """A brief declaring a new cg-* claim with a stale validate_claims.py mtime
    must refuse to promote."""
    repo = _repo_copy(tmp_path)
    monkeypatch.setenv("CONFGATE_REPO_ROOT", str(repo))

    brief = tmp_path / f"triage-2026-06-14-{ARXIV}.md"
    brief.write_text(
        FIXTURE.read_text().replace(
            "## New claims\n\nnone",
            "## New claims\n\n- cg-test-claim: RouteLLM router AUROC 0.88 on MATH-500",
        )
    )
    # Make the brief newer than validate_claims.py (gate compares mtimes).
    vc = RG / "validate_claims.py"
    old = vc.stat().st_mtime
    os.utime(brief, (old + 10, old + 10))

    import promote_brief
    parsed = promote_brief.parse_brief(brief)
    assert parsed["new_claims_lines"], "fixture edit should declare a new claim"
    with pytest.raises(SystemExit):
        promote_brief.assert_claims_gate(parsed, brief)


@pytest.mark.integration
def test_premise_cascade_moots_and_reverses(clean_graph, tmp_path, monkeypatch):
    _apply_schema(clean_graph)
    _seed_findings(clean_graph)
    repo = _repo_copy(tmp_path)
    brief = _brief_copy(tmp_path)
    monkeypatch.setenv("CONFGATE_REPO_ROOT", str(repo))

    import promote_brief
    monkeypatch.setattr(promote_brief, "resolve_papers", lambda *a, **k: None)
    monkeypatch.setattr(sys, "argv", ["promote_brief.py", str(brief)])
    promote_brief.main()

    # The scripts read NEO4J_* from the (already-mapped) environment.
    env = dict(os.environ)

    def run_cli(script, *args):
        return subprocess.run(
            [sys.executable, str(RG / script), *args],
            capture_output=True, text=True, env=env,
        )

    # Seed + link a premise to CG-FE1, then refute it -> CG-FE1 MOOTED.
    assert run_cli("premises.py", "seed").returncode == 0
    assert run_cli("premises.py", "link", "CG-FE1", "free-gate-is-ceiling").returncode == 0
    r = run_cli("premises.py", "refute", "free-gate-is-ceiling",
                "--by", "CG-FE-TEST", "--reason", "unit-test refutation")
    assert r.returncode == 0, r.stderr

    with clean_graph.session() as s:
        st = s.run("MATCH (fe:FutureExperiment {id:'CG-FE1'}) RETURN fe.status AS s"
                   ).single()["s"]
    assert st == "MOOTED"

    # Resurrect it.
    r = run_cli("update_status.py", "CG-FE1", "READY")
    assert r.returncode == 0, r.stderr
    with clean_graph.session() as s:
        st = s.run("MATCH (fe:FutureExperiment {id:'CG-FE1'}) RETURN fe.status AS s"
                   ).single()["s"]
    assert st == "READY"
