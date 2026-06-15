"""CLI query interface for the confgate research graph (bolt :7689).

Trimmed clone of topo-confidence's query.py — the grouping-MVP command surface
only. Namespace-repointed F-/H-/P11-FE -> CF-/CH-/CG-FE. The semantic/RAG/`ask`
machinery (vector embeddings + LLM synthesis) is intentionally dropped: the MVP
groups by tag, not by embedding, so there is no PyTorch dependency here.

Examples:
    python query.py novelty "learned router beats the cascade at matched cost"
    python query.py pending                # tier-ordered pending_triage papers
    python query.py pending --ids-only     # arxiv IDs only — feeds triage_pending.sh
    python query.py status-report
    python query.py subgraph CF-1 --depth 2
    python query.py future CG               # future experiments (optionally by pathway)
    python query.py grouped                 # papers grouped by the CF/CH lever they touch
"""
from __future__ import annotations

import argparse
import json
import os
import textwrap
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from neo4j import GraphDatabase

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

BOLT = os.environ.get("NEO4J_BOLT_URL", "bolt://localhost:7689")
USER = os.environ.get("NEO4J_USER", "neo4j")
PASSWORD = os.environ.get("NEO4J_PASSWORD", "confgate_graph_dev")


# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------

def _driver():
    return GraphDatabase.driver(
        BOLT, auth=(USER, PASSWORD), notifications_min_severity="OFF",
    )


def _run(cypher: str, **params) -> list[dict[str, Any]]:
    with _driver() as drv, drv.session() as session:
        return [dict(record) for record in session.run(cypher, **params)]


# ---------------------------------------------------------------------------
# Library functions (importable)
# ---------------------------------------------------------------------------

def corroborators(finding_id: str) -> list[dict[str, Any]]:
    return _run(
        """
        MATCH (f:Finding {id: $id})-[r:CORROBORATED_BY]->(p:Paper)
        RETURN p.arxiv_id AS arxiv_id, p.title AS title, p.year AS year,
               properties(r) AS edge
        ORDER BY p.year DESC
        """,
        id=finding_id,
    )


def contradictors(finding_id: str) -> list[dict[str, Any]]:
    return _run(
        """
        MATCH (f:Finding {id: $id})-[r:CONTRADICTED_BY]->(p:Paper)
        RETURN p.arxiv_id AS arxiv_id, p.title AS title, p.year AS year,
               properties(r) AS edge
        ORDER BY p.year DESC
        """,
        id=finding_id,
    )


def extensions(finding_id: str) -> list[dict[str, Any]]:
    return _run(
        """
        MATCH (f:Finding {id: $id})-[r:EXTENDED_BY]->(p:Paper)
        RETURN p.arxiv_id AS arxiv_id, p.title AS title, p.year AS year,
               properties(r) AS edge
        ORDER BY coalesce(r.actionable, false) DESC, p.year DESC
        """,
        id=finding_id,
    )


def novelty_check(claim: str, limit: int = 8) -> list[dict[str, Any]]:
    """Fulltext search across findings + papers (the confgate schema's
    `finding_claims` + `paper_relevance` indexes). Lucene-safe."""
    safe = _escape_lucene(claim)
    finding_hits = _run(
        """
        CALL db.index.fulltext.queryNodes('finding_claims', $q)
        YIELD node, score
        RETURN 'Finding' AS kind, node.id AS id, node.claim AS text,
               node.status AS status, score
        ORDER BY score DESC LIMIT $limit
        """,
        q=safe, limit=limit,
    )
    paper_hits = _run(
        """
        CALL db.index.fulltext.queryNodes('paper_relevance', $q)
        YIELD node, score
        RETURN 'Paper' AS kind, node.arxiv_id AS id,
               coalesce(node.title, '') + ' — ' + coalesce(node.relevance_note, '') AS text,
               node.year AS status, score
        ORDER BY score DESC LIMIT $limit
        """,
        q=safe, limit=limit,
    )
    return finding_hits + paper_hits


def finding_status_report() -> dict[str, list[dict[str, Any]]]:
    rows = _run(
        """
        MATCH (f:Finding)
        RETURN f.id AS id, f.claim AS claim, f.strength AS strength,
               f.status AS status
        ORDER BY f.id
        """
    )
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row["status"] or "ACTIVE", []).append(row)
    return grouped


