"""Promote a reviewed confgate paper-triage brief into the research repo.

Parses a brief at ``research-graph/briefs/triage-<date>-<arxiv-id>.md`` and:

  1. Extracts YAML ``CG-FE`` blocks from "## Proposed FutureExperiments" -> MERGE
     :FutureExperiment nodes (DEPENDS_ON_FINDING / WOULD_UPDATE -> :Finding(CF-N),
     TRIGGERED_BY -> :Paper, RELIES_ON -> :Premise).
  2. Inserts ``### CH-N`` blocks from "## Proposed HYPOTHESES.md additions" into
     HYPOTHESES.md before the "## Historical / abandoned" anchor.
  3. Folds the deep-extraction subsections under a PAPER_INDEX.md entry.
  4. Writes (:Method|:Dataset)-[:USED_IN]->(:Paper) edges.
  5. Calls bridge.py resolve for the source arxiv id (link-forge enrichment).
  6. Claims gate: refuses if "## New claims" is non-empty AND
     ``research-graph/validate_claims.py`` hasn't been edited since the brief.
  7. Calls generate_next_experiments.py to refresh NEXT_EXPERIMENTS.md.
  8. Sets :Paper{status:'graphed'}.

The brief parser itself is the SHARED, PURE ``brief_parser`` module (Phase 2) —
this script imports ``parse_brief`` / ``validate_future_experiment`` rather than
re-deriving them, so the brief contract has exactly one parser.

Cloned from topo-confidence's promote_brief.py with the 5 mandatory surgeries:
  (1) The NGS research-channel Redis publish (topo step 9) is STRIPPED — no NGS
      bridge in the confgate MVP.
  (2) The embedding-backfill call (topo step 8b) is DISABLED — grouping is
      tag-based, so no PyTorch embedder is introduced (ONNX<->PyTorch drift);
      Papers already carry the copied :Link.embedding from admit.py.
  (3) Claims-gate path repointed to research-graph/validate_claims.py (ROOT).
  (4) bolt/password repointed to the confgate .env (:7689).
  (5) Every namespace regex repointed F-/H-/P11-FE -> CF-/CH-/CG-FE; FE pathway
      pseudo-id is the single "CG". (Load-bearing — renumber() crashes otherwise.)

The repo-root the markdown files live under honors $CONFGATE_REPO_ROOT (defaults
to the actual repo root) so the integration test can run a real promote against
temp copies without dirtying HYPOTHESES.md / PAPER_INDEX.md / NEXT_EXPERIMENTS.md.

Usage:
    python promote_brief.py briefs/triage-2026-06-14-2406.18665.md
    python promote_brief.py briefs/triage-2026-06-14-2406.18665.md --dry-run
    python promote_brief.py briefs/triage-2026-06-14-2406.18665.md --update-existing
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from neo4j import GraphDatabase

# The shared, pure parser shipped in Phase 2 — the single source of truth for the
# brief contract. Do NOT re-derive parsing here.
from brief_parser import (
    DEEP_SUBSECTIONS,
    known_finding_ids,
    parse_brief,
    validate_future_experiment,
)

ROOT = Path(__file__).resolve().parent
# $CONFGATE_REPO_ROOT lets the integration test point the markdown writes at temp
# copies. Defaults to the real repo root (research-graph/..).
REPO = Path(os.environ.get("CONFGATE_REPO_ROOT", ROOT.parent)).resolve()
load_dotenv(ROOT / ".env")

BOLT = os.environ.get("NEO4J_BOLT_URL", "bolt://localhost:7689")
USER = os.environ.get("NEO4J_USER", "neo4j")
PASSWORD = os.environ.get("NEO4J_PASSWORD", "confgate_graph_dev")

BRIEF_FILENAME_RE = re.compile(r"^triage-(\d{4}-\d{2}-\d{2})-(.+)\.md$")
CH_BLOCK_RE = re.compile(r"### CH-(\d+):")

# Single pseudo-pathway for confgate FutureExperiments: CG-FE<n>.
FE_PATHWAY = "CG"
FE_PREFIX = f"{FE_PATHWAY}-FE"


# ---------------------------------------------------------------------------
# Filename
# ---------------------------------------------------------------------------

def parse_filename(path: Path) -> tuple[str, str]:
    m = BRIEF_FILENAME_RE.match(path.name)
    if not m:
        raise SystemExit(
            f"Brief filename '{path.name}' does not match required pattern "
            "triage-YYYY-MM-DD-<arxiv-id>.md"
        )
    return m.group(1), m.group(2)


# ---------------------------------------------------------------------------
# ID renumbering (collision-safe contiguous allocation at promote time)
# ---------------------------------------------------------------------------

def _max_fe(driver) -> int:
    """Largest existing CG-FE number in the graph (0 if none)."""
    with driver.session() as s:
        res = s.run(
            """
            MATCH (fe:FutureExperiment)
            WHERE fe.id STARTS WITH $prefix
            WITH toInteger(substring(fe.id, size($prefix))) AS n
            RETURN max(n) AS max_n
            """,
            prefix=FE_PREFIX,
        ).single()
    return int(res["max_n"]) if res and res["max_n"] is not None else 0


def renumber(parsed: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Remap brief-declared CH-N / CG-FE-N to contiguous IDs from current Next-ID
    state. Mutates `parsed` in place; returns the remap dicts."""
    # CH-N remap: contiguous from HYPOTHESES.md "Next ID: CH-N".
    hyp_text = (REPO / "HYPOTHESES.md").read_text()
    m = re.search(r"Next ID: CH-(\d+)", hyp_text)
    if not m:
        raise SystemExit('No "Next ID: CH-N" line in HYPOTHESES.md.')
    next_h = int(m.group(1))

    h_remap: dict[str, str] = {}
    for i, block in enumerate(parsed["hypotheses_blocks"]):
        hm = CH_BLOCK_RE.match(block)
        if not hm:
            continue
        old = f"CH-{hm.group(1)}"
        new = f"CH-{next_h + i}"
        if old != new:
            h_remap[old] = new

    # CG-FE remap: contiguous from current graph max+1.
    fe_remap: dict[str, str] = {}
    if parsed["future_experiments"]:
        drv = GraphDatabase.driver(BOLT, auth=(USER, PASSWORD))
        try:
            nxt = _max_fe(drv) + 1
        finally:
            drv.close()
        for fe in parsed["future_experiments"]:
            old = fe.get("id", "")
            new = f"{FE_PREFIX}{nxt}"
            nxt += 1
            if old != new:
                fe_remap[old] = new

    full = {**h_remap, **fe_remap}
    if not full:
        return {"h_remap": {}, "fe_remap": {}}

    # Substitute longest keys first so "CH-7" doesn't shadow "CH-72".
    sorted_keys = sorted(full.keys(), key=len, reverse=True)

    def remap_text(text: str) -> str:
        for k in sorted_keys:
            v = full[k]
            text = re.sub(rf"(?<![A-Za-z0-9]){re.escape(k)}(?![0-9])", v, text)
        return text

    # Mutate FE blocks: id, prose fields, blocked-by-experiment cross-refs.
    for fe in parsed["future_experiments"]:
        if fe.get("id") in fe_remap:
            fe["id"] = fe_remap[fe["id"]]
        for fld in ("description", "rationale", "trigger"):
            v = fe.get(fld)
            if isinstance(v, str):
                fe[fld] = remap_text(v)
        bbe = fe.get("blocked-by-experiment")
        if isinstance(bbe, list):
            fe["blocked-by-experiment"] = [fe_remap.get(x, x) for x in bbe]

    # Mutate CH-N blocks, PAPER_INDEX entry, deep subsections, new-claim lines.
    parsed["hypotheses_blocks"] = [remap_text(b) for b in parsed["hypotheses_blocks"]]
    parsed["paper_index_entry"] = remap_text(parsed["paper_index_entry"])
    parsed["deep_subsections"] = {
        k: remap_text(v) for k, v in parsed["deep_subsections"].items()
    }
    parsed["new_claims_lines"] = [remap_text(c) for c in parsed["new_claims_lines"]]

    return {"h_remap": h_remap, "fe_remap": fe_remap}


