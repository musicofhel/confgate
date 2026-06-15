#!/usr/bin/env bash
# Parallel dispatcher for deep paper triage over every confgate
# :Paper {status:'pending_triage'} in the confgate graph (bolt :7689).
#
# Spawns N workers (default 3), each running triage_one.sh on one paper via
# `xargs -P`. Each worker spawns its own `claude -p`, preserving per-paper
# isolation (the SKILL.md hard rule, Ríos-García 2604.18805 confirmation-bias
# defense). Conservative parallelism (3) keeps API/MCP load well under any rate
# limit; bump with `PARALLEL=5 bash triage_pending.sh`.
#
# MVP DIVERGENCE FROM TOPO: workers WRITE BRIEFS ONLY — no inline auto-promote.
# Promotion is a separate explicit step (`promote_brief.py`, Phase 3).
#
# Pending-id source: until Phase 3 ships `query.py pending --ids-only`, this
# dispatcher fetches the list directly from the graph with a small inline Python
# (driver from research-graph/requirements.txt, creds from .env). When query.py
# lands, swap the `list_pending` body for `python query.py pending --ids-only`.
#
# Usage:
#   bash triage_pending.sh                 # 3 workers, all pending
#   PARALLEL=5 bash triage_pending.sh      # 5 workers
#   LIMIT=10 bash triage_pending.sh        # at most 10 ids from the queue

set -euo pipefail

cd "$(dirname "$0")"

# `claude -p` refuses to start cleanly inside an existing Claude Code session
# (the parent CLAUDECODE env var triggers a nested-session guard). Strip it so
# spawned per-paper sessions are truly fresh.
unset CLAUDECODE

mkdir -p briefs

PARALLEL="${PARALLEL:-3}"
LIMIT="${LIMIT:-0}"

# Resolve a real interpreter (interactive `python` alias is "command not found"
# under non-interactive bash). Prefer the repo venv, fall back to python3.
if [[ -x "../.venv/bin/python" ]]; then
  PYTHON="../.venv/bin/python"
else
  PYTHON="python3"
fi

list_pending() {
  "$PYTHON" - <<'PY'
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except Exception:
    pass

from neo4j import GraphDatabase

uri = os.environ.get("NEO4J_BOLT_URL", "bolt://localhost:7689")
user = os.environ.get("NEO4J_USER", "neo4j")
pwd = os.environ.get("NEO4J_PASSWORD", "confgate_graph_dev")
drv = GraphDatabase.driver(uri, auth=(user, pwd))
with drv.session(default_access_mode="READ") as s:
    rows = s.run(
        "MATCH (p:Paper {status:'pending_triage'}) "
        "RETURN p.arxiv_id AS id ORDER BY coalesce(p.forge_score,0) DESC, p.arxiv_id"
    )
    for r in rows:
        if r["id"]:
            print(r["id"])
drv.close()
PY
}

ids="$(list_pending)"
total="$(printf '%s\n' "$ids" | grep -c '.' || true)"

if [[ "$LIMIT" -ne 0 ]]; then
  ids="$(printf '%s\n' "$ids" | head -n "$LIMIT")"
  echo "==> $total pending papers, processing first $LIMIT with PARALLEL=$PARALLEL"
else
  echo "==> $total pending papers, processing all with PARALLEL=$PARALLEL"
fi

# xargs -P spawns up to PARALLEL workers; -n 1 = one arxiv_id per worker;
# --no-run-if-empty avoids running with empty input. A worker's exit status
# does NOT abort siblings (xargs default).
printf '%s\n' "$ids" \
  | grep '.' \
  | xargs --no-run-if-empty -P "$PARALLEL" -n 1 -I {} bash triage_one.sh {}

echo
echo "==> dispatcher exited."
echo "    Brief count:  $(ls briefs/triage-*.md 2>/dev/null | wc -l)"
echo "    Briefs are written ONLY — review then promote (Phase 3):"
echo "      python promote_brief.py briefs/triage-YYYY-MM-DD-<arxiv-id>.md --dry-run"