def subgraph_for_finding(finding_id: str, depth: int = 2) -> dict[str, Any]:
    """Return the full neighborhood of a CF-N as a dict suitable for LLM context."""
    finding = _run(
        "MATCH (f:Finding {id: $id}) RETURN properties(f) AS props",
        id=finding_id,
    )
    if not finding:
        return {"error": f"No finding {finding_id}"}
    payload: dict[str, Any] = {"finding": finding[0]["props"]}
    payload["corroborated_by"] = corroborators(finding_id)
    payload["contradicted_by"] = contradictors(finding_id)
    payload["extended_by"] = extensions(finding_id)
    payload["tags"] = [
        r["name"]
        for r in _run(
            "MATCH (:Finding {id: $id})-[:TAGGED]->(t:Tag) RETURN t.name AS name",
            id=finding_id,
        )
    ]
    payload["depends_on_experiments"] = _run(
        """
        MATCH (fe:FutureExperiment)-[:DEPENDS_ON_FINDING]->(:Finding {id: $id})
        RETURN fe.id AS id, fe.description AS description, fe.status AS status,
               fe.roi_score AS roi_score
        ORDER BY fe.roi_score DESC, fe.id
        """,
        id=finding_id,
    )
    return payload


def future_experiments(
    pathway_id: str | None = None,
    status: str | None = None,
    min_roi: int | None = None,
) -> list[dict[str, Any]]:
    """Return future experiments, optionally filtered. Sorted by roi_score desc."""
    where = []
    params: dict[str, Any] = {}
    if pathway_id:
        where.append("fe.pathway_id = $pid")
        params["pid"] = pathway_id
    if status:
        where.append("fe.status = $status")
        params["status"] = status
    if min_roi is not None:
        where.append("fe.roi_score >= $min_roi")
        params["min_roi"] = min_roi
    where_clause = ("WHERE " + " AND ".join(where)) if where else ""
    return _run(
        f"""
        MATCH (fe:FutureExperiment)
        {where_clause}
        OPTIONAL MATCH (fe)-[:TRIGGERED_BY]->(p:Paper)
        OPTIONAL MATCH (fe)-[:DEPENDS_ON_FINDING]->(d:Finding)
        OPTIONAL MATCH (fe)-[:WOULD_UPDATE]->(u:Finding)
        WITH fe,
             collect(DISTINCT p.arxiv_id) AS triggered_by,
             collect(DISTINCT d.id) AS depends_on,
             collect(DISTINCT u.id) AS would_update
        RETURN fe.id AS id, fe.pathway_id AS pathway_id,
               fe.description AS description, fe.status AS status,
               fe.blocked_by AS blocked_by, fe.priority AS priority,
               fe.estimated_cost AS estimated_cost, fe.roi_score AS roi_score,
               [x IN triggered_by WHERE x IS NOT NULL] AS triggered_by,
               [x IN depends_on WHERE x IS NOT NULL] AS depends_on,
               [x IN would_update WHERE x IS NOT NULL] AS would_update
        ORDER BY coalesce(fe.roi_score, 0) DESC, fe.id
        """,
        **params,
    )


def highest_roi(n: int = 10) -> list[dict[str, Any]]:
    return future_experiments(min_roi=None)[:n]


def pending_triage_papers() -> list[dict[str, Any]]:
    """Papers awaiting deep triage (status='pending_triage'/'candidate'),
    forge-score ordered (highest-signal first)."""
    return _run(
        """
        MATCH (p:Paper)
        WHERE p.status IN ['pending_triage', 'candidate']
        OPTIONAL MATCH (p)-[:TAGGED]->(t:Tag)
        WITH p, collect(DISTINCT t.name) AS tags
        RETURN p.arxiv_id AS arxiv_id, p.title AS title,
               p.relevance_note AS relevance_note,
               p.linkforge_url AS linkforge_url,
               p.forge_score AS forge_score,
               p.suggested_at AS suggested_at, tags
        ORDER BY coalesce(p.forge_score, 0) DESC, p.arxiv_id
        """
    )


def grouped_by_lever() -> list[dict[str, Any]]:
    """The grouping view: every CF/CH lever Tag with the papers tagged to it and
    the CG-FE experiments that depend on it."""
    return _run(
        """
        MATCH (t:Tag)
        OPTIONAL MATCH (t)<-[:TAGGED]-(p:Paper)
        OPTIONAL MATCH (fe:FutureExperiment)-[:DEPENDS_ON_FINDING]->(:Finding {id: t.name})
        WITH t,
             collect(DISTINCT {arxiv_id: p.arxiv_id, title: p.title, status: p.status}) AS papers,
             collect(DISTINCT {id: fe.id, status: fe.status, roi: fe.roi_score}) AS fes
        RETURN t.name AS lever,
               [x IN papers WHERE x.arxiv_id IS NOT NULL] AS papers,
               [x IN fes WHERE x.id IS NOT NULL] AS experiments
        ORDER BY t.name
        """
    )


