---
title: CRITIC trailer — canonical machine-readable verdict footer
summary: The canonical fenced field-schema block (VERDICT, REASON, ROUND, optional FAILED_RULES/FINDINGS_COUNT/ESCALATE) appended at the end of every critic verdict so consumers can parse it programmatically.
tags: [glossary, output-shape, project-jargon, critic]
type: concept
last_updated: 2026-05-26
sources:
  - decisions/0005-output-shape-and-slicing-methodology.md
  - CLAUDE.md
---

# CRITIC trailer

The **CRITIC trailer** is the canonical fenced field-schema block appended at the end of every critic verdict. It exists so cross-agent consumers (`/ship`, future orchestrators, post-run audit scripts) can parse a verdict's disposition mechanically rather than re-reading the prose body. Per [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D1, every one of the 6 critics emits this trailer; the body shape (5-section verdict template) is also standardized, but only the trailer is the machine-readable contract.

**Edges**

- **related-to:** [[concepts/glossary/generator-trailer]]
- **related-to:** [[concepts/glossary/critic]]
- **part-of:** [[topics/output-shapes]]

## What

The trailer is a fenced code block (no language tag) containing line-oriented `KEY: value` pairs. Required fields:

- `VERDICT:` either `APPROVE` or `BLOCK`.
- `REASON:` one sentence summarizing the disposition.
- `ROUND:` `<N>/<max>` (e.g., `1/3`).

Conditional fields fire on BLOCK:

- `FAILED_RULES:` comma-separated rule IDs (e.g., `R-LOC, R-CLOSES`).
- `FINDINGS_COUNT:` integer count of itemized findings.

Conditional field fires on round-max BLOCK:

- `ESCALATE: needs-human` — signals the orchestrator to apply the `needs-human` label per I5.

Permitted critic-specific extensions follow per-critic conventions named in the critic's own body file (e.g., `MERGE_STATUS:` for `reviewer`, scoring extensions for `slicer-critic`). The trailer's shape — fenced block, line-oriented, last in the output — is invariant across critics.

## Why

The trailer exists because **prose verdicts don't compose with orchestration**. The `/ship` skill chains generator-critic pairs; it needs to know "did the critic approve?" without an LLM re-read of the verdict body. A grep-able trailer makes that decision a one-line shell test (`grep '^VERDICT: APPROVE'`) rather than a sub-agent invocation. Post-run audit and the workflow event log per [ADR-0016](../../../decisions/0016-workflow-event-log-jsonl.md) consume the same trailer for structured analysis of pipeline outcomes.

Putting the trailer LAST (after the prose body, after any extensions) is deliberate. A human reader gets the conversational verdict first; an automated parser tails the output for the trailer. Both audiences served, no duplicated truth, no field-of-truth ambiguity.

## Examples from this project

- **`reviewer` on every PR** — every reviewer verdict comment ends with a fenced trailer; `/ship`'s reviewer-dispatch loop parses it to decide auto-merge vs. forward-block-to-implementer per [ADR-0010](../../../decisions/0010-implementer-subagent-auto-pipeline.md) D8.
- **`prd-critic` on PRD drafts** — APPROVE trailer triggers `/to-prd` to post the PRD; BLOCK trailer surfaces the round count and `FAILED_RULES` to the next regeneration.
- **`slicer-critic` on slicer outputs** — APPROVE trailer accompanies the "Final approved decomposition" extension that `/ship` consumes to create the GitHub Issues for each slice.

## Anti-patterns

- **Multi-line `REASON:` values** — breaks line-oriented parsing; if more rationale is needed, put it in the Summary section above the trailer.
- **Trailer in the middle of the output** — parsers tail the output for the fenced block; misplacement causes verdict ambiguity.
- **Critic-specific trailer in a separate fenced block** — extensions go INSIDE the canonical block as additional `KEY: value` lines, not as a second block.

## Scope

(a) project jargon coined here

## Authority

[ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D1

## References

- [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D1 — canonical CRITIC trailer field schema.
- [ADR-0010](../../../decisions/0010-implementer-subagent-auto-pipeline.md) D8 — reviewer dispatch consumes the trailer for auto-merge decisions.
- [ADR-0016](../../../decisions/0016-workflow-event-log-jsonl.md) — JSONL workflow event log records trailer dispositions.
- [CLAUDE.md](../../../CLAUDE.md) "Output-shape standard for subagents" — cross-agent reference.
- [[concepts/glossary/generator-trailer]] — the sibling trailer for output-emitting generators.
