"""Seed the CF-1…CF-8 :Finding nodes into the confgate graph (bolt :7689).

The grouping view (`query.py grouped`) joins
``(:FutureExperiment)-[:DEPENDS_ON_FINDING]->(:Finding {id})`` and
``promote_brief.py`` writes that edge with a *MATCH* on the Finding — so without
the Finding nodes the experiment-side of every lever stays empty (the paper-side,
keyed on :Tag, works regardless). This idempotently MERGEs one :Finding per
``### CF-N:`` header in FINDINGS.md, using the header text as the claim, so the
dev graph's grouping is complete and `query.py novelty` has finding nodes to hit.

Run once after `make up && make schema`:  python seed_findings.py
"""
from __future__ import annotations

import os
import re
from pathlib import Path

# dotenv + neo4j are imported LAZILY in main() so the pure parser
# (parse_findings) stays importable in the Docker-free unit tier, which installs
# neither — same discipline as admit.py.

ROOT = Path(__file__).resolve().parent
FINDINGS = ROOT.parent / "FINDINGS.md"

CF_HEADER = re.compile(r"^### (CF-\d+): (.+)$", re.MULTILINE)

MERGE_FINDING = """
MERGE (f:Finding {id: $id})
SET f.claim = $claim, f.strength = 'strong', f.status = 'ACTIVE', f.source = 'seed'
"""


def parse_findings(path: Path = FINDINGS) -> list[tuple[str, str]]:
    return [(m.group(1), m.group(2).strip()) for m in CF_HEADER.finditer(path.read_text())]


def main() -> None:
    from dotenv import load_dotenv
    from neo4j import GraphDatabase

    load_dotenv(ROOT / ".env")
    bolt = os.environ.get("NEO4J_BOLT_URL", "bolt://localhost:7689")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD", "confgate_graph_dev")

    findings = parse_findings()
    if not findings:
        raise SystemExit(f"No '### CF-N:' headers found in {FINDINGS}.")
    drv = GraphDatabase.driver(bolt, auth=(user, password))
    with drv.session() as s:
        for fid, claim in findings:
            s.run(MERGE_FINDING, id=fid, claim=claim)
    drv.close()
    print(f"seeded {len(findings)} :Finding node(s): {', '.join(f for f, _ in findings)}")


if __name__ == "__main__":
    main()
