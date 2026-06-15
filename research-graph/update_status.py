"""Update the status of an existing FutureExperiment (CG-FE).

Cloned from topo-confidence, repointed to the confgate standalone graph
(bolt :7689). Reverses a MOOTED close back to READY when a premise is resurrected.

Examples:
    # Mark as completed with an outcome
    python update_status.py CG-FE1 COMPLETED \\
        --outcome "RouteLLM router lost to the gate-ordered cascade at matched cost."

    # Re-classify (e.g. a paper appears that triggers a READY experiment)
    python update_status.py CG-FE2 TRIGGERED

    # Resurrect a MOOTED FE after its premise is un-refuted
    python update_status.py CG-FE1 READY

    # Moot / Answer with provenance (and, when the id matches a graph node, a
    # MOOTED_BY / ANSWERED_BY edge):
    python update_status.py CG-FE1 MOOTED \\
        --by free-gate-is-ceiling --outcome "Premise still holds; challenger moot."
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

BOLT = os.environ.get("NEO4J_BOLT_URL", "bolt://localhost:7689")
USER = os.environ.get("NEO4J_USER", "neo4j")
PASSWORD = os.environ.get("NEO4J_PASSWORD", "confgate_graph_dev")

VALID_STATUS = ["READY", "TRIGGERED", "BLOCKED", "COMPLETED", "ABANDONED",
                "MOOTED", "ANSWERED"]
TERMINAL_STATUS = ["COMPLETED", "ABANDONED", "MOOTED", "ANSWERED"]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("fe_id", help="e.g. CG-FE1")
    p.add_argument("status", choices=VALID_STATUS)
    p.add_argument("--outcome", default=None,
                   help="What happened. Required for COMPLETED/ABANDONED.")
    p.add_argument("--blocked-by", default=None,
                   help="If status=BLOCKED, what's blocking it.")
    p.add_argument("--by", default=None,
                   help="For MOOTED/ANSWERED: id of the experiment/premise that "
                        "closed this FE. Stored as fe.closed_by and, when a "
                        "matching node exists, as a MOOTED_BY/ANSWERED_BY edge.")
    args = p.parse_args()

    if args.status in TERMINAL_STATUS and not args.outcome:
        print(f"--outcome is required when setting status to {args.status}.")
        sys.exit(2)
    if args.status in ("MOOTED", "ANSWERED") and not args.by:
        print(f"--by is required when setting status to {args.status} "
              "(what closed it?).")
        sys.exit(2)

    today = date.today().isoformat()
    drv = GraphDatabase.driver(BOLT, auth=(USER, PASSWORD))
    with drv.session() as s:
        rec = s.run(
            """
            MATCH (fe:FutureExperiment {id: $id})
            SET fe.status = $status,
                fe.outcome = coalesce($outcome, fe.outcome),
                fe.closed_by = CASE
                    WHEN $status IN ['MOOTED', 'ANSWERED'] THEN $by
                    ELSE fe.closed_by
                END,
                fe.blocked_by = CASE
                    WHEN $status = 'BLOCKED' THEN coalesce($blocked, fe.blocked_by)
                    WHEN $status IN $terminal THEN null
                    ELSE fe.blocked_by
                END,
                fe.completed_date = CASE
                    WHEN $status IN $terminal THEN $today
                    ELSE fe.completed_date
                END
            RETURN fe.id AS id, fe.status AS status
            """,
            id=args.fe_id,
            status=args.status,
            outcome=args.outcome,
            blocked=args.blocked_by,
            by=args.by,
            today=today,
            terminal=TERMINAL_STATUS,
        ).single()

        if rec and args.status in ("MOOTED", "ANSWERED") and args.by:
            edge = "MOOTED_BY" if args.status == "MOOTED" else "ANSWERED_BY"
            linked = s.run(
                f"""
                MATCH (fe:FutureExperiment {{id: $id}})
                MATCH (src) WHERE (src:FutureExperiment OR src:Premise
                                   OR src:Finding)
                            AND src.id = $by
                MERGE (fe)-[r:{edge}]->(src)
                SET r.reason = $outcome, r.date = $today
                RETURN count(src) AS n
                """,
                id=args.fe_id, by=args.by, outcome=args.outcome, today=today,
            ).single()
            if linked and linked["n"] == 0:
                print(f"  (no graph node with id {args.by!r} — provenance kept "
                      "as fe.closed_by property only)")

    drv.close()
    if not rec:
        print(f"No FutureExperiment {args.fe_id}.")
        sys.exit(1)
    print(f"FutureExperiment {rec['id']} -> {rec['status']}")
    print("Run `python generate_next_experiments.py` to refresh NEXT_EXPERIMENTS.md.")


if __name__ == "__main__":
    main()
