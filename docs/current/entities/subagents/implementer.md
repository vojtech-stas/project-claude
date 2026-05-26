---
title: implementer — slice-to-PR generator subagent
summary: Generator at pipeline stage 4a; consumes a single `slice`-labeled GitHub issue, reads the slice + parent PRD + relevant ADRs, claims the slice (I2), branches per CLAUDE.md naming, implements within scope, commits per Conventional Commits, and opens a PR with `Closes #<slice>`; hands off to reviewer for auto-merge.
tags: [subagent, generator, pipeline, implementer]
type: entity
last_updated: 2026-05-26
sources:
  - .claude/agents/implementer.md
  - decisions/0010-implementer-subagent-auto-pipeline.md
  - decisions/0003-autonomous-pipeline-with-critics.md
  - decisions/0005-output-shape-and-slicing-methodology.md
  - decisions/0002-autonomous-merge-policy.md
---

# implementer

The `implementer` subagent is the **slice-to-PR generator** at stage 4a of the autonomous pipeline. Given one `slice`-labeled GitHub issue, it produces one PR that `Closes #<slice>` and hands off to [`reviewer`](reviewer.md) for auto-merge per [ADR-0002](../../../decisions/0002-autonomous-merge-policy.md). It is a **process-not-rubric** subagent (per PRD #283 §5 OQ-1) — its discipline lives in the synthesis of git workflow + Conventional Commits + slice-grabbing protocol + scope-paranoid adversarial mindset, not in a numbered rubric like the 6 critics.

This entity note is the **canonical full role synthesis** for the implementer subagent. After the T4 knowledge-architecture migration ([ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D10 step 4 of 9, PRD #283 slice 8), the operational [`.claude/agents/implementer.md`](../../../.claude/agents/implementer.md) carries only the prompt-level operational mechanics (mandatory reading order, tool boundaries, conduct) and links here for the full process synthesis, the adversarial-mindset rationale, the failure return modes, and the relationship to reviewer.

## Role and responsibility

The implementer has three jobs, in strict priority order:

1. **Stay strictly within slice scope.** Apply the adversarial mindset before each Write/Edit; refuse any "while I'm here" addition. YAGNI per CLAUDE.md rule #1 is the primary failure mode it guards against, and pre-empting reviewer findings is the cheapest path to APPROVE.
2. **Produce one PR per slice.** Create the branch (`<type>/<N>-<kebab-summary>` per CLAUDE.md "Starting a slice"), claim the slice via `gh issue edit --add-assignee @me` (I2 — first to claim owns it), commit per [Conventional Commits](../../concepts/glossary/conventional-commits.md) (lowercase subject, ≤72 char cap, `Co-Authored-By:` trailer), and open a PR with the required body sections (`Closes #<N>`, `## Scope`, `## Out-of-scope`, `## Verification`, optional `## ADR reference`).
3. **Return the canonical [GENERATOR trailer](../../concepts/glossary/generator-trailer.md)** with `PR_URL` + `BRANCH_NAME` + `SLICE_ISSUE` per-agent extensions (see [[topics/output-shapes]] for the canonical schema and [ADR-0010](../../../decisions/0010-implementer-subagent-auto-pipeline.md) D7 for the per-agent extension naming).

It does NOT spawn other subagents (no `Agent` tool per [ADR-0010](../../../decisions/0010-implementer-subagent-auto-pipeline.md) D6), does NOT invoke `reviewer` itself (the `/ship` orchestrator does that at stage 4b per [ADR-0010](../../../decisions/0010-implementer-subagent-auto-pipeline.md) D8), does NOT create issues outside its own branch (no `gh issue create` for captures or backlog — that is the orchestrator's or other skills' job), and does NOT edit existing ADRs (immutability per `decisions/README.md`; MAY create new ADR files inside its slice's PR per [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D8 if the slice body authorizes it).

## Invocation contract

- **Caller:** the [`/ship`](../../../.claude/skills/ship/SKILL.md) orchestrator at stage 4a (per [ADR-0010](../../../decisions/0010-implementer-subagent-auto-pipeline.md) D2 + D3 DAG-aware parallel batching), or a human via the `Agent` tool with `subagent_type: "implementer"` passing the slice issue number.
- **Input:** a `slice`-labeled GitHub issue number (e.g., `81`). The implementer fetches via `gh issue view <N> --json number,title,body,labels,assignees,state` and verifies: `labels` includes `slice`, `state` is `OPEN`, body has the slice-template sections (Parent / What ships / Acceptance criteria / Branch + commit conventions). Verification failure → `RESULT: INVALID_INPUT` and stop without creating a branch.
- **Output:** the canonical [GENERATOR trailer](../../concepts/glossary/generator-trailer.md) per [[topics/output-shapes]] with three per-agent extensions: `PR_URL` (the opened PR's URL), `BRANCH_NAME` (the branch created), `SLICE_ISSUE` (the slice number, for orchestrator correlation per [ADR-0010](../../../decisions/0010-implementer-subagent-auto-pipeline.md) D7). Body shape is domain-specific (a brief plain-text report of what was done) and not canonical.
- **Tool boundaries** per [ADR-0010](../../../decisions/0010-implementer-subagent-auto-pipeline.md) D6: `Read`, `Edit`, `Write`, `Bash`, `Glob`, `Grep`. **NOT** authorized: `Agent` (no recursive subagent invocation — prevents confused authority and runaway spawning), `gh issue create` for anything other than the PR, `gh issue close` outside the slice (which auto-closes via `Closes #<N>` on merge), edits to existing ADR files, edits to any file untracked in the working tree and not named in the slice's "What ships".

## Adversarial mindset — the paranoid implementer

The implementer's discipline is **process, not rubric** (per PRD #283 §5 OQ-1) — its rigor lives in self-audit questions applied before each Write/Edit, not in a numbered critic-style checklist. Pre-empting reviewer findings is the cheapest path to APPROVE; the reviewer will block on any of the below, so the implementer's adversarial mindset mirrors the reviewer's rubric in self-audit form.

Before each Write/Edit, the implementer asks:

- **Scope drift:** does this change a file outside the slice's stated `What ships`? If yes, STOP and re-justify against the slice body, or BLOCK. The [`/audit-subagents`](../../../.claude/skills/audit-subagents/SKILL.md) rubric does NOT apply to the implementer (per [ADR-0011](../../../decisions/0011-subagent-quality-framework.md) D8 non-recursion), but the same scope-drift suspicion drives self-discipline.
- **YAGNI** (per [yagni](../../concepts/glossary/yagni.md)): am I adding a helper / abstraction / config knob that the slice's acceptance criteria don't require? If yes, delete it.
- **Missing tests:** does new behavior (not docs/config/refactor) have a corresponding test in this PR? If no, write one before pushing. The reviewer's [R-TESTS](../../concepts/rules/r-tests.md) blocks new behavior without tests.
- **Commit format:** is the subject lowercase, ≤72 chars, Conventional-Commits-shaped? If not, fix before pushing. The reviewer's [R-CONV-COMMITS](../../concepts/rules/r-conv-commits.md) blocks on format violations.
- **R-LOC pressure:** am I tracking under the [R-LOC](../../concepts/rules/r-loc.md) 300-LoC runtime-artifact cap? If approaching, invoke the slice's SPIDR-Interface fallback hint (see [spidr](../../concepts/glossary/spidr.md)) or BLOCK.

**Default conservative** per [ADR-0009](../../../decisions/0009-discipline-tightening.md) D3 / D4: when uncertain about ANY of (acceptance-criterion interpretation, scope boundary, branch-name choice, commit-format compliance, whether an edit belongs in this slice) → return `RESULT: BLOCKED` with a one-sentence `REASON:` rather than guess. A spurious BLOCK costs one human-prompt round; a wrong-guess edit costs a reviewer round-trip plus rework. Conservative is the asymmetric correct default.

## Failure return modes (per [ADR-0010](../../../decisions/0010-implementer-subagent-auto-pipeline.md) D7)

- **`RESULT: SUCCESS`** — PR opened, `Closes #<N>` present, branch pushed. Trailer includes `PR_URL` + `BRANCH_NAME` + `SLICE_ISSUE`. Reviewer takes over per the existing [ADR-0002](../../../decisions/0002-autonomous-merge-policy.md) flow.
- **`RESULT: BLOCKED`** + one-sentence `REASON:` — genuine failure auto-retry couldn't absorb: merge conflict unresolvable, ambiguous acceptance criterion, scope explosion past the slice's SPIDR fallback, repeated tool errors. The implementer posts a comment on the slice describing the block; the orchestrator applies the `needs-human` label per [ADR-0010](../../../decisions/0010-implementer-subagent-auto-pipeline.md) D4. Does NOT open a PR.
- **`RESULT: INVALID_INPUT`** + one-sentence `REASON:` — slice issue is malformed (missing AC, missing parent-PRD ref, wrong label/state). The implementer does NOT attempt the work; surfaces for slicer/human correction.

**Auto-retry before BLOCKED:** transient failures get retried up to 3 times with brief backoff — `Edit`/`Write` tool errors (retry once after re-reading the file), `gh` API errors (5s/15s/30s backoff for HTTP 5xx and rate-limit), `git push` non-fast-forward rejections (`git fetch origin main && git rebase origin/main` once, then retry). Test failures from tests the implementer wrote → iterate locally (fix, re-run, ≤5 iterations) before pushing; do NOT push known-failing tests.

## Bootstrap-mode acknowledgment

This subagent ships per [ADR-0010](../../../decisions/0010-implementer-subagent-auto-pipeline.md) D9 bootstrap-mode: its enforcement of CLAUDE.md rules (current shape — universal/mandatory if [ADR-0009](../../../decisions/0009-discipline-tightening.md) has merged, otherwise the pre-tightening shape) binds **forward** from invocation time. It uses whichever `CLAUDE.md` was loaded at session start; it does NOT re-read mid-pipeline to pick up a freshly-merged update. This matches the in-flight `/ship`-invocation non-reload pattern of [ADR-0010](../../../decisions/0010-implementer-subagent-auto-pipeline.md) D9.

## Relationship to other agents

- **Adversarial critic to** the [`reviewer`](reviewer.md) subagent — but in the inverse direction of every other generator/critic pair. The implementer generates the PR; the reviewer judges it. The implementer's adversarial mindset is *anticipatory*: it self-audits using the reviewer's rubric to pre-empt findings before the reviewer fires. Reviewer is the implementer's downstream gate per [ADR-0010](../../../decisions/0010-implementer-subagent-auto-pipeline.md) D8.
- **Downstream consumer of** the slice issues posted by the slicer-critic-approved decomposition per [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D3 + [ADR-0013](../../../decisions/0013-slicer-n3-contract-refined.md). The implementer treats the slice body as immutable spec (the "Acceptance criteria" checkboxes drive self-verification mechanically).
- **Upstream producer for** the [`reviewer`](reviewer.md) subagent (next stage 4b). Reviewer auto-merges on APPROVE per [ADR-0002](../../../decisions/0002-autonomous-merge-policy.md), returns to implementer for revision on BLOCK (≤3 rounds before `needs-human` per I5 + [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D4).
- **Honors the 6-critic-cap** per [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7 — implementer is a generator, not a critic; its adversarial gate is `reviewer`.
- **Authority:** [ADR-0010](../../../decisions/0010-implementer-subagent-auto-pipeline.md) D1 (one implementer for all slice types), D2 (`/ship` auto-invokes), D3 (DAG-aware parallel batching), D4 (forward-block failure handling), D5 (sequential walking-skeleton baseline), D6 (tool boundaries), D7 (failure return modes), D8 (reviewer is the critic), D9 (bootstrap-mode); [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D2 (5-stage pipeline; implementer fills stage 4) + D4 (no human gates between stages — implementer's existence closes the residual gap) + D8 (ADR placement at slice 1); [ADR-0002](../../../decisions/0002-autonomous-merge-policy.md) (reviewer auto-merge on APPROVE); [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D1c (GENERATOR trailer shape).

## Edges

- **related_to:** [[entities/subagents/reviewer]]
- **related_to:** [[entities/subagents/slicer]]
- **related_to:** [[entities/subagents/slicer-critic]]
- **part_of:** [[topics/pipeline-stages]]
- **related_to:** [[topics/output-shapes]]
- **related_to:** [[concepts/glossary/slice]]
- **related_to:** [[concepts/glossary/prd]]
- **related_to:** [[concepts/glossary/conventional-commits]]
- **related_to:** [[concepts/glossary/generator-trailer]]
- **related_to:** [[concepts/glossary/yagni]]
- **related_to:** [[concepts/glossary/spidr]]
- **related_to:** [[concepts/rules/r-loc]]
- **related_to:** [[concepts/rules/r-closes]]
- **related_to:** [[concepts/rules/r-conv-commits]]
- **related_to:** [[concepts/rules/r-tests]]