# ---------------------------------------------------------------------------
# Validate-claims gate (surgery #3: confgate's validate_claims.py is under ROOT)
# ---------------------------------------------------------------------------

def assert_claims_gate(parsed: dict[str, Any], brief_path: Path) -> None:
    if not parsed["new_claims_lines"]:
        print("  no new claims declared — gate skipped")
        return
    validate_path = ROOT / "validate_claims.py"
    if not validate_path.exists():
        raise SystemExit(f"validate_claims.py not found at {validate_path} — abort.")
    if validate_path.stat().st_mtime <= brief_path.stat().st_mtime:
        print("  CLAIMS GATE: brief declares new quantitative claims:")
        for c in parsed["new_claims_lines"]:
            print(f"    - {c}")
        raise SystemExit(
            "validate_claims.py has NOT been modified since the brief — refusing to "
            "promote. Add a cg-* Claim entry per declared new claim, run "
            "`python validate_claims.py`, then re-run promote_brief.py."
        )
    print(f"  ok: {len(parsed['new_claims_lines'])} new claims, "
          "validate_claims.py updated since brief")


# ---------------------------------------------------------------------------
# FutureExperiment writes
# ---------------------------------------------------------------------------

def write_future_experiments(fes: list[dict[str, Any]], dry_run: bool) -> list[str]:
    if not fes:
        print("  no FutureExperiment YAML blocks in brief")
        return []

    # Validate every block against the SHARED contract (brief_parser) — this is
    # the same vocabulary Phase 2's test asserts, plus depends-on -> real CF-N.
    known = known_finding_ids()
    arxiv_ids: set[str] = set()
    problems: list[str] = []
    for fe in fes:
        errs = validate_future_experiment(fe, known_findings=known)
        if errs:
            problems.append(f"{fe.get('id', '?')}: " + "; ".join(errs))
        for arx in fe.get("triggered-by") or []:
            arxiv_ids.add(str(arx))
    if problems:
        raise SystemExit("Invalid CG-FE block(s):\n  - " + "\n  - ".join(problems))

    if dry_run:
        for fe in fes:
            print(f"  Would MERGE FutureExperiment {fe['id']} "
                  f"(priority={fe.get('priority', 'MEDIUM')}, ROI={fe['roi']})")
        return sorted(arxiv_ids)

    from datetime import date as _date
    drv = GraphDatabase.driver(BOLT, auth=(USER, PASSWORD))
    today = _date.today().isoformat()
    try:
        with drv.session() as s:
            for fe in fes:
                s.run(
                    """
                    MERGE (fe:FutureExperiment {id: $id})
                    SET fe.pathway_id = $pathway_id,
                        fe.description = $description,
                        fe.rationale = $rationale,
                        fe.trigger = $trigger,
                        fe.status = $status,
                        fe.blocked_by = $blocked_by,
                        fe.priority = $priority,
                        fe.estimated_cost = $cost,
                        fe.roi_score = $roi,
                        fe.created_date = coalesce(fe.created_date, $today)
                    """,
                    id=fe["id"], pathway_id=fe["pathway"],
                    description=fe["description"], rationale=fe.get("rationale", ""),
                    trigger=fe.get("trigger", ""), status=fe.get("status", "READY"),
                    blocked_by=fe.get("blocked-by"),
                    priority=fe.get("priority", "MEDIUM"),
                    cost=fe.get("cost", ""), roi=int(fe["roi"]), today=today,
                )
                # MERGE (not MATCH) the Pathway so the single "CG" node self-creates.
                s.run(
                    "MERGE (p:Pathway {id: $pid}) "
                    "WITH p MATCH (fe:FutureExperiment {id: $fid}) "
                    "MERGE (p)-[:HAS_FUTURE_EXPERIMENT]->(fe)",
                    pid=fe["pathway"], fid=fe["id"],
                )
                for fnd in (fe.get("depends-on") or []):
                    s.run(
                        "MATCH (fe:FutureExperiment {id: $fid}), (f:Finding {id: $fnd}) "
                        "MERGE (fe)-[:DEPENDS_ON_FINDING]->(f)",
                        fid=fe["id"], fnd=fnd,
                    )
                for fnd in (fe.get("would-update") or []):
                    s.run(
                        "MATCH (fe:FutureExperiment {id: $fid}), (f:Finding {id: $fnd}) "
                        "MERGE (fe)-[:WOULD_UPDATE]->(f)",
                        fid=fe["id"], fnd=fnd,
                    )
                for arx in (fe.get("triggered-by") or []):
                    s.run("MERGE (:Paper {arxiv_id: $a})", a=arx)
                    s.run(
                        "MATCH (fe:FutureExperiment {id: $fid}), (p:Paper {arxiv_id: $a}) "
                        "MERGE (fe)-[:TRIGGERED_BY]->(p)",
                        fid=fe["id"], a=arx,
                    )
                born_mooted = None
                for premise in (fe.get("relies-on") or []):
                    rec = s.run(
                        """
                        MATCH (fe:FutureExperiment {id: $fid}), (pr:Premise {id: $pid})
                        MERGE (fe)-[:RELIES_ON]->(pr)
                        RETURN pr.status AS status, pr.refuted_by AS refuted_by,
                               pr.reason AS reason
                        """,
                        fid=fe["id"], pid=premise,
                    ).single()
                    if rec is None:
                        print(f"  WARNING: FE {fe['id']} relies-on unknown premise "
                              f"{premise!r} — edge skipped. Known: python premises.py list")
                    elif rec["status"] == "REFUTED":
                        born_mooted = (premise, rec["refuted_by"], rec["reason"])
                if born_mooted and fe.get("status", "READY") not in ("COMPLETED", "ABANDONED"):
                    premise, refuted_by, reason = born_mooted
                    s.run(
                        """
                        MATCH (fe:FutureExperiment {id: $fid})
                        SET fe.status = 'MOOTED', fe.outcome = $outcome,
                            fe.closed_by = $by, fe.completed_date = $today
                        WITH fe MATCH (pr:Premise {id: $pid})
                        MERGE (fe)-[r:MOOTED_BY]->(pr)
                        SET r.reason = $outcome, r.date = $today
                        """,
                        fid=fe["id"], pid=premise, by=refuted_by or premise,
                        outcome=f"Born MOOTED — relies on refuted premise "
                                f"'{premise}' ({reason})",
                        today=today,
                    )
                    print(f"  ok FutureExperiment {fe['id']} — born MOOTED "
                          f"(premise '{premise}' already refuted)")
                    continue
                print(f"  ok FutureExperiment {fe['id']}")
    finally:
        drv.close()
    return sorted(arxiv_ids)


