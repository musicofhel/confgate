# /confgate-triage

Deep triage of a single arxiv paper for the **confgate** research program — the
free length+logprob confidence gate. Produces a structured brief at
`~/confgate/research-graph/briefs/triage-YYYY-MM-DD-<arxiv-id>.md` that a human
or agent can review and feed to `promote_brief.py` (Phase 3).

This is a clone of the topo-confidence `paper-triage` skill, repointed to
confgate's `CF-`/`CH-`/`CG-FE` namespace. The triage **goal is different**: every
brief should propose `:FutureExperiment` levers that could **beat the free gate** —
raise its OOF AUROC, beat the gate-ordered cascade at matched cost, crack the
cross-domain certificate wall, or find a better base-swap / escalation target.

## Usage

`/confgate-triage <arxiv-id>` — e.g. `/confgate-triage 2406.18665`

## How it works

### Step 0: Check for existing brief

```bash
ls ~/confgate/research-graph/briefs/triage-*-<arxiv-id>.md 2>/dev/null
```

If a brief already exists, report it and ask whether to overwrite or skip.

### Step 1: Load default context (NOTHING ELSE until Refutations is written)

Load these in order. Do **not** load anything else until after the Refutations
section is written — this ordering is a confirmation-bias defense per Ríos-García
`2604.18805` (68% in agent traces). Loading the full FINDINGS/HYPOTHESES bodies
makes the model fit the paper into existing frames instead of finding refutations.

1. CF-N + CH-N one-liners (the success factors and the levers):
   ```bash
   grep -E "^### (CF|CH)-[0-9]+:" ~/confgate/FINDINGS.md ~/confgate/HYPOTHESES.md
   ```
2. The pinned headline anchors (the only numbers you may cite — they come
   verbatim from the shipped package):
   ```bash
   python3 -c "import json;d=json.load(open('$HOME/confgate/confgate/data/pinned_meta.json'));print(json.dumps(d['anchors'],indent=2))"
   ```
