"""Packaging guard (Docker-free, unit tier): the shipped wheel must NOT drift.

Builds the wheel into a temp dir and asserts its file-name set is exactly the
13-file v0.1.1 baseline — so research-graph/ tooling, FINDINGS.md, HYPOTHESES.md,
PAPER_INDEX.md, and the test tree can never leak into the published package.
Names only (dist-info content/hash bytes ignored). hatchling-based.
"""
from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Exactly the committed dist/topo_confgate-0.1.1-py3-none-any.whl contents.
BASELINE_WHEEL_FILES = {
    "confgate/__init__.py",
    "confgate/certify.py",
    "confgate/cli.py",
    "confgate/gate.py",
    "confgate/preflight.py",
    "confgate/route.py",
    "confgate/data/pinned_gates.json",
    "confgate/data/pinned_meta.json",
    "topo_confgate-0.1.1.dist-info/METADATA",
    "topo_confgate-0.1.1.dist-info/WHEEL",
    "topo_confgate-0.1.1.dist-info/entry_points.txt",
    "topo_confgate-0.1.1.dist-info/licenses/LICENSE",
    "topo_confgate-0.1.1.dist-info/RECORD",
}


def test_wheel_file_set_matches_baseline(tmp_path):
    out = tmp_path / "wheelhouse"
    subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(out)],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    wheels = list(out.glob("*.whl"))
    assert len(wheels) == 1, f"expected one wheel, got {wheels}"

    with zipfile.ZipFile(wheels[0]) as zf:
        built = {n for n in zf.namelist() if not n.endswith("/")}

    extra = built - BASELINE_WHEEL_FILES
    missing = BASELINE_WHEEL_FILES - built
    assert not extra, f"wheel gained files (tooling leaked into the package!): {sorted(extra)}"
    assert not missing, f"wheel lost files vs v0.1.1 baseline: {sorted(missing)}"