# ---------------------------------------------------------------------------
# CLI helpers
# ---------------------------------------------------------------------------

LUCENE_RESERVED = r'+-&|!(){}[]^"~*?:\\/'


def _escape_lucene(s: str) -> str:
    out: list[str] = []
    for ch in s:
        out.append("\\" + ch if ch in LUCENE_RESERVED else ch)
    return " ".join("".join(out).split())


def _print_paper_edges(rows: list[dict[str, Any]]) -> None:
    if not rows:
        print("  (none)")
        return
    for r in rows:
        title = r.get("title") or "(untitled)"
        print(f"  - {r['arxiv_id']} ({r.get('year')}) {title}")
        for k, v in (r.get("edge") or {}).items():
            print(textwrap.fill(f"{k}: {v}", width=88, subsequent_indent=" " * 8,
                                initial_indent="      "))


def _print_future_experiment(fe: dict[str, Any], indent: str = "  ") -> None:
    cost = fe.get("estimated_cost") or "—"
    blocked = fe.get("blocked_by")
    blocked_str = f"  blocked: {blocked}" if blocked else ""
    print(f"\n{indent}{fe['id']}  [ROI={fe['roi_score']}, {fe['status']}, "
          f"{fe.get('priority')}]  {cost}{blocked_str}")
    print(textwrap.fill(fe.get("description") or "", width=92,
                        initial_indent=indent + "  ", subsequent_indent=indent + "  "))
    if fe.get("triggered_by"):
        print(f"{indent}  triggered by: {', '.join(fe['triggered_by'])}")
    if fe.get("depends_on"):
        print(f"{indent}  depends on:   {', '.join(fe['depends_on'])}")
    if fe.get("would_update"):
        print(f"{indent}  would update: {', '.join(fe['would_update'])}")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_corroborators(args) -> None:
    print(f"\nCorroborators for {args.finding_id}:")
    _print_paper_edges(corroborators(args.finding_id))


def cmd_contradictors(args) -> None:
    print(f"\nContradictors for {args.finding_id}:")
    _print_paper_edges(contradictors(args.finding_id))


def cmd_extensions(args) -> None:
    print(f"\nExperiment ideas extending {args.finding_id}:")
    _print_paper_edges(extensions(args.finding_id))


def cmd_novelty(args) -> None:
    rows = novelty_check(args.claim, limit=args.limit)
    print(f"\nNovelty check for: {args.claim!r}")
    if not rows:
        print("  (no fulltext matches — likely novel, but verify external lit too)")
        return
    rows.sort(key=lambda r: r["score"], reverse=True)
    for r in rows[: args.limit]:
        print(f"\n  [{r['kind']} {r['id']}] score={r['score']:.2f}")
        print(textwrap.fill(f"    {r['text']}", width=92, subsequent_indent="    "))


def cmd_status_report(_args) -> None:
    grouped = finding_status_report()
    print("\nFinding status report:")
    for status, items in sorted(grouped.items()):
        print(f"\n  === {status} ({len(items)}) ===")
        for it in items:
            print(f"    {it['id']} [{it['strength']}]")
            print(textwrap.fill(f"      {it['claim']}", width=92,
                                subsequent_indent="      "))


def cmd_subgraph(args) -> None:
    print(json.dumps(subgraph_for_finding(args.finding_id, depth=args.depth),
                     indent=2, default=str))


def cmd_future(args) -> None:
    rows = future_experiments(pathway_id=args.pathway_id, status=args.status,
                              min_roi=args.min_roi)
    print(f"\nFuture experiments ({args.pathway_id or 'ALL'}, {len(rows)}):")
    for r in rows:
        _print_future_experiment(r)


def cmd_highest_roi(args) -> None:
    rows = highest_roi(n=args.n)
    print(f"\nTop {args.n} future experiments by ROI:")
    for r in rows:
        _print_future_experiment(r)


def cmd_pending(args) -> None:
    rows = pending_triage_papers()
    if getattr(args, "ids_only", False):
        for r in rows:
            if r["arxiv_id"]:
                print(r["arxiv_id"])
        return
    print(f"\nPending-triage papers ({len(rows)}) — admitted, awaiting deep triage:")
    if not rows:
        print("  (none)")
        return
    for r in rows:
        print(f"\n  {r['arxiv_id']}  forge={r.get('forge_score')}  "
              f"suggested: {r.get('suggested_at') or '—'}")
        print(textwrap.fill(f"    title: {r.get('title') or '(untitled)'}",
                            width=92, subsequent_indent="           "))
        if r.get("relevance_note"):
            print(textwrap.fill(f"    note:  {r['relevance_note']}", width=92,
                                subsequent_indent="           "))
        if r.get("tags"):
            print(f"    tags:  {', '.join(r['tags'])}")
    print("\nDeep pass: bash triage_one.sh <arxiv-id>")
    print("Promote:   python promote_brief.py <brief-path>")


