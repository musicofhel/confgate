"""confgate paper-triage — Phase 1 relevance gate (admit.py).

Pull-model admitter (decision #4 forbids editing link-forge's push bridge). It:

  1. DISCOVERS candidate papers from the dated sweep JSON that
     ``research-sweep.ts`` wrote (``--from-sweep <project>``), falling back to
     ``queue.db`` (``--from-queue <project>``) or an explicit arxiv-id list.
  2. Extracts a strict arxiv id from each URL (clone of link-forge's
     ``extractArxivId``); non-arxiv URLs get a ``sha1(url)[:16]`` synthetic id.
  3. Resolves the matching ``:Link`` in link-forge (READ ONLY) by
     arxiv-id-NORMALIZED match (Gap 7 — not exact URL) and COPIES the stored
     384-dim MiniLM ``embedding`` + ``forgeScore`` rather than re-embedding.
  4. Runs a lean-inclusive relevance check (``claude -p`` by default, injectable
     for tests) against the CF-N / CH-N one-liners.
  5. On admit, MERGEs ``(:Paper {status:'pending_triage'})`` into confgate's OWN
     graph (bolt 7689) plus ``(:Paper)-[:TAGGED]->(:Tag {name:'CF-N'|'CH-N'})``
     grouping-seed edges.

Idempotent (MERGE), re-runnable, ``--dry-run`` returns a plan and writes nothing.
Graceful-degrade: a missing sweep JSON or unreachable link-forge warns and
copes (no embedding) rather than crashing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import urlparse

# research-graph/ is not a package; when run as a script its own dir is on
# sys.path[0], so a flat `import bridge` resolves. Make it robust under pytest
# (which imports this module by path) by ensuring the dir is on sys.path.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

REPO_ROOT = _HERE.parent
FINDINGS_PATH = REPO_ROOT / "FINDINGS.md"
HYPOTHESES_PATH = REPO_ROOT / "HYPOTHESES.md"

# dotenv + neo4j (via bridge) are imported LAZILY below so the pure helpers
# (extractor, context builder) stay importable in the Docker-free unit tier,
# which doesn't install the graph-tooling requirements.
try:
    from dotenv import load_dotenv

    load_dotenv(_HERE / ".env")  # override=False: CI/test env wins
except ImportError:
    pass

RelevanceFn = Callable[["Candidate", str], dict[str, Any]]


# ---------------------------------------------------------------------------
# arxiv id extraction (clone of link-forge research-graph-suggest.ts)
# ---------------------------------------------------------------------------

# Strict: a YYMM.NNNNN with digit boundaries and a valid month. The (?!\d)
# right boundary means a trailing version suffix (v2) is naturally stripped.
_ARXIV_RE = re.compile(r"(?<!\d)(\d{2})(\d{2})\.(\d{4,5})(?!\d)")


def extract_arxiv_id(url: str) -> str | None:
    """Strictly extract an arxiv id from a *genuine* arxiv URL only.

    The host MUST be ``arxiv.org`` (or a subdomain). This rejects URLs like
    ``https://example.com/papers/2410.13640.html`` that merely contain an
    arxiv-shaped substring — admitting those would fabricate ids that pollute
    the triage pipeline. Mirrors link-forge's ``extractArxivId`` exactly.
    """
    try:
        host = (urlparse(url).hostname or "").lower()
    except (ValueError, TypeError):
        return None
    if host != "arxiv.org" and not host.endswith(".arxiv.org"):
        return None
    m = _ARXIV_RE.search(url)
    if not m:
        return None
    month = int(m.group(2))
    if month < 1 or month > 12:
        return None
    return f"{m.group(1)}{m.group(2)}.{m.group(3)}"


def synthetic_id(url: str) -> str:
    """Non-arxiv URL → stable synthetic id (mirrors enqueue-research-sweep)."""
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


def candidate_id(url: str) -> str:
    return extract_arxiv_id(url) or synthetic_id(url)


def link_matches_candidate(link_url: str, candidate_arxiv_id: str) -> bool:
    """Gap-7 normalized match: does this :Link.url resolve to this candidate id?

    Applies the SAME strict extractor to the stored link URL and compares bare
    ids, so ``/pdf/2406.18665v2`` matches candidate ``2406.18665`` while a
    spurious substring hit (a longer id) is rejected.
    """
    return extract_arxiv_id(link_url or "") == candidate_arxiv_id


# ---------------------------------------------------------------------------
# Candidate discovery
# ---------------------------------------------------------------------------

@dataclass
class Candidate:
    arxiv_id: str
    url: str
    title: str | None = None
    abstract: str | None = None
    year: Any = None
    is_arxiv: bool = False


def _candidate_from_entry(entry: dict[str, Any]) -> Candidate | None:
    url = entry.get("url")
    if not url:
        return None
    aid = extract_arxiv_id(url)
    return Candidate(
        arxiv_id=aid or synthetic_id(url),
        url=url,
        title=entry.get("title"),
        abstract=entry.get("abstract"),
        year=entry.get("year"),
        is_arxiv=aid is not None,
    )


def discover_from_sweep(project: str, sweep_dir: str) -> list[Candidate]:
    """Read the newest ``research-sweep-<project>-<date>.json`` in ``sweep_dir``."""
    d = Path(os.path.expanduser(sweep_dir))
    matches = sorted(d.glob(f"research-sweep-{project}-*.json"))
    if not matches:
        print(f"[admit] no sweep JSON for project '{project}' in {d} — skipping")
        return []
    latest = matches[-1]  # date-stamped names sort lexically == chronologically
    print(f"[admit] discovery: {latest.name} ({len(matches)} sweep file(s) present)")
    try:
        data = json.loads(latest.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[admit] could not read sweep JSON {latest}: {exc}")
        return []
    out = [c for e in data if (c := _candidate_from_entry(e))]
    return out


def discover_from_queue(project: str, queue_db: str) -> list[Candidate]:
    """Fallback: join ``queue.db`` rows for ``research-sweep:<project>`` (READ ONLY)."""
    db = Path(os.path.expanduser(queue_db))
    if not db.exists():
        print(f"[admit] queue.db not found at {db} — skipping")
        return []
    channel = f"research-sweep:{project}"
    # mode=ro: we NEVER write link-forge's queue.
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = con.execute(
            "SELECT url, comment FROM queue WHERE discord_channel_id = ?",
            (channel,),
        ).fetchall()
    finally:
        con.close()
    out = [c for (url, comment) in rows
           if (c := _candidate_from_entry({"url": url, "abstract": comment}))]
    print(f"[admit] queue discovery: {len(out)} rows for channel '{channel}'")
    return out


def discover_from_ids(arxiv_ids: Iterable[str]) -> list[Candidate]:
    out = []
    for aid in arxiv_ids:
        url = f"https://arxiv.org/abs/{aid}"
        out.append(Candidate(arxiv_id=aid, url=url, is_arxiv=True))
    return out


# ---------------------------------------------------------------------------
# CF/CH relevance context + check
# ---------------------------------------------------------------------------

def build_cf_ch_context(
    findings_path: Path = FINDINGS_PATH,
    hypotheses_path: Path = HYPOTHESES_PATH,
) -> str:
    """One-liner index of every CF-N and CH-N (grep the ### headers)."""
    lines: list[str] = []
    for path, prefix in ((findings_path, "CF"), (hypotheses_path, "CH")):
        text = path.read_text()
        for m in re.finditer(rf"^### ({prefix}-\d+): (.+)$", text, re.MULTILINE):
            lines.append(f"{m.group(1)}: {m.group(2).strip()}")
    return "\n".join(lines)


def known_tag_ids(
    findings_path: Path = FINDINGS_PATH,
    hypotheses_path: Path = HYPOTHESES_PATH,
) -> set[str]:
    """The valid tag namespace — used to reject hallucinated CF/CH tags."""
    ids: set[str] = set()
    for path, prefix in ((findings_path, "CF"), (hypotheses_path, "CH")):
        for m in re.finditer(rf"^### ({prefix}-\d+):", path.read_text(), re.MULTILINE):
            ids.add(m.group(1))
    return ids


_RUBRIC = """\
You are the admission filter for the confgate research graph. confgate ships a
FREE (zero-cost) length+logprob confidence gate for small LLMs. We admit a
paper iff it could plausibly CORROBORATE or CONTRADICT one of our findings
(CF-N) or inform one of our open levers (CH-N) — i.e. it might help BEAT the
free gate or sharpen a certificate.

Lean INCLUSIVE: a false-positive admit is far cheaper than a false-negative
miss. When unsure, admit.

Our findings and open hypotheses:
{context}

Paper under review:
  title: {title}
  abstract: {abstract}

Respond with ONLY a JSON object, no prose:
{{"relevant": true|false,
  "relevance_note": "<one sentence: why it does/doesn't touch confgate>",
  "which_CF_or_CH": ["CF-3", "CH-5"]}}
"""


def build_rubric_prompt(candidate: Candidate, context: str) -> str:
    return _RUBRIC.format(
        context=context,
        title=candidate.title or "(title unavailable)",
        abstract=(candidate.abstract or "(abstract unavailable)")[:3000],
    )


def claude_relevance(candidate: Candidate, context: str) -> dict[str, Any]:
    """Default relevance fn — asks ``claude -p`` and parses the JSON verdict.

    On any tooling/parse error: returns relevant=False with an error note (a
    tooling failure must not silently flood the graph; the rubric itself is
    what leans inclusive on genuine uncertainty).
    """
    prompt = build_rubric_prompt(candidate, context)
    try:
        proc = subprocess.run(
            ["claude", "-p", prompt],
            capture_output=True, text=True, timeout=120,
        )
        raw = proc.stdout.strip()
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        verdict = json.loads(m.group(0) if m else raw)
        return {
            "relevant": bool(verdict.get("relevant")),
            "relevance_note": str(verdict.get("relevance_note", "")),
            "which_CF_or_CH": list(verdict.get("which_CF_or_CH", [])),
        }
    except (subprocess.SubprocessError, json.JSONDecodeError, OSError) as exc:
        print(f"[admit] relevance check failed for {candidate.arxiv_id}: {exc}")
        return {"relevant": False, "relevance_note": f"relevance error: {exc}", "which_CF_or_CH": []}


# ---------------------------------------------------------------------------
# link-forge resolution (READ ONLY) + admission
# ---------------------------------------------------------------------------

def resolve_link(candidate: Candidate, lf_session: Any | None) -> dict[str, Any] | None:
    """Resolve the link-forge :Link for this candidate (Gap-7 normalized match).

    Returns the bridge metadata (incl. embedding + forgeScore) or None if not
    found / link-forge unavailable / the substring match was spurious.
    """
    if lf_session is None or not candidate.is_arxiv:
        return None
    import bridge  # lazy: keeps neo4j out of the unit tier's import path

    meta = bridge.resolve_from_linkforge(candidate.arxiv_id, session=lf_session)
    if meta is None:
        return None
    if not link_matches_candidate(meta.get("url") or "", candidate.arxiv_id):
        return None  # Gap 7: spurious substring hit on a longer id — reject
    return meta


@dataclass
class AdmissionPlan:
    arxiv_id: str
    url: str
    action: str               # 'admit' | 'skip-not-relevant'
    relevance_note: str = ""
    tags: list[str] = field(default_factory=list)
    title: str | None = None
    year: Any = None
    forge_score: Any = None
    has_embedding: bool = False
    embedding: list[float] | None = None
    written: bool = False

    def to_summary(self) -> dict[str, Any]:
        d = {k: v for k, v in self.__dict__.items() if k != "embedding"}
        return d


_WRITE_CYPHER = """
MERGE (p:Paper {arxiv_id: $arxiv_id})
SET p.status = 'pending_triage',
    p.relevance_note = $note,
    p.title = $title,
    p.url = $url,
    p.year = $year,
    p.forge_score = $forge_score,
    p.source = 'admit',
    p.admitted_date = $today
"""

_WRITE_EMBEDDING = "MATCH (p:Paper {arxiv_id: $arxiv_id}) SET p.embedding = $embedding"

_WRITE_TAG = """
MATCH (p:Paper {arxiv_id: $arxiv_id})
MERGE (t:Tag {name: $tag})
MERGE (p)-[:TAGGED]->(t)
"""


def admit(
    candidates: list[Candidate],
    *,
    relevance_fn: RelevanceFn = claude_relevance,
    rg_driver: Any | None = None,
    lf_driver: Any | None = None,
    dry_run: bool = False,
    findings_path: Path = FINDINGS_PATH,
    hypotheses_path: Path = HYPOTHESES_PATH,
) -> list[AdmissionPlan]:
    """Run the relevance gate over ``candidates``; return per-candidate plans.

    Writes to ``rg_driver`` (confgate's graph) only when ``dry_run`` is False.
    Reads ``lf_driver`` (link-forge) READ-ONLY to copy embeddings. Drivers are
    injected so tests can point at throwaway service containers.
    """
    context = build_cf_ch_context(findings_path, hypotheses_path)
    valid_tags = known_tag_ids(findings_path, hypotheses_path)
    today = date.today().isoformat()

    lf_session = lf_driver.session(default_access_mode="READ") if lf_driver else None
    rg_session = rg_driver.session() if (rg_driver and not dry_run) else None

    plans: list[AdmissionPlan] = []
    try:
        for cand in candidates:
            verdict = relevance_fn(cand, context)
            if not verdict.get("relevant"):
                plans.append(AdmissionPlan(
                    arxiv_id=cand.arxiv_id, url=cand.url, action="skip-not-relevant",
                    relevance_note=str(verdict.get("relevance_note", "")),
                    title=cand.title, year=cand.year,
                ))
                continue

            # Keep only tags that name a real CF-N / CH-N.
            tags = sorted({
                t.strip().upper() for t in verdict.get("which_CF_or_CH", [])
                if t.strip().upper() in valid_tags
            })

            meta = resolve_link(cand, lf_session)
            embedding = meta.get("embedding") if meta else None
            forge_score = meta.get("forgeScore") if meta else None
            title = cand.title or (meta.get("title") if meta else None)

            plan = AdmissionPlan(
                arxiv_id=cand.arxiv_id, url=cand.url, action="admit",
                relevance_note=str(verdict.get("relevance_note", "")),
                tags=tags, title=title, year=cand.year,
                forge_score=forge_score,
                has_embedding=embedding is not None,
                embedding=embedding,
            )

            if not dry_run and rg_session is not None:
                rg_session.run(
                    _WRITE_CYPHER,
                    arxiv_id=cand.arxiv_id, note=plan.relevance_note,
                    title=title, url=cand.url, year=cand.year,
                    forge_score=forge_score, today=today,
                )
                if embedding is not None:
                    rg_session.run(_WRITE_EMBEDDING, arxiv_id=cand.arxiv_id, embedding=embedding)
                for tag in tags:
                    rg_session.run(_WRITE_TAG, arxiv_id=cand.arxiv_id, tag=tag)
                plan.written = True

            plans.append(plan)
    finally:
        if lf_session is not None:
            lf_session.close()
        if rg_session is not None:
            rg_session.close()

    return plans


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_drivers() -> tuple[Any | None, Any | None]:
    """Build (rg_driver, lf_driver) from env. link-forge degrades to None."""
    from neo4j import GraphDatabase
    from neo4j.exceptions import AuthError, ServiceUnavailable

    rg = GraphDatabase.driver(
        os.environ.get("NEO4J_BOLT_URL", "bolt://localhost:7689"),
        auth=(os.environ.get("NEO4J_USER", "neo4j"),
              os.environ.get("NEO4J_PASSWORD", "confgate_graph_dev")),
    )
    lf = None
    try:
        lf = GraphDatabase.driver(
            os.environ.get("LINK_FORGE_BOLT_URL", "bolt://localhost:7687"),
            auth=(os.environ.get("LINK_FORGE_USER", "neo4j"),
                  os.environ.get("LINK_FORGE_PASSWORD", "link_forge_dev")),
        )
        lf.verify_connectivity()
    except (ServiceUnavailable, AuthError, OSError) as exc:
        print(f"[admit] link-forge unreachable — admitting without embeddings: {exc}")
        if lf is not None:
            lf.close()
        lf = None
    return rg, lf


def main() -> None:
    p = argparse.ArgumentParser(description="confgate Phase 1 relevance gate")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--from-sweep", metavar="PROJECT",
                     help="discover candidates from the newest sweep JSON")
    src.add_argument("--from-queue", metavar="PROJECT",
                     help="fallback: discover from queue.db research-sweep:<PROJECT>")
    src.add_argument("arxiv_ids", nargs="*", default=[],
                     help="explicit arxiv ids to admit")
    p.add_argument("--dry-run", action="store_true", help="plan only; write nothing")
    args = p.parse_args()

    if args.from_sweep:
        cands = discover_from_sweep(args.from_sweep, os.environ.get("LINK_FORGE_SWEEP_DIR", "~/link-forge/data"))
    elif args.from_queue:
        cands = discover_from_queue(args.from_queue, os.environ.get("LINK_FORGE_QUEUE_DB", "~/link-forge/data/queue.db"))
    else:
        cands = discover_from_ids(args.arxiv_ids)

    if not cands:
        print("[admit] no candidates discovered — nothing to do.")
        return

    rg_driver, lf_driver = _build_drivers()
    try:
        plans = admit(cands, rg_driver=rg_driver, lf_driver=lf_driver, dry_run=args.dry_run)
    finally:
        rg_driver.close()
        if lf_driver is not None:
            lf_driver.close()

    admitted = [pl for pl in plans if pl.action == "admit"]
    print(json.dumps({
        "discovered": len(cands),
        "admitted": len(admitted),
        "skipped": len(plans) - len(admitted),
        "with_embedding": sum(1 for pl in admitted if pl.has_embedding),
        "dry_run": args.dry_run,
        "plans": [pl.to_summary() for pl in plans],
    }, indent=2, default=str))


if __name__ == "__main__":
    main()