# ---------------------------------------------------------------------------
# Markdown insertions
# ---------------------------------------------------------------------------

def _h_block_bounds(text: str, h_n: int) -> tuple[int, int] | None:
    m = re.search(rf"^### CH-{h_n}:", text, re.MULTILINE)
    if not m:
        return None
    start = m.start()
    next_h = re.search(r"^### CH-\d+:", text[m.end():], re.MULTILINE)
    next_section = re.search(r"^## ", text[m.end():], re.MULTILINE)
    candidates = [c.start() + m.end() for c in [next_h, next_section] if c]
    end = min(candidates) if candidates else len(text)
    return (start, end)


def insert_hypotheses(blocks: list[str], dry_run: bool, update_existing: bool) -> None:
    if not blocks:
        print("  no CH-N blocks in brief")
        return
    path = REPO / "HYPOTHESES.md"
    text = path.read_text()

    next_id_match = re.search(r"Next ID: CH-(\d+)", text)
    if not next_id_match:
        raise SystemExit('No "Next ID: CH-N" line found in HYPOTHESES.md.')
    next_id = int(next_id_match.group(1))

    declared_ids = []
    for block in blocks:
        m = CH_BLOCK_RE.match(block)
        if not m:
            raise SystemExit(f"Block lacks ### CH-N: header:\n{block[:200]}")
        declared_ids.append(int(m.group(1)))

    new_blocks: list[str] = []
    update_blocks: list[tuple[int, str]] = []
    for h_n, block in zip(declared_ids, blocks):
        if h_n < next_id:
            if not update_existing:
                raise SystemExit(
                    f"CH-{h_n} already exists in HYPOTHESES.md and --update-existing "
                    "was not passed. Drop the block from the brief or re-run with "
                    "--update-existing to replace it in place."
                )
            update_blocks.append((h_n, block))
        else:
            new_blocks.append(block)

    expected_new = list(range(next_id, next_id + len(new_blocks)))
    actual_new = [int(CH_BLOCK_RE.match(b).group(1)) for b in new_blocks]  # type: ignore[union-attr]
    if actual_new != expected_new:
        raise SystemExit(
            f"New CH-N IDs {actual_new} do not match contiguous sequence starting "
            f"from current Next ID CH-{next_id}: expected {expected_new}."
        )

    new_text = text

    for h_n, block in update_blocks:
        bounds = _h_block_bounds(new_text, h_n)
        if not bounds:
            raise SystemExit(f"Could not locate CH-{h_n} block to update.")
        start, end = bounds
        tail = new_text[start:end]
        trailing = "\n\n" if tail.endswith("\n\n") else ("\n" if tail.endswith("\n") else "")
        new_text = new_text[:start] + block.strip() + trailing + new_text[end:]

    if new_blocks:
        new_next = next_id + len(new_blocks)
        hist_anchor = "## Historical / abandoned"
        if hist_anchor not in new_text:
            raise SystemExit("Historical-section anchor not found in HYPOTHESES.md.")
        insertion = "\n" + "\n\n".join(new_blocks) + "\n\n---\n\n"
        new_text = new_text.replace(f"Next ID: CH-{next_id}.", f"Next ID: CH-{new_next}.")
        new_text = new_text.replace(hist_anchor, insertion + hist_anchor)
    else:
        new_next = next_id

    if dry_run:
        if update_blocks:
            print(f"  Would update {len(update_blocks)} existing CH-N block(s): "
                  f"{[h for h, _ in update_blocks]}")
        if new_blocks:
            print(f"  Would insert {len(new_blocks)} new CH-N block(s): {actual_new}")
            print(f"  Would update Next ID: CH-{next_id} -> CH-{new_next}")
        if not update_blocks and not new_blocks:
            print("  (nothing to do)")
    else:
        path.write_text(new_text)
        if update_blocks:
            print(f"  ok HYPOTHESES.md replaced {len(update_blocks)} block(s): "
                  f"{[h for h, _ in update_blocks]}")
        if new_blocks:
            print(f"  ok HYPOTHESES.md appended {len(new_blocks)} new block(s), "
                  f"Next ID -> CH-{new_next}")