def cmd_premises(_args) -> None:
    rows = _run(
        """
        MATCH (pr:Premise)
        OPTIONAL MATCH (fe:FutureExperiment)-[:RELIES_ON]->(pr)
        WITH pr, count(fe) AS reliant,
             sum(CASE WHEN fe.status IN ['READY','TRIGGERED','BLOCKED']
                 THEN 1 ELSE 0 END) AS open_reliant
        RETURN pr.id AS id, pr.status AS status, pr.statement AS statement,
               pr.refuted_by AS refuted_by, pr.status_date AS status_date,
               reliant, open_reliant
        ORDER BY pr.id
        """
    )
    print(f"\nPremises ({len(rows)}):")
    for r in rows:
        prov = f" by {r['refuted_by']}" if r["refuted_by"] else ""
        print(f"  {r['id']} [{r['status']}{prov}, {r['status_date']}] — "
              f"{r['reliant']} reliant, {r['open_reliant']} open")
        print(f"    {r['statement']}")


def cmd_mooted(args) -> None:
    rows = _run(
        """
        MATCH (fe:FutureExperiment)
        WHERE fe.status IN ['MOOTED', 'ANSWERED']
        RETURN fe.id AS id, fe.status AS status, fe.closed_by AS closed_by,
               fe.completed_date AS date, fe.outcome AS outcome
        ORDER BY fe.completed_date DESC, fe.id
        LIMIT $n
        """,
        n=args.n,
    )
    print(f"\nClosed-by-adjacency FEs (most recent {len(rows)}) — revive with "
          "`update_status.py <id> READY`:")
    for r in rows:
        outcome = " ".join((r["outcome"] or "").split())
        if len(outcome) > 150:
            outcome = outcome[:149] + "…"
        print(f"  {r['id']} [{r['status']} by {r['closed_by']}, {r['date']}]")
        print(f"    {outcome}")


def cmd_grouped(_args) -> None:
    rows = grouped_by_lever()
    print(f"\nPapers grouped by lever ({len(rows)} levers):")
    for r in rows:
        papers = r.get("papers") or []
        fes = r.get("experiments") or []
        print(f"\n  === {r['lever']} ===  ({len(papers)} paper(s), {len(fes)} experiment(s))")
        for p in papers:
            print(f"    paper {p['arxiv_id']} [{p.get('status')}] {p.get('title') or ''}")
        for fe in sorted(fes, key=lambda f: -(f.get("roi") or 0)):
            print(f"    exp   {fe['id']} [ROI={fe.get('roi')}, {fe.get('status')}]")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    for name, fn in (("corroborators", cmd_corroborators),
                     ("contradictors", cmd_contradictors),
                     ("extensions", cmd_extensions)):
        s = sub.add_parser(name)
        s.add_argument("finding_id")
        s.set_defaults(func=fn)

    s = sub.add_parser("novelty")
    s.add_argument("claim")
    s.add_argument("--limit", type=int, default=8)
    s.set_defaults(func=cmd_novelty)

    s = sub.add_parser("status-report")
    s.set_defaults(func=cmd_status_report)

    s = sub.add_parser("subgraph")
    s.add_argument("finding_id")
    s.add_argument("--depth", type=int, default=2)
    s.set_defaults(func=cmd_subgraph)

    s = sub.add_parser("future", help="List future experiments (filter by pathway/status/roi)")
    s.add_argument("pathway_id", nargs="?", default=None)
    s.add_argument("--status", default=None)
    s.add_argument("--min-roi", type=int, default=None, dest="min_roi")
    s.set_defaults(func=cmd_future)

    s = sub.add_parser("highest-roi", help="Top N future experiments by ROI")
    s.add_argument("-n", type=int, default=10)
    s.set_defaults(func=cmd_highest_roi)

    s = sub.add_parser("pending", help="pending_triage papers (--ids-only feeds triage_pending.sh)")
    s.add_argument("--ids-only", action="store_true")
    s.set_defaults(func=cmd_pending)

    s = sub.add_parser("premises", help="Premise vocabulary + reliant-FE counts")
    s.set_defaults(func=cmd_premises)

    s = sub.add_parser("mooted", help="FEs closed by adjacency (MOOTED/ANSWERED)")
    s.add_argument("-n", type=int, default=20)
    s.set_defaults(func=cmd_mooted)

    s = sub.add_parser("grouped", help="Papers grouped by the CF/CH lever they touch")
    s.set_defaults(func=cmd_grouped)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
