"""Shared fixtures for the research-graph tooling test tier.

The integration tier needs a live Neo4j. It reads connection details from env
(the same vars the CI integration job sets for its service container, and that
`research-graph/.env` sets locally). If none are present the integration tests
SKIP — the Docker-free unit tier still runs everywhere.

Local: `make test-int` spins an EPHEMERAL throwaway graph on a non-dev port and
exports CONFGATE_TEST_* before invoking pytest. CI sets the same vars to point at
the `neo4j-main` service container. We never bind the dev :7689 in a test.
"""
from __future__ import annotations

import os

import pytest


def _env(*names: str) -> str | None:
    for n in names:
        v = os.environ.get(n)
        if v:
            return v
    return None


def _conn():
    """Resolve (uri, user, password) from env, or None if unconfigured."""
    uri = _env("CONFGATE_TEST_BOLT_URL", "TEST_NEO4J_URI")
    user = _env("CONFGATE_TEST_USER", "TEST_NEO4J_USER") or "neo4j"
    pwd = _env("CONFGATE_TEST_PASSWORD", "TEST_NEO4J_PASSWORD")
    if not uri or not pwd:
        return None
    return uri, user, pwd


@pytest.fixture(scope="session")
def neo4j_driver():
    conn = _conn()
    if conn is None:
        pytest.skip(
            "No test Neo4j configured — set CONFGATE_TEST_BOLT_URL / "
            "CONFGATE_TEST_PASSWORD (see `make test-int`)."
        )
    try:
        from neo4j import GraphDatabase
    except ImportError:
        pytest.skip("neo4j driver not installed (pip install -r research-graph/requirements.txt)")
    uri, user, pwd = conn
    driver = GraphDatabase.driver(uri, auth=(user, pwd))
    driver.verify_connectivity()
    yield driver
    driver.close()


def _lf_conn():
    """Resolve the link-forge stand-in (uri, user, password), or None."""
    uri = _env("LINK_FORGE_TEST_BOLT_URL")
    user = _env("LINK_FORGE_TEST_USER") or "neo4j"
    pwd = _env("LINK_FORGE_TEST_PASSWORD")
    if not uri or not pwd:
        return None
    return uri, user, pwd


@pytest.fixture(scope="session")
def linkforge_driver():
    """A SECOND Neo4j standing in for link-forge (Gap 4). Skips if unconfigured.

    Phase 1 admit.py reads link-forge READ-ONLY to copy embeddings; the test
    seeds a link-forge-shaped :Link here. Locally `make test-int` spins this on
    :7691; CI points it at the `neo4j-linkforge` service container (:7688).
    """
    conn = _lf_conn()
    if conn is None:
        pytest.skip(
            "No link-forge test Neo4j configured — set LINK_FORGE_TEST_BOLT_URL / "
            "LINK_FORGE_TEST_PASSWORD (see `make test-int`)."
        )
    from neo4j import GraphDatabase

    uri, user, pwd = conn
    driver = GraphDatabase.driver(uri, auth=(user, pwd))
    driver.verify_connectivity()
    yield driver
    driver.close()


@pytest.fixture
def clean_linkforge(linkforge_driver):
    """Wipe the link-forge stand-in before and after each test."""
    with linkforge_driver.session() as s:
        s.run("MATCH (n) DETACH DELETE n")
    yield linkforge_driver
    with linkforge_driver.session() as s:
        s.run("MATCH (n) DETACH DELETE n")


@pytest.fixture
def clean_graph(neo4j_driver):
    """Wipe nodes AND drop every constraint/index so schema-from-scratch is honest."""
    def _wipe(session):
        session.run("MATCH (n) DETACH DELETE n")
        for rec in session.run("SHOW CONSTRAINTS YIELD name RETURN name"):
            session.run(f"DROP CONSTRAINT {rec['name']} IF EXISTS")
        for rec in session.run("SHOW INDEXES YIELD name RETURN name"):
            session.run(f"DROP INDEX {rec['name']} IF EXISTS")

    with neo4j_driver.session() as session:
        _wipe(session)
    yield neo4j_driver
    with neo4j_driver.session() as session:
        _wipe(session)
