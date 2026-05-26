---
title: GENERATOR trailer — canonical machine-readable generator-output footer
summary: The canonical fenced field-schema block (RESULT, REASON, ARTIFACTS, plus per-agent extensions) appended at the end of every output-emitting generator's output.
tags: [glossary, output-shape, project-jargon, generator]
type: concept
last_updated: 2026-05-26
sources:
  - decisions/0005-output-shape-and-slicing-methodology.md
  - CLAUDE.md
---

# GENERATOR trailer

The **GENERATOR trailer** is the canonical fenced field-schema block appended at the end of every output-emitting generator's output. It is the sibling of the CRITIC trailer: critics emit verdicts (APPROVE/BLOCK), generators emit artifacts (URLs, file paths, decompositions, test plans). Per [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D1c, generator body shapes remain domain-specific (decompositions for `slicer`, test plans for `qa-plan`, PR descriptions for `implementer`); only the trailer is canonical across generators.

**Edges**

- **related-to:** [[concepts/glossary/critic-trailer]]
- **part-of:** [[topics/output-shapes]]

## What

The trailer is a fenced code block (no language tag) containing line-oriented `KEY: value` pairs. Required fields:

- `RESULT:` one of `SUCCESS`, `STOPPED`, `INVALID_INPUT`, `BLOCKED` (the implementer subagent uses `BLOCKED` for auto-retry-exhaustion per [ADR-0010](../../../decisions/0010-implementer-subagent-auto-pipeline.md) D7).
- `REASON:` one sentence summarizing the disposition.
- `ARTIFACTS:` URLs or filesystem paths, comma-separated; empty for non-SUCCESS results.

Per-agent extensions follow per-generator conventions named in the generator's own body file. Documented extensions include:

- **`implementer`**: `PR_URL`, `BRANCH_NAME`, `SLICE_ISSUE` per [ADR-0010](../../../decisions/0010-implementer-subagent-auto-pipeline.md) D7.
- **`slicer`**: `SLICE_COUNT`, `COVERAGE_GAPS`.
- **`qa-plan`**: `PRD_DISPOSITION` per [ADR-0020](../../../decisions/0020-qa-automation-writer-executor.md) D9.
- **`qa-tester`**: `PASS_COUNT`, `FAIL_COUNT`, `JUDGMENT_COUNT`, `EXTRACT_FAILED_COUNT` per [ADR-0020](../../../decisions/0020-qa-automation-writer-executor.md) D9.

The list is not closed — new generators name their own extensions in their body and the trailer accommodates them; the only invariant is the three required fields and the fenced-block placement at the end.

## Why

The trailer exists because **cross-agent orchestration needs structured handoffs**. The `/ship` skill dispatches `implementer` and then waits for the SUCCESS/BLOCKED disposition + the PR URL to hand off to `reviewer`; without the trailer, that handoff would require LLM re-reading of the implementer's prose report. The trailer makes the handoff a parse-and-grep operation.

The split between CRITIC and GENERATOR trailers — rather than one unified shape — is intentional. Critics decide things (APPROVE/BLOCK with a possible escalation); generators produce things (SUCCESS with artifacts, or failure modes that branch differently). Keeping the field schemas distinct prevents the conflation of "judge" and "build" — the two roles have different downstream consumers and benefit from different parse contracts.

## Examples from this project

- **`implementer` on a slice** — emits SUCCESS with PR_URL + BRANCH_NAME + SLICE_ISSUE; `/ship` parses PR_URL to dispatch `reviewer` against that PR.
- **`slicer` on a PRD** — emits SUCCESS with the decomposition stored under ARTIFACTS; `slicer-critic` parses it to apply the rubric.
- **`qa-tester` on a PRD acceptance plan** — emits SUCCESS with per-criterion counts; the `qa-plan` writer half consumes the counts to decide PRD disposition (close / reopen / cull) per [ADR-0020](../../../decisions/0020-qa-automation-writer-executor.md) D5.

## Anti-patterns

- **Generator with no trailer** — orchestrator can't determine result without LLM re-read; misclassifies success/failure under load.
- **Mixing GENERATOR and CRITIC trailer fields in one block** — verdicts and artifacts are different shapes; readers parse against the wrong schema.
- **Trailer fields outside the fenced block** — parsers tail for the fence; bare KEY: value lines in prose are not the trailer.

## Scope

(a) project jargon coined here

## Authority

[ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D1

## References

- [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D1 / D1c — canonical GENERATOR trailer field schema and per-agent extension policy.
- [ADR-0010](../../../decisions/0010-implementer-subagent-auto-pipeline.md) D7 — `implementer` failure return modes encoded in the trailer.
- [ADR-0020](../../../decisions/0020-qa-automation-writer-executor.md) D9 — qa-tester / qa-plan per-agent extensions.
- [CLAUDE.md](../../../CLAUDE.md) "Output-shape standard for subagents" — cross-agent reference.
- [[concepts/glossary/critic-trailer]] — the sibling trailer for adversarial critics.
