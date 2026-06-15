# confgate — dev targets. CI calls these same targets (SPEC v1.2 Gap 5).
.PHONY: test test-int e2e-dry up down schema lint help

help:
	@echo "test      - unit tier (Docker-free): pytest -m 'not integration' + ruff"
	@echo "test-int  - integration tier: spin ephemeral graph + pytest -m integration"
	@echo "e2e-dry   - zero-network end-to-end smoke (Phase 4)"
	@echo "up        - docker compose up the research graph"
	@echo "down      - docker compose down"
	@echo "schema    - apply schema.cypher to the running graph"

# --- Unit tier: no Docker, no Neo4j. Must stay green at every phase boundary. ---
test:
	pytest -m "not integration" tests/
	ruff check confgate research-graph

# --- Integration tier: needs a live Neo4j. ---
# Local: spins an EPHEMERAL throwaway graph (non-dev port), runs, tears down.
# CI: the integration job sets CONFGATE_TEST_* from its service container and
#     runs `pytest -m integration` directly (skip this spinner under docker-in-docker).
test-int:
	bash research-graph/scripts/spin-test-graph.sh

test-int-ci:
	pytest -m integration tests/research_graph/

# --- Zero-network end-to-end smoke (wired in Phase 4). ---
e2e-dry:
	pytest -m "e2e_dry" tests/research_graph/ || echo "e2e-dry target lands in Phase 4"

# --- Graph lifecycle helpers ---
up:
	docker compose -f research-graph/docker-compose.yml --env-file research-graph/.env up -d

down:
	docker compose -f research-graph/docker-compose.yml down

schema:
	@set -a && . research-graph/.env && set +a && \
	  docker exec -i confgate-research-graph cypher-shell -u "$$NEO4J_USER" -p "$$NEO4J_PASSWORD" \
	    < research-graph/schema.cypher

lint:
	ruff check confgate research-graph
