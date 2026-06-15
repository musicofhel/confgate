#!/usr/bin/env bash
# Spin an EPHEMERAL throwaway Neo4j for the integration tier, run pytest against
# it, then tear it down. Never touches the dev :7689 graph or its volume.
#
# Used by `make test-int` for local runs. CI does NOT use this — its integration
# job runs `pytest -m integration` directly against a service container.
set -euo pipefail

PORT_BOLT="${TEST_GRAPH_BOLT_PORT:-7690}"
PORT_HTTP="${TEST_GRAPH_HTTP_PORT:-7477}"
PW="ephemeral_test_$$"
NAME="confgate-test-graph-$$"

cleanup() { docker rm -f "$NAME" >/dev/null 2>&1 || true; }
trap cleanup EXIT

echo ">> starting ephemeral neo4j ($NAME) on bolt:$PORT_BOLT"
docker run -d --name "$NAME" \
  -p "${PORT_BOLT}:7687" -p "${PORT_HTTP}:7474" \
  -e NEO4J_AUTH="neo4j/${PW}" \
  neo4j:5.26-community >/dev/null

echo ">> waiting for neo4j to accept bolt..."
for i in $(seq 1 60); do
  if docker exec "$NAME" cypher-shell -u neo4j -p "$PW" "RETURN 1" >/dev/null 2>&1; then
    echo ">> neo4j ready after ${i}s"
    break
  fi
  sleep 1
  if [ "$i" -eq 60 ]; then echo "!! neo4j did not become ready" >&2; exit 1; fi
done

export CONFGATE_TEST_BOLT_URL="bolt://localhost:${PORT_BOLT}"
export CONFGATE_TEST_USER="neo4j"
export CONFGATE_TEST_PASSWORD="$PW"

pytest -m integration tests/research_graph/ "$@"
