"""validate_claims.py — the confgate research-graph claims ledger.

Every quantitative number this triage pipeline asserts about confgate's findings
(CF-1..CF-8) is registered here as a :Claim, sourced VERBATIM from the shipped
package's pinned result file ``confgate/data/pinned_meta.json``. confgate is a
*downstream consumer* of the topo-confidence experiments — it owns no NPZ caches —
so every CF anchor is ``kind="external"`` (REGISTERED, no project-side readback),
exactly like topo's external paper anchors. New ``cg-*`` claims minted by promoted
triage briefs go in the same ledger.

Run:  python validate_claims.py

This file is also the **claims gate** ``promote_brief.py`` checks: if a brief
declares new ``cg-*`` claims and this file's mtime is older than the brief, the
promote refuses until a Claim entry is added here. So *touching this file is the
deliberate act of accepting a new claim.*

Smoke contract: every entry is REGISTERED (or PASS for any future internal
readback) and the process exits 0.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
PINNED = REPO / "confgate" / "data" / "pinned_meta.json"


def _load_anchors() -> dict[str, Any]:
    return json.loads(PINNED.read_text())["anchors"]


def _drill(d: Any, path: list[str | int]) -> Any:
    cur = d
    for p in path:
        cur = cur[p]
    return cur


@dataclass
class Claim:
    cid: str
    description: str
    expected: Any
    # `kind` controls readback semantics, mirroring topo's validate_claims.py:
    #   "external"        — registered, no project-side readback. Result=REGISTERED.
    #   "internal"        — back-check against a confgate-side JSON (none yet).
    #   "forward_looking" — a CG-FE acceptance threshold, live once its result
    #                       JSON lands. Result=PENDING_FE.
    kind: str = "external"
    labels: str = "external_anchor"
    cf: str = ""          # which CF-N / CH-N this anchor underpins
    note: str = ""
    result: str = field(default="", init=False)


# --- CLAIMS ------------------------------------------------------------------
# The 8 CF anchors, values pulled live from pinned_meta.json so they can never
# drift from the shipped package.
_A = _load_anchors()

CLAIMS: list[Claim] = [
    Claim("cg-cf1-loco-free-auroc",
          "CF-1: free length+logprob in-domain T1 LOCO OOF AUROC",
          _drill(_A, ["in_domain_qwen1.5b", "t1_loco_free_baseline_auroc"]),
          cf="CF-1"),
    Claim("cg-cf1-t3-crossscale-free-auroc",
          "CF-1: free baseline T3 cross-scale OOF AUROC",
          _drill(_A, ["in_domain_qwen1.5b", "t3_crossscale_free_baseline_auroc"]),
          cf="CF-1"),
    Claim("cg-cf1-t5-smollm2-free-auroc",
          "CF-1: T5 held-out SmolLM2-1.7B free-baseline OOF AUROC",
          _drill(_A, ["t5_heldout_oof", "smollm2-1.7b", "free_baseline_auroc"]),
          cf="CF-1"),
    Claim("cg-cf1-t5-gemma-free-auroc",
          "CF-1: T5 held-out Gemma-2-2b free-baseline OOF AUROC",
          _drill(_A, ["t5_heldout_oof", "gemma-2-2b", "free_baseline_auroc"]),
          cf="CF-1"),
    Claim("cg-cf1-t5-olmo-free-auroc",
          "CF-1: T5 held-out OLMo-2-1B free-baseline OOF AUROC",
          _drill(_A, ["t5_heldout_oof", "olmo-2-1b", "free_baseline_auroc"]),
          cf="CF-1"),
    Claim("cg-cf2-smollm2-length-only-auroc",
          "CF-2: which-scalar-carries — SmolLM2 length-only AUROC ~ free (logprob ~ chance)",
          _drill(_A, ["t5_heldout_oof", "smollm2-1.7b", "length_only_auroc"]),
          cf="CF-2"),
    Claim("cg-cf3-hybrid-cascade-gap-pp",
          "CF-3: gate-ordered hybrid cascade beats the convex hull by +pp at matched cost (SIG)",
          _drill(_A, ["cascade", "hybrid_beats_hull_gap_pp"]),
          cf="CF-3"),
    Claim("cg-cf4-crossscale-cert-validity-k64",
          "CF-4: cross-scale 1.5B->7B conformal cert validity at eps=0.2, k=64",
          _drill(_A, ["conformal", "cross_scale_math1.5b_to_7b_eps0.2", "k64", "validity"]),
          cf="CF-4"),
    Claim("cg-cf5-crossdomain-cert-validity-k0",
          "CF-5: cross-domain MATH->BBH cert validity = 0.0 (infeasible) at eps=0.2",
          _drill(_A, ["conformal", "cross_domain_math_to_bbh_eps0.2", "k0", "validity"]),
          cf="CF-5"),
    Claim("cg-cf6-mondrian-prealgebra-validity",
          "CF-6: in-domain Mondrian group-conditional cert validity (prealgebra, k=32)",
          _drill(_A, ["conformal", "group_conditional_in_domain_math_eps0.2",
                      "certifiable_groups", "prealgebra", "validity"]),
          cf="CF-6"),
    Claim("cg-cf7-preflight-promptlen-auroc",
          "CF-7: preflight prompt-length-only OOF AUROC (~0.71; prompt-cloud adds nothing)",
          _drill(_A, ["preflight", "prompt_length_only_auroc"]),
          cf="CF-7"),
    Claim("cg-cf8-basewap-cascade-acc",
          "CF-8: base-swap escalation target (Qwen2.5-Math-7B) cascade accuracy",
          _drill(json.loads(PINNED.read_text()),
                 ["v8_frontier", "pinned_escalation_target", "cascade_acc"]),
          cf="CF-8"),
]


def _check(c: Claim) -> None:
    if c.kind == "external":
        c.result = "REGISTERED"
    elif c.kind == "forward_looking":
        c.result = "PENDING_FE"
    else:
        # No confgate-side internal readback files exist yet; reaching here means
        # a future internal claim was added without wiring a JSON path.
        c.result = "MISSING_FILE"


def main() -> int:
    for c in CLAIMS:
        _check(c)

    pass_n = sum(1 for c in CLAIMS if c.result == "PASS")
    fail_n = sum(1 for c in CLAIMS if c.result.startswith("FAIL"))
    missing = sum(1 for c in CLAIMS if c.result.startswith("MISSING")
                  or c.result.startswith("LOAD_ERROR")
                  or c.result.startswith("KEY_MISSING"))
    registered = sum(1 for c in CLAIMS if c.result == "REGISTERED")
    pending_fe = sum(1 for c in CLAIMS if c.result == "PENDING_FE")

    print(f"# validate_claims.py — {len(CLAIMS)} claims (confgate research-graph ledger)")
    print(f"PASS:        {pass_n}")
    print(f"FAIL:        {fail_n}")
    print(f"MISSING:     {missing}")
    print(f"REGISTERED:  {registered}  (external pinned-result anchors, no project readback)")
    print(f"PENDING_FE:  {pending_fe}  (CG-FE thresholds, live once their result JSON lands)\n")

    hdr = ("ID", "CF", "result", "expected", "description")
    widths = (34, 6, 12, 14, 60)
    line = "  ".join(h.ljust(w) for h, w in zip(hdr, widths))
    print(line)
    print("-" * len(line))
    for c in CLAIMS:
        exp = c.expected
        exp_s = f"{exp:.6g}" if isinstance(exp, float) else str(exp)[:14]
        row = (c.cid[:34], (c.cf or "—")[:6], c.result[:12], exp_s[:14], c.description[:60])
        print("  ".join(r.ljust(w) for r, w in zip(row, widths)))

    issues = [c for c in CLAIMS if c.result not in ("PASS", "REGISTERED", "PENDING_FE")]
    if issues:
        print("\n## Issues requiring attention\n")
        for c in issues:
            print(f"- [{c.cid}] {c.result}: {c.description}")

    return 0 if fail_n == 0 and missing == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
