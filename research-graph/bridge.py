"""Bridge from the confgate research graph to link-forge.

link-forge stores academic papers as (:Link) nodes whose URL contains the
arxiv ID (e.g. http://arxiv.org/abs/2410.13640). This module maps an arxiv
ID to that node and enriches the research graph's Paper stubs with the
fields we want to keep here (title and forgeScore — abstracts stay in
link-forge to avoid duplication), and exposes the stored MiniLM embedding so
admit.py can copy it rather than re-embedding.

Connections:
    research graph -> bolt://localhost:7689 (read+write, confgate's OWN graph)
    link-forge     -> bolt://localhost:7687 (READ ONLY — never written)

If link-forge is unreachable, every function returns gracefully (None or
[]) and prints a one-line warning.

Cloned from topo-confidence/research-graph/bridge.py and repointed at
confgate's standalone graph (decision #4). The link-forge env var names are
identical, so only the research-graph defaults changed (7688 -> 7689).
"""
from __future__ import annotations

import argparse
import json
import os
import re
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from dotenv import load_dotenv
from neo4j import GraphDatabase
from neo4j.exceptions import AuthError, ServiceUnavailable

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")  # override=False: real env (CI/tests) wins over .env

RG_BOLT = os.environ.get("NEO4J_BOLT_URL", "bolt://localhost:7689")
RG_USER = os.environ.get("NEO4J_USER", "neo4j")
RG_PASS = os.environ.get("NEO4J_PASSWORD", "confgate_graph_dev")

LF_BOLT = os.environ.get("LINK_FORGE_BOLT_URL", "bolt://localhost:7687")
LF_USER = os.environ.get("LINK_FORGE_USER", "neo4j")
LF_PASS = os.environ.get("LINK_FORGE_PASSWORD", "link_forge_dev")


# ---------------------------------------------------------------------------
# Connections
# ---------------------------------------------------------------------------

@contextmanager
def _link_forge_session() -> Iterator[Any]:
    """Yield a link-forge READ session, or None if unreachable."""
    try:
        drv = GraphDatabase.driver(LF_BOLT, auth=(LF_USER, LF_PASS))
        with drv.session(default_access_mode="READ") as s:
            s.run("RETURN 1").consume()  # quick handshake
            yield s
        drv.close()
    except (ServiceUnavailable, AuthError, OSError) as exc:
        print(f"[bridge] link-forge unreachable at {LF_BOLT}: {exc}")
        yield None


@contextmanager
def _research_session() -> Iterator[Any]:
    drv = GraphDatabase.driver(RG_BOLT, auth=(RG_USER, RG_PASS))
    with drv.session() as s:
        yield s
    drv.close()


# ---------------------------------------------------------------------------
# Core queries
# ---------------------------------------------------------------------------

ARXIV_RE = re.compile(r"(\d{4}\.\d{4,5})")


def _arxiv_to_url_substr(arxiv_id: str) -> str:
    """Return a substring guaranteed to appear in any canonical arxiv URL."""
    return f"/{arxiv_id}"


def resolve_from_linkforge(arxiv_id: str, session: Any | None = None) -> dict[str, Any] | None:
    """Look up a paper in link-forge by arxiv ID.

    Returns a dict with title/forgeScore/url/quality/contentType/concepts (top 8)
    AND the 384-dim ``embedding`` (so admit.py can copy it), or None if not
    found / link-forge unreachable.

    Pass an existing link-forge READ ``session`` to reuse one connection across
    many lookups (admit.py does this); otherwise a one-shot session is opened.
    """
    needle = _arxiv_to_url_substr(arxiv_id)

    def _run(s: Any) -> dict[str, Any] | None:
        rows = list(
            s.run(
                """
                MATCH (l:Link)
                WHERE l.url CONTAINS $needle
                OPTIONAL MATCH (l)-[:RELATES_TO_CONCEPT]->(c:Concept)
                OPTIONAL MATCH (l)-[:TAGGED_WITH]->(t:Tag)
                WITH l,
                     collect(DISTINCT c.name)[0..8] AS concepts,
                     collect(DISTINCT t.name)[0..8] AS tags
                RETURN l.title       AS title,
                       l.url         AS url,
                       l.forgeScore  AS forgeScore,
                       l.quality     AS quality,
                       l.contentType AS contentType,
                       l.purpose     AS purpose,
                       l.description AS description,
                       l.embedding   AS embedding,
                       concepts,
                       tags
                LIMIT 1
                """,
                needle=needle,
            )
        )
        if not rows:
            return None
        rec = dict(rows[0])
        rec["arxiv_id"] = arxiv_id
        return rec

    if session is not None:
        return _run(session)
    with _link_forge_session() as s:
        if s is None:
            return None
        return _run(s)


