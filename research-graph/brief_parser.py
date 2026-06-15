"""Shared triage-brief parser for the confgate research graph.

A triage brief (``briefs/triage-YYYY-MM-DD-<arxiv>.md``) is the artifact the
``/confgate-triage`` skill writes. This module is the single source of truth for
turning that markdown into structured data:

  - section bodies keyed by their ``## Heading`` (the brief's deterministic order),
  - the YAML ``CG-FE`` blocks under ``## Proposed FutureExperiments``,
  - the ``### CH-N:`` hypothesis blocks, the PAPER_INDEX entry, new-claim lines,
    and the deep-extraction subsections (methods / datasets / …).

It is namespace-repointed from topo's ``promote_brief.py`` parser: ``F-`` → ``CF-``,
``H-`` → ``CH-``, ``P11-FE`` → ``CG-FE`` (single pseudo-pathway ``CG``). Crucially
it is **pure** — no neo4j, no dotenv, no graph — so it imports cleanly in the
Docker-free unit tier (the Phase-2 tracer test). Phase 3's ``promote_brief.py``
imports ``parse_brief`` / ``validate_future_experiment`` from here rather than
re-deriving them, so the brief contract has exactly one parser.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

_HERE = Path(__file__).resolve().parent
REPO_ROOT = _HERE.parent
FINDINGS_PATH = REPO_ROOT / "FINDINGS.md"

# Top-level section headings the brief is *required* to use, in order. The parser
# uses these as anchors so an embedded `##` inside a section body (e.g. a
# PAPER_INDEX entry that starts with `## <arxiv> —`) is captured as content, not
# split as a new section. Byte-for-byte the topo KNOWN_SECTIONS with F→CF, H→CH.
KNOWN_SECTIONS = [
    "## Refutations",
    "## Direct connections to CF-N / CH-N",
    "## Methodologies extracted",
    "## Approaches & framings",
    "## Datasets & benchmarks",
    "## Implementation details worth capturing",
    "## Replicable intermediates",
    "## Cross-paper signals",
    "## Proposed FutureExperiments",
    "## Proposed HYPOTHESES.md additions",
    "## Proposed PAPER_INDEX.md classification",
    "## New claims",
    "## Sources consulted",
]

# Subheading order for folding deep-extraction sections into a PAPER_INDEX entry.
DEEP_SUBSECTIONS = [
    ("## Methodologies extracted", "### Methodologies extracted"),
    ("## Approaches & framings", "### Approaches & framings"),
    ("## Datasets & benchmarks", "### Datasets & benchmarks"),
    ("## Implementation details worth capturing",
     "### Implementation details worth capturing"),
    ("## Replicable intermediates", "### Replicable intermediates"),
    ("## Cross-paper signals", "### Cross-paper signals"),
]

YAML_BLOCK_RE = re.compile(r"```yaml\n(.*?)\n```", re.DOTALL)
CH_HEADER_RE = re.compile(r"^### CH-\d+:", re.MULTILINE)
NAMED_BULLET_RE = re.compile(r"^\s*-\s*\*\*([^*]+)\*\*", re.MULTILINE)
FE_ID_RE = re.compile(r"^CG-FE(\d+)$")
CF_ID_RE = re.compile(r"^CF-\d+$")

# FE field vocabularies — mirror topo promote_brief.py so Phase 3 stays aligned.
VALID_STATUS = {"READY", "TRIGGERED", "BLOCKED", "COMPLETED", "ABANDONED",
                "MOOTED", "ANSWERED"}
VALID_PRIORITY = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
REQUIRED_FE_FIELDS = ("id", "pathway", "description", "roi")


def _is_empty_section(body: str) -> bool:
    """True if the section is blank or its first line starts with a 'none' marker.

    Briefs write 'none' / 'none extracted' / 'none worth flagging' rather than
    inventing filler, so empty sections don't leak into PAPER_INDEX or the graph.
    """
    stripped = body.strip().lower()
    if not stripped:
        return True
    first_line = stripped.splitlines()[0].strip("-* ").strip()
    return first_line.startswith("none")


def known_finding_ids(findings_path: Path = FINDINGS_PATH) -> set[str]:
    """The valid CF-N namespace, scraped from FINDINGS.md `### CF-N:` headers."""
    if not Path(findings_path).exists():
        return set()
    ids: set[str] = set()
    for m in re.finditer(r"^### (CF-\d+):", Path(findings_path).read_text(), re.MULTILINE):
        ids.add(m.group(1))
    return ids


def parse_brief(source: Path | str) -> dict[str, Any]:
    """Parse a brief (a path or its raw text) into structured fields.

    Returns a dict with: ``sections`` (heading → body), ``future_experiments``
    (list of YAML CG-FE dicts), ``hypotheses_blocks`` (raw ``### CH-N:`` blocks),
    ``paper_index_entry``, ``new_claims_lines``, ``deep_subsections``,
    ``method_names``, ``dataset_names``.
    """
    if isinstance(source, Path) or (isinstance(source, str) and "\n" not in source
                                    and source.endswith(".md")):
        text = Path(source).read_text()
    else:
        text = str(source)

    section_offsets: list[tuple[str, int]] = []
    for heading in KNOWN_SECTIONS:
        idx = text.find("\n" + heading + "\n")
        if idx == -1 and text.startswith(heading + "\n"):
            idx = 0
        elif idx != -1:
            idx += 1
        if idx != -1:
            section_offsets.append((heading, idx))
    section_offsets.sort(key=lambda x: x[1])

    sections: dict[str, str] = {}
    for i, (heading, start) in enumerate(section_offsets):
        body_start = start + len(heading) + 1
        body_end = section_offsets[i + 1][1] if i + 1 < len(section_offsets) else len(text)
        sections[heading] = text[body_start:body_end].strip()

    parsed: dict[str, Any] = {
        "raw": text,
        "sections": sections,
        "future_experiments": [],
        "hypotheses_blocks": [],
        "paper_index_entry": "",
        "new_claims_lines": [],
        "method_names": [],
        "dataset_names": [],
        "deep_subsections": {},
    }

    for section_key, sub_heading in DEEP_SUBSECTIONS:
        body = sections.get(section_key, "")
        if _is_empty_section(body):
            continue
        parsed["deep_subsections"][sub_heading] = body.strip()
        if section_key == "## Methodologies extracted":
            parsed["method_names"] = [m.group(1).strip() for m in NAMED_BULLET_RE.finditer(body)]
        elif section_key == "## Datasets & benchmarks":
            parsed["dataset_names"] = [m.group(1).strip() for m in NAMED_BULLET_RE.finditer(body)]

    fe_section = sections.get("## Proposed FutureExperiments", "")
    for yaml_match in YAML_BLOCK_RE.finditer(fe_section):
        try:
            data = yaml.safe_load(yaml_match.group(1))
        except yaml.YAMLError as e:
            raise ValueError(f"YAML parse error in brief: {e}") from e
        if isinstance(data, list):
            parsed["future_experiments"].extend(data)
        elif isinstance(data, dict):
            parsed["future_experiments"].append(data)

    hyp_section = sections.get("## Proposed HYPOTHESES.md additions", "")
    h_starts = [m.start() for m in CH_HEADER_RE.finditer(hyp_section)]
    for i, start in enumerate(h_starts):
        end = h_starts[i + 1] if i + 1 < len(h_starts) else len(hyp_section)
        block = hyp_section[start:end].strip()
        if block:
            parsed["hypotheses_blocks"].append(block)

    parsed["paper_index_entry"] = sections.get(
        "## Proposed PAPER_INDEX.md classification", ""
    ).strip()

    claims_section = sections.get("## New claims", "")
    parsed["new_claims_lines"] = [
        line.strip("- ").strip()
        for line in claims_section.splitlines()
        if line.strip() and line.strip().startswith("-")
    ]

    return parsed


def validate_future_experiment(
    fe: dict[str, Any],
    known_findings: set[str] | None = None,
) -> list[str]:
    """Return a list of human-readable problems with a CG-FE block (empty == valid).

    Checks the load-bearing contract Phase 3's promote relies on: required fields
    present, ``roi`` an int in [1,10], ``status``/``priority`` in their vocab, ``id``
    shaped ``CG-FE<n>``/``pathway`` ``CG``, and every ``depends-on``/``would-update``
    entry naming a CF-N (in ``known_findings`` when supplied).
    """
    errors: list[str] = []
    if not isinstance(fe, dict):
        return [f"FE block is not a mapping: {fe!r}"]

    for required in REQUIRED_FE_FIELDS:
        if required not in fe or fe[required] in (None, ""):
            errors.append(f"missing required field '{required}'")

    fe_id = fe.get("id")
    if isinstance(fe_id, str) and not FE_ID_RE.match(fe_id):
        errors.append(f"id '{fe_id}' is not shaped CG-FE<n>")
    if fe.get("pathway") not in (None, "CG"):
        errors.append(f"pathway must be 'CG', got {fe.get('pathway')!r}")

    if "roi" in fe and fe["roi"] not in (None, ""):
        try:
            roi = int(fe["roi"])
            if not (1 <= roi <= 10):
                errors.append(f"roi out of [1,10]: {roi}")
        except (TypeError, ValueError):
            errors.append(f"roi not an integer: {fe['roi']!r}")

    if fe.get("status", "READY") not in VALID_STATUS:
        errors.append(f"invalid status {fe.get('status')!r}")
    if fe.get("priority", "MEDIUM") not in VALID_PRIORITY:
        errors.append(f"invalid priority {fe.get('priority')!r}")

    for field in ("depends-on", "would-update"):
        refs = fe.get(field) or []
        if not isinstance(refs, list):
            errors.append(f"{field} must be a list, got {refs!r}")
            continue
        for ref in refs:
            if not (isinstance(ref, str) and CF_ID_RE.match(ref)):
                errors.append(f"{field} entry '{ref}' is not a CF-N id")
            elif known_findings is not None and ref not in known_findings:
                errors.append(f"{field} references unknown finding '{ref}'")

    return errors