def _paper_index_entry_bounds(text: str, arxiv_id: str) -> tuple[int, int] | None:
    pattern = rf"^## {re.escape(arxiv_id)}(\s|—|-)"
    m = re.search(pattern, text, re.MULTILINE)
    if not m:
        m = re.search(rf"^## .*{re.escape(arxiv_id)}", text, re.MULTILINE)
        if not m:
            return None
    start = m.start()
    next_h = re.search(r"^## ", text[m.end():], re.MULTILINE)
    end = next_h.start() + m.end() if next_h else len(text)
    return (start, end)


def _build_paper_index_block(entry: str, deep_subsections: dict[str, str]) -> str:
    parts = [entry.strip()]
    for _section_key, sub_heading in DEEP_SUBSECTIONS:
        body = deep_subsections.get(sub_heading)
        if not body:
            continue
        parts.append(f"\n{sub_heading}\n\n{body.strip()}")
    return "\n".join(parts).rstrip() + "\n"


def append_paper_index(entry: str, deep_subsections: dict[str, str], arxiv_id: str,
                       dry_run: bool, update_existing: bool) -> None:
    if not entry:
        print("  no PAPER_INDEX.md entry in brief")
        return
    path = REPO / "PAPER_INDEX.md"
    text = path.read_text()
    block = _build_paper_index_block(entry, deep_subsections)
    bounds = _paper_index_entry_bounds(text, arxiv_id)
    extra_subs = list(deep_subsections.keys())

    if bounds:
        if not update_existing:
            raise SystemExit(
                f"PAPER_INDEX.md already has an entry for {arxiv_id}. "
                "Re-run with --update-existing to replace it in place."
            )
        if dry_run:
            print(f"  Would replace existing PAPER_INDEX.md entry for {arxiv_id} "
                  f"({len(extra_subs)} deep subsection(s) folded in)")
            return
        start, end = bounds
        new_text = text[:start] + block.rstrip() + "\n\n" + text[end:]
        path.write_text(new_text.rstrip() + "\n")
        print(f"  ok PAPER_INDEX.md entry for {arxiv_id} replaced in place "
              f"(+{len(extra_subs)} deep subsection(s))")
        return

    if dry_run:
        print(f"  Would append PAPER_INDEX.md entry for {arxiv_id} "
              f"({len(extra_subs)} deep subsection(s))")
        return
    path.write_text(text.rstrip() + "\n\n" + block)
    print(f"  ok PAPER_INDEX.md appended (+{len(extra_subs)} deep subsection(s))")