3. Existing PAPER_INDEX status flags (what's already triaged):
   ```bash
   grep -E "^## [0-9]|^\*\*Status:\*\*" ~/confgate/PAPER_INDEX.md
   ```

Do **not** load the full `FINDINGS.md`, `HYPOTHESES.md`, or `NEXT_EXPERIMENTS.md`
by default. On-demand `Read` of a specific `### CF-N:` body is allowed once you
are past Refutations — log every such read in "Sources consulted".

### Step 2: Fetch the paper

Use `mcp__paper-search__read_arxiv_paper` or `mcp__arxiv__read_paper`. If those
fail, fall back to `WebFetch` of `https://arxiv.org/abs/<arxiv-id>`.

### Step 3: Write the brief

Save to `~/confgate/research-graph/briefs/triage-{today}-{arxiv-id}.md`.

The brief must follow this **exact** structure, in this **exact** order (the
section headings are parsed byte-for-byte by `brief_parser.py` — do not rename or
reorder them). Empty sections write `none` rather than invented filler.

```markdown
# Triage brief — <arxiv-id> — <paper title>

Source: https://arxiv.org/abs/<arxiv-id>
Triaged: <today>

## Refutations

List **≥3** distinct ways this paper would *refute* a current CF-N finding or
CH-N lever. Each refutation must:
  - cite a specific CF-N or CH-N (not "their work in general"),
  - name a mechanism by which the refutation would fire,
  - be falsifiable by a concrete experiment.

If you genuinely cannot find ≥3 substantive refutations after a careful read,
write "No genuine refutations identified after [N] minutes — paper is likely
off-topic or purely confirming. Recommend rejection or weak CITED ONLY status."
Do not invent thin refutations just to fill the section.

## Direct connections to CF-N / CH-N

Each connection must cite a specific CF-N or CH-N and the relevant pinned anchor
(e.g. free-gate OOF AUROC SmolLM2 0.810 / Gemma 0.844 / OLMo-2 0.838; cascade
+3.38pp; cross-scale cert validity 1.0 @ 0.60 cov; Qwen2.5-Math base-swap +9.2pp).
On-demand `Read` of `~/confgate/FINDINGS.md` for a specific CF-N is allowed — log
it in "Sources consulted".

## Methodologies extracted

Every technique / probe / metric / loss / training trick the paper uses that
could touch a confidence readout, a routing/cascade policy, a calibration or
conformal procedure, or a small-model base-swap. For each:

- **<method name>** — one-line description.
  *Replication cost*: e.g. "20min CPU", "H100 day", "needs new dataset".
  *We'd plausibly run this*: yes | no — and one phrase on why or why not.

Leave empty (write "none extracted") only if the paper is pure theory with no
method we could borrow.

## Approaches & framings

Theoretical lens shifts, reformulations, conceptual moves. One sentence each.
How does each intersect our CF-N / CH-N framings? Write "none extracted" if the
paper makes only narrow incremental claims with no reusable framing.

## Datasets & benchmarks

Datasets/benchmarks used or introduced, with applicability to the MATH-500 /
BBH / small-model regime confgate ships against. For each:

- **<name>** — size, license, accessibility (HF | gated | proprietary | not
  released). Applicable? yes | no — one phrase.

Leave empty (write "none") if purely theoretical or trivial synthetic data.

## Implementation details worth capturing

Architectures, hyperparameters, schedules, gotchas, code links. Bullet list.
Write "none" if no concrete implementation guidance.

## Replicable intermediates

The smallest cross-check we could run *right now* against the paper's headline
claim with confgate's shipped artifacts (`pinned_meta.json` anchors, the gate /
cascade / certify code). Bullet list naming the artifact / function. Write
"none — paper claims need fresh data we don't have" if no sanity check is possible.

## Cross-paper signals

Papers this paper cites that are (or should be) in our research graph. Format:

- <arxiv-id> — already in graph (status: graphed | pending_triage). Connection.
- <arxiv-id> — NOT in graph; recommend admission. Connection.

Write "none worth flagging" otherwise.

## Proposed FutureExperiments

Propose experiments that could **beat the free gate**. Every paper should produce
AT LEAST one experiment if at all possible. Think abstractly — the paper need not
be about confidence for its method to apply to our readouts / cascade / certs.

One or more YAML blocks with EXACTLY these fields (every field required; the
parser validates `roi ∈ [1,10]`, `status`, `priority`, and that every
`depends-on`/`would-update` entry is a real CF-N):

    ```yaml
    - id: CG-FE<next>
      pathway: CG
      description: "..."
      rationale: "..."
      trigger: "..."
      status: READY
      priority: HIGH
      roi: 8
      cost: "20min CPU"
      depends-on: [CF-1, CF-3]
      would-update: [CF-3]
      triggered-by: ["<arxiv-id>"]
      relies-on: []
    ```

Pick `CG-FE` numbers well above any currently-graphed id (add 50+) to avoid
collisions with concurrent briefs — `promote_brief.py` renumbers to contiguous
ids at promote time. Flag GPU-only experiments with `cost: "H100 ..."` and only
propose them at `roi ≥ 7` (experiment *execution* is out of MVP scope).

## Proposed HYPOTHESES.md additions

CH-N blocks. Pick numbers well above the current Next ID to avoid collisions.

    ### CH-<next>: <one-line lever>
    **Priority:** HIGH | MEDIUM | LOW | PARKED
    **Motivated by:** <arxiv-id> + <relevant CF-N>
    **Test:** <what you'd run, what data, est time>
    **Requires:** <CPU/GPU, model, cached or new data>
    **Would change:** <what shifts on confirm vs reject>
    **Blocks:** <CH-N or "nothing">

Skip (write "none") if the paper motivates only methodology FEs without a new lever.

## Proposed PAPER_INDEX.md classification

    ## <arxiv-id> — <paper title> (<authors>, <year>)

    **Relevance:** <one paragraph — which CF-N / CH-N it touches>

    **Key claim we tested:** <their claim, in our terms>

    **Our result:** **<STATUS>** <one paragraph>

    **Related experiments:** <CG-FE-N, CH-N>

    **Status:** REPLICATED | CONTRADICTED | PARTIALLY CONFIRMED | CITED ONLY | TO TEST

## New claims

Quantitative claims this brief introduces into narrative docs that need a
`validate_claims.py` (`cg-*`) entry. Empty if the brief only quotes pinned numbers.

## Sources consulted

Every file you read on-demand beyond the default context. Format:
    - <path> — <reason>
```

### Step 4: Report

Print the absolute path of the brief. **Do not auto-promote** (MVP keeps promote
a separate, explicit step). Surface the command for review:

```bash
cd ~/confgate/research-graph && python promote_brief.py briefs/triage-{today}-{arxiv-id}.md --dry-run
```

## Hard rules

1. **Refutations first.** Write Refutations before any on-demand `Read` of CF-N
   bodies. This is the confirmation-bias defense.
2. **Use only CF-N / CH-N IDs that exist** (CF-1…CF-8, CH-1…CH-6 currently).
   Verify with the grep from Step 1.
3. **Numbers come only from `pinned_meta.json` anchors.** Never invent or
   restate a number that isn't pinned.
4. **Use high CG-FE / CH-N numbering** to avoid collisions with concurrent briefs.
5. **Brief filename**: exactly `briefs/triage-{today}-{arxiv-id}.md` relative to
   `~/confgate/research-graph/`.
6. **Leave a section empty** (with `none` / `none extracted`) rather than
   inventing filler.
7. **Do NOT auto-promote.** Surface the brief path + the `promote_brief.py`
   command.

## Batch mode

For batch triage of all pending papers:

```bash
cd ~/confgate/research-graph && bash triage_pending.sh
```

This spawns parallel `claude -p` workers using `_confgate_triage_prompt.template`
(same content as this skill). Each worker **writes a brief only** — promotion is a
separate explicit step (`promote_brief.py`), unlike topo's auto-promote.
