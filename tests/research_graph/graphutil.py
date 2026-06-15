"""Shared helpers for the research-graph test tier (importable by tests + conftest)."""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_CYPHER = REPO_ROOT / "research-graph" / "schema.cypher"


def split_cypher_statements(text: str) -> list[str]:
    """Strip // line-comments and split a .cypher file into runnable statements."""
    lines = []
    for line in text.splitlines():
        if line.lstrip().startswith("//"):
            continue
        lines.append(line)
    body = "\n".join(lines)
    return [s.strip() for s in body.split(";") if s.strip()]