# ---------------------------------------------------------------------------
# Method/Dataset edges, bridge resolve, status='graphed', regen
# ---------------------------------------------------------------------------

def write_method_dataset_edges(arxiv_id: str, method_names: list[str],
                               dataset_names: list[str], dry_run: bool) -> None:
    methods = [m for m in (n.strip() for n in method_names) if m]
    datasets = [d for d in (n.strip() for n in dataset_names) if d]
    if not methods and not datasets:
        print("  no methods/datasets to write")
        return
    if dry_run:
        if methods:
            print(f"  Would MERGE {len(methods)} :Method node(s): {methods}")
        if datasets:
            print(f"  Would MERGE {len(datasets)} :Dataset node(s): {datasets}")
        return
    drv = GraphDatabase.driver(BOLT, auth=(USER, PASSWORD))
    with drv.session() as s:
        for name in methods:
            s.run(
                """
                MERGE (m:Method {key: $key})
                  ON CREATE SET m.display_name = $name
                  ON MATCH SET m.display_name = coalesce(m.display_name, $name)
                """,
                key=name.lower(), name=name,
            )
            s.run("MATCH (m:Method {key: $key}), (p:Paper {arxiv_id: $a}) "
                  "MERGE (m)-[:USED_IN]->(p)", key=name.lower(), a=arxiv_id)
        for name in datasets:
            s.run(
                """
                MERGE (d:Dataset {key: $key})
                  ON CREATE SET d.display_name = $name
                  ON MATCH SET d.display_name = coalesce(d.display_name, $name)
                """,
                key=name.lower(), name=name,
            )
            s.run("MATCH (d:Dataset {key: $key}), (p:Paper {arxiv_id: $a}) "
                  "MERGE (d)-[:USED_IN]->(p)", key=name.lower(), a=arxiv_id)
    drv.close()
    print(f"  ok wrote {len(methods)} :Method / {len(datasets)} :Dataset edge(s)")