def enrich_all_papers(verbose: bool = True) -> dict[str, Any]:
    """For every Paper in the research graph, copy title + forgeScore from link-forge.

    Existing title/relevance_note are preserved; only fills in missing title and
    adds forgeScore. Returns a small summary dict.
    """
    with _research_session() as rg:
        papers = list(
            rg.run("MATCH (p:Paper) RETURN p.arxiv_id AS arxiv_id, p.title AS title")
        )

    found, missing = [], []
    for r in papers:
        arxiv_id = r["arxiv_id"]
        meta = resolve_from_linkforge(arxiv_id)
        if meta is None:
            missing.append(arxiv_id)
            if verbose:
                print(f"  miss   {arxiv_id}")
            continue
        found.append(arxiv_id)
        with _research_session() as rg:
            rg.run(
                """
                MATCH (p:Paper {arxiv_id: $a})
                SET p.linkforge_title = $title,
                    p.forge_score = $score,
                    p.linkforge_url = $url
                """,
                a=arxiv_id,
                title=meta.get("title"),
                score=meta.get("forgeScore"),
                url=meta.get("url"),
            )
        if verbose:
            print(f"  hit    {arxiv_id}  forgeScore={meta.get('forgeScore')}  {meta.get('title') or ''}")

    return {"enriched": len(found), "missing": len(missing), "missing_ids": missing}


def find_ungraphed_papers(tag: str, limit: int = 25) -> list[dict[str, Any]]:
    """Find arxiv links in link-forge matching a tag and NOT yet in the research graph.

    Discovery aid: "what's in link-forge about `<tag>` that I haven't pulled in?"
    """
    with _research_session() as rg:
        graphed = {
            r["arxiv_id"]
            for r in rg.run("MATCH (p:Paper) RETURN p.arxiv_id AS arxiv_id")
        }

    candidates: list[dict[str, Any]] = []
    with _link_forge_session() as session:
        if session is None:
            return []
        rows = session.run(
            """
            MATCH (l:Link)
            WHERE l.url CONTAINS 'arxiv'
              AND (toLower(coalesce(l.title, '')) CONTAINS toLower($tag)
                   OR toLower(coalesce(l.description, '')) CONTAINS toLower($tag)
                   OR toLower(coalesce(l.purpose, '')) CONTAINS toLower($tag))
            RETURN l.url AS url, l.title AS title,
                   l.forgeScore AS forgeScore, l.contentType AS contentType
            ORDER BY coalesce(l.forgeScore, 0) DESC
            LIMIT $limit
            """,
            tag=tag,
            limit=limit * 3,
        )
        for r in rows:
            url = r["url"] or ""
            m = ARXIV_RE.search(url)
            if not m:
                continue
            arxiv_id = m.group(1)
            if arxiv_id in graphed:
                continue
            candidates.append(
                {
                    "arxiv_id": arxiv_id,
                    "title": r["title"],
                    "url": url,
                    "forgeScore": r["forgeScore"],
                    "contentType": r["contentType"],
                }
            )
            if len(candidates) >= limit:
                break
    return candidates


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("resolve")
    s.add_argument("arxiv_id")

    s = sub.add_parser("enrich")
    s.add_argument("--quiet", action="store_true")

    s = sub.add_parser("ungraphed")
    s.add_argument("tag")
    s.add_argument("--limit", type=int, default=25)

    args = p.parse_args()

    if args.cmd == "resolve":
        out = resolve_from_linkforge(args.arxiv_id)
        if out is None:
            print(json.dumps({"arxiv_id": args.arxiv_id, "found": False}))
        else:
            # Drop the 384-float embedding from CLI output — too noisy to print.
            printable = {k: v for k, v in out.items() if k != "embedding"}
            printable["has_embedding"] = out.get("embedding") is not None
            print(json.dumps(printable, indent=2, default=str))
    elif args.cmd == "enrich":
        print(json.dumps(enrich_all_papers(verbose=not args.quiet), indent=2))
    elif args.cmd == "ungraphed":
        print(json.dumps(find_ungraphed_papers(args.tag, limit=args.limit), indent=2, default=str))


if __name__ == "__main__":
    main()
