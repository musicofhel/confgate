"""Shared helpers for the research-graph test tier (importable by tests + conftest)."""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_CYPHER = REPO_ROOT / "research-graph" / "schema.cypher"
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def bootstrap_repo(tmp_path: Path) -> Path:
    """A throwaway $CONFGATE_REPO_ROOT seeded with the *frozen Phase-0 bootstrap*
    copies of the markdown files promote mutates (HYPOTHESES.md at ``Next ID:
    CH-7`` with CH-1..6 + the insertion anchor; the PAPER_INDEX stub).

    Deliberately NOT a copy of the live canonical files: those advance every time
    the pipeline promotes a brief (e.g. CH-7..N), which would silently break the
    renumber math the promote tests assert (CH-57 -> CH-7, Next ID -> CH-8). The
    fixtures keep the integration tier hermetic and stable across promotes.
    """
    for name in ("HYPOTHESES.md", "PAPER_INDEX.md"):
        src = FIXTURES / f"{name.removesuffix('.md')}.bootstrap.md"
        (tmp_path / name).write_text(src.read_text())
    return tmp_path


def split_cypher_statements(text: str) -> list[str]:
    """Strip // line-comments and split a .cypher file into runnable statements."""
    lines = []
    for line in text.splitlines():
        if line.lstrip().startswith("//"):
            continue
        lines.append(line)
    body = "\n".join(lines)
    return [s.strip() for s in body.split(";") if s.strip()]