def resolve_papers(arxiv_ids: list[str], primary_arxiv: str, dry_run: bool) -> None:
    all_ids = sorted(set(arxiv_ids + [primary_arxiv]))
    for arx in all_ids:
        if dry_run:
            print(f"  Would call bridge.py resolve {arx}")
            continue
        res = subprocess.run(
            [sys.executable, str(ROOT / "bridge.py"), "resolve", arx],
            capture_output=True, text=True,
        )
        if res.returncode != 0:
            print(f"  bridge.py resolve {arx} non-zero (continuing): {res.stderr.strip()}")
        else:
            print(f"  ok bridge.py resolve {arx}")


def set_paper_graphed(arxiv_id: str, dry_run: bool) -> None:
    if dry_run:
        print(f"  Would set Paper {arxiv_id} status='graphed'")
        return
    drv = GraphDatabase.driver(BOLT, auth=(USER, PASSWORD))
    with drv.session() as s:
        s.run("MERGE (p:Paper {arxiv_id: $a}) SET p.status = 'graphed'", a=arxiv_id)
    drv.close()
    print(f"  ok Paper {arxiv_id} status='graphed'")


def regen_next_experiments(dry_run: bool) -> None:
    if dry_run:
        print("  Would call generate_next_experiments.py")
        return
    res = subprocess.run(
        [sys.executable, str(ROOT / "generate_next_experiments.py")],
        capture_output=True, text=True,
    )
    if res.returncode != 0:
        print("  generate_next_experiments.py FAILED:")
        print(res.stdout)
        print(res.stderr)
        raise SystemExit(res.returncode)
    last = res.stdout.strip().splitlines()[-1] if res.stdout.strip() else "regenerated"
    print(f"  ok {last}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("brief", help="Path to triage brief markdown file")
    p.add_argument("--dry-run", action="store_true",
                   help="Print what would happen without writing")
    p.add_argument("--update-existing", action="store_true",
                   help="Re-promote a brief whose CH-N / PAPER_INDEX entries "
                        "already exist. Replaces them in place idempotently.")
    p.add_argument("--no-renumber", action="store_true",
                   help="Use the brief's exact CH-N / CG-FE-N IDs verbatim.")
    args = p.parse_args()

    brief_path = Path(args.brief).expanduser().resolve()
    if not brief_path.exists():
        raise SystemExit(f"Brief not found: {brief_path}")

    date_str, arxiv_id = parse_filename(brief_path)
    mode_tags = ["DRY-RUN" if args.dry_run else "APPLY"]
    if args.update_existing:
        mode_tags.append("UPDATE-EXISTING")
    print(f"=== promote_brief: {brief_path.name} ===")
    print(f"date={date_str}  arxiv_id={arxiv_id}  mode={' / '.join(mode_tags)}")

    parsed = parse_brief(brief_path)
    print(f"\nparsed: {len(parsed['future_experiments'])} FE blocks, "
          f"{len(parsed['hypotheses_blocks'])} CH-N blocks, "
          f"paper_index_entry={'yes' if parsed['paper_index_entry'] else 'no'}, "
          f"new_claims={len(parsed['new_claims_lines'])}, "
          f"deep subsections={len(parsed['deep_subsections'])}, "
          f"methods={len(parsed['method_names'])}, "
          f"datasets={len(parsed['dataset_names'])}")

    if args.no_renumber:
        print("\nstep 0: renumber (skipped — --no-renumber)")
    else:
        print("\nstep 0: renumber to contiguous IDs from current Next-ID state")
        remaps = renumber(parsed)
        for old, new in sorted(remaps["h_remap"].items()):
            print(f"  CH remap: {old} -> {new}")
        for old, new in sorted(remaps["fe_remap"].items()):
            print(f"  FE remap: {old} -> {new}")
        if not remaps["h_remap"] and not remaps["fe_remap"]:
            print("  (no IDs needed renumbering)")

    print("\nstep 1: validate-claims gate")
    assert_claims_gate(parsed, brief_path)

    print("\nstep 2: FutureExperiment writes")
    arxiv_from_fes = write_future_experiments(parsed["future_experiments"], args.dry_run)

    print("\nstep 3: HYPOTHESES.md")
    insert_hypotheses(parsed["hypotheses_blocks"], args.dry_run, args.update_existing)

    print("\nstep 4: PAPER_INDEX.md (with deep-extraction subheadings)")
    append_paper_index(parsed["paper_index_entry"], parsed["deep_subsections"],
                       arxiv_id, args.dry_run, args.update_existing)

    print("\nstep 5: :Method / :Dataset graph edges")
    write_method_dataset_edges(arxiv_id, parsed["method_names"],
                               parsed["dataset_names"], args.dry_run)

    print("\nstep 6: bridge.py resolve (link-forge enrichment)")
    resolve_papers(arxiv_from_fes, arxiv_id, args.dry_run)

    print("\nstep 7: regenerate NEXT_EXPERIMENTS.md")
    regen_next_experiments(args.dry_run)

    print("\nstep 8: set Paper status='graphed'")
    set_paper_graphed(arxiv_id, args.dry_run)

    # surgery #2: the topo step-8b embedding backfill is DISABLED here (tag-based
    #   grouping needs no FE/Paper embedder).
    # surgery #1: the topo step-9 NGS research-channel publish is STRIPPED here.

    print()
    print("Dry run complete." if args.dry_run else "DONE. Brief is now promoted.")


if __name__ == "__main__":
    main()
