"""Pull link-forge's per-project paper tags into the confgate graph.

The consumer half of link-forge's pull-decoupled tagging (link-forge spec
`docs/specs/project-graders.md`). link-forge grades every ingested paper against
a project registry and tags relevant ones in its OWN graph as
``(:Link)-[:RELEVANT_TO {score,note}]->(:Project {name,threshold})``.

This reads the tags for ``:Project {name:'confgate'}`` with ``score >= threshold``
and writes each as a ``:Paper {status:'pending_triage'}`` into confgate's graph —
the SAME node shape ``admit.py`` produces, so ``query.py pending`` /
``triage_pending.sh`` pick them up unchanged. It is an ALTERNATIVE discovery
front-end to ``admit.py --from-sweep``: link-forge has already run the
lean-inclusive relevance gate (the ``r.score``), so there is no second
``claude -p`` admission check here.

link-forge stays strictly **READ-ONLY** (confgate's invariant): idempotency comes
from confgate's own graph — a paper already present as a ``:Paper`` (any status)
is never re-written — NOT from stamping link-forge. (topo-confidence's pull stamps
``pulledAt`` on its own disjoint edge; confgate deliberately does not write
link-forge at all.)

Connections (reuses admit._build_drivers):
    confgate graph -> bolt://localhost:7689  (read + write)
    link-forge     -> bolt://localhost:7687  (READ ONLY)

Run:
    python pull_from_linkforge.py                 # pull project 'confgate'
    python pull_from_linkforge.py --dry-run       # show, write nothing
    python pull_from_linkforge.py --project confgate --threshold 0.5 --limit 50
"""
from __future__ import annotations

import argparse
from datetime import date
from typing import Any

from admit import (
    _WRITE_CYPHER,
    _WRITE_EMBEDDING,
    _build_drivers,
    extract_arxiv_id,
    synthetic_id,
)

DEFAULT_PROJECT = "confgate"
# Used only if the :Project node has no threshold (it always does — link-forge's
# mergeProject sets it from the registry). Pass --threshold to override.
DEFAULT_THRESHOLD = 0.5

# Read RELEVANT_TO tags for a project, pulling the link's embedding + forgeScore
# in the same round-trip (parity with admit's resolve_link copy). Mirrors
# link-forge's papersForProject. coalesce on p.threshold so a registry edit
# propagates; the CLI --threshold is only the fallback floor.
_READ_CYPHER = """
MATCH (l:Link)-[r:RELEVANT_TO]->(p:Project {name: $project})
WHERE r.score >= coalesce(p.threshold, $floor)
RETURN l.url AS url, l.title AS title,
       l.embedding AS embedding, l.forgeScore AS forge_score,
       r.score AS score, r.note AS note
ORDER BY r.score DESC
LIMIT $limit
"""

_EXISTS_CYPHER = "MATCH (p:Paper) RETURN p.arxiv_id AS arxiv_id"


def _fetch_tagged(lf_driver: Any, project: str, threshold: float, limit: int) -> list[dict[str, Any]]:
    if lf_driver is None:
        print("[pull] link-forge unreachable — nothing to pull")
        return []
    with lf_driver.session(default_access_mode="READ") as lf:
        rows = lf.run(_READ_CYPHER, project=project, floor=threshold, limit=limit)
        return [dict(r) for r in rows]


def _existing_ids(rg_driver: Any) -> set[str]:
    with rg_driver.session(default_access_mode="READ") as rg:
        return {r["arxiv_id"] for r in rg.run(_EXISTS_CYPHER) if r["arxiv_id"]}


def pull(project: str = DEFAULT_PROJECT, threshold: float = DEFAULT_THRESHOLD,
         limit: int = 100, dry_run: bool = False) -> int:
    """Pull tagged papers for `project` into confgate's graph. Returns the count
    of NEW :Paper{pending_triage} nodes written. Idempotent: papers already in
    the graph (any status) are skipped, so a re-run writes nothing new."""
    rg_driver, lf_driver = _build_drivers()
    try:
        tagged = _fetch_tagged(lf_driver, project, threshold, limit)
        if not tagged:
            print(f"[pull] no RELEVANT_TO tags for {project!r} at score >= {threshold}")
            return 0

        existing = _existing_ids(rg_driver)
        today = date.today().isoformat()
        written = 0
        rg_session = rg_driver.session() if not dry_run else None
        try:
            for row in tagged:
                url = row["url"] or ""
                arxiv_id = extract_arxiv_id(url) or synthetic_id(url)
                already = arxiv_id in existing
                tag = "DRY" if dry_run else ("skip-existing" if already else "write")
                print(f"[pull] {tag:13s} {arxiv_id}  score={float(row['score']):.2f}  {url}")
                if dry_run or already:
                    continue

                rg_session.run(
                    _WRITE_CYPHER,
                    arxiv_id=arxiv_id,
                    note=row["note"] or "",
                    title=row["title"],
                    url=url,
                    year=None,
                    forge_score=row["forge_score"],
                    today=today,
                )
                # source distinguishes pull-discovered papers from admit's
                # sweep-discovered ones (admit sets source='admit').
                rg_session.run(
                    "MATCH (p:Paper {arxiv_id: $a}) SET p.source = 'linkforge-pull'",
                    a=arxiv_id,
                )
                if row["embedding"] is not None:
                    rg_session.run(_WRITE_EMBEDDING, arxiv_id=arxiv_id, embedding=row["embedding"])
                existing.add(arxiv_id)
                written += 1
        finally:
            if rg_session is not None:
                rg_session.close()

        print(f"[pull] wrote {written} new pending_triage paper(s) for {project!r}")
        return written
    finally:
        rg_driver.close()
        if lf_driver is not None:
            lf_driver.close()


def main() -> None:
    ap = argparse.ArgumentParser(description="Pull link-forge RELEVANT_TO tags into the confgate graph")
    ap.add_argument("--project", default=DEFAULT_PROJECT, help="project name in link-forge's :Project registry")
    ap.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD,
                    help="fallback score floor if the :Project node has none")
    ap.add_argument("--limit", type=int, default=100, help="max tagged papers to pull per run")
    ap.add_argument("--dry-run", action="store_true", help="print what would be pulled, write nothing")
    args = ap.parse_args()
    pull(project=args.project, threshold=args.threshold, limit=args.limit, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
