#!/usr/bin/env bash
# Spin EPHEMERAL throwaway Neo4j instances for the integration tier, run pytest
# against them, then tear them down. Never touches the dev :7689 graph/volume.
#
# Two instances (Gap 4 — Community Edition is single-DB, so the link-forge
# stand-in is its OWN container, never a second DB):
#   - confgate graph   -> CONFGATE_TEST_*   (bolt :7690)
#   - link-forge graph -> LINK_FORGE_TEST_* (bolt :7691)
#
# Used by `make test-int` for local runs. CI does NOT use this — its integration
# job runs `pytest -m integration` directly against two service containers.
set -euo pipefail

CG_BOLT="${TEST_GRAPH_BOLT_PORT:-7690}"
CG_HTTP="${TEST_GRAPH_HTTP_PORT:-7477}"
LF_BOLT="${TEST_LF_BOLT_PORT:-7691}"
LF_HTTP="${TEST_LF_HTTP_PORT:-7478}"
PW="ephemeral_test_$$"
CG_NAME="confgate-test-graph-$$"
LF_NAME="confgate-test-linkforge-$$"

cleanup() {
  docker rm -f "$CG_NAME" >/dev/null 2>&1 || true
  docker rm -f "$LF_NAME" >/dev/null 2>&1 || true
}
trap cleanup EXIT

start_graph() {
  local name="$1" bolt="$2" http="$3"
  echo ">> starting ephemeral neo4j ($name) on bolt:$bolt"
  docker run -d --name "$name" \
    -p "${bolt}:7687" -p "${http}:7474" \
    -e NEO4J_AUTH="neo4j/${PW}" \
    neo4j:5.26-community >/dev/null
}

wait_graph() {
  local name="$1"
  echo ">> waiting for $name to accept bolt..."
  for i in $(seq 1 60); do
    if docker exec "$name" cypher-shell -u neo4j -p "$PW" "RETURN 1" >/dev/null 2>&1; then
      echo ">> $name ready after ${i}s"
      return 0
    fi
    sleep 1
  done
  echo "!! $name did not become ready" >&2
  exit 1
}

start_graph "$CG_NAME" "$CG_BOLT" "$CG_HTTP"
start_graph "$LF_NAME" "$LF_BOLT" "$LF_HTTP"
wait_graph "$CG_NAME"
wait_graph "$LF_NAME"

export CONFGATE_TEST_BOLT_URL="bolt://localhost:${CG_BOLT}"
export CONFGATE_TEST_USER="neo4j"
export CONFGATE_TEST_PASSWORD="$PW"
export LINK_FORGE_TEST_BOLT_URL="bolt://localhost:${LF_BOLT}"
export LINK_FORGE_TEST_USER="neo4j"
export LINK_FORGE_TEST_PASSWORD="$PW"

# PYTEST_MARKER lets `make e2e-dry` reuse this spinner to run just the
# zero-network e2e tracer (`-m e2e_dry`); defaults to the full integration tier.
pytest -m "${PYTEST_MARKER:-integration}" tests/research_graph/ "$@"
