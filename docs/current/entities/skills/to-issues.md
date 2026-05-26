---
title: to-issues — thin wrapper around slicer + slicer-critic that posts slice GitHub Issues
summary: Stage-3 wrapper that delegates decomposition to the slicer subagent (N=3 alternatives per ADR-0003 D3) and selection-plus-revision to slicer-critic, then publishes one GitHub Issue per slice (label slice) in dependency order with the canonical slice-template body.
tags: [skill, pipeline, generator, to-issues]
type: entity
last_updated: 2026-05-27
sources:
  - .claude/skills/to-issues/SKILL.md
  - decisions/0003-autonomous-pipeline-with-critics.md
  - decisions/0013-slicer-n3-contract-refined.md
---

# /to-issues

The `/to-issues` skill is the **slice-issue posting stage** of the autonomous pipeline. It is a thin wrapper around the `slicer` and `slicer-critic` subagents (per [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D2 + D6 + [ADR-0013](../../../decisions/0013-slicer-n3-contract-refined.md)): given a PRD, the subagent pair generates N=3 alternative decompositions, picks the best one with a single revision loop, and this skill walks the dependency graph topologically and posts one `slice`-labeled GitHub Issue per slice. The `/to-issues` invocation shape is preserved for backward-compatibility — both direct human use and `/ship` orchestration work the same way.

## Role and responsibility

`/to-issues` has three jobs:

1. **Identify the target PRD.** Take the explicit `#N` / URL argument, or scan conversation context for a recently-posted `prd`-labeled issue. If ambiguous → STOP and ask which PRD to slice (do NOT invent one).
2. **Delegate decomposition + selection** to the `slicer` and `slicer-critic` subagents in sequence. On `slicer-critic` BLOCK, surface reasons and STOP — do NOT post issues.
3. **Publish on APPROVE.** Walk the approved decomposition's `Depends on` graph topologically (blockers first); `gh issue create --label slice --body-file <tempfile>` per slice. Each posted issue body includes `Parent: #<PRD>` so GitHub renders the back-link.

## Invocation contract

- **Caller:** the [`/ship`](ship.md) orchestrator at stage 3 (autonomous, skips interactive confirmation), OR a human via `/to-issues #<PRD>` (interactive — asks "Post these slices to GitHub?" before any `gh issue create`).
- **Input:** a PRD GitHub issue reference (`#N`, URL, or path), OR conversation context referencing a recently-posted PRD.
- **Output:** a list of posted slice issue URLs in dependency order; returned to the orchestrator for the implementer-reviewer dispatch loop downstream.
- **Tool boundaries:** `Bash` (`gh issue create`), `Read`, `Agent` (slicer + slicer-critic dispatch), `AskUserQuestion` (interactive-mode confirmation only).

## The canonical slice-template body

Each posted slice issue body follows the template in this skill (see [`.claude/skills/to-issues/SKILL.md`](../../../.claude/skills/to-issues/SKILL.md) for the verbatim shape):

- **Parent** — `PRD #<N> — <PRD title>`
- **What ships** — 1–3 sentence end-to-end description
- **Acceptance criteria** — checkboxes derived from slicer output; LoC cap mentioned per PRD §4
- **Walking-skeleton role** — only if the slice is tagged `walking-skeleton: yes`
- **Depends on** — `#<blocker>` lines, or "None — can start immediately"
- **LoC estimate** — `~<int> runtime LoC`
- **Branch + commit conventions** — branch name + commit prefix + `Closes #<this>` reminder

## Relationship to other skills and agents

- **Called by** [`/ship`](ship.md) at stage 3 (autonomous), or by the user directly (interactive).
- **Invokes** [`slicer`](../subagents/slicer.md) (decomposition generator), then [`slicer-critic`](../subagents/slicer-critic.md) (best-of-N + single revision).
- **Upstream consumer of** the PRD posted by [`/to-prd`](to-prd.md).
- **Downstream producer for** the [`implementer`](../subagents/implementer.md) subagent (one PR per posted slice).
- **Honors the 6-critic-cap** per [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7 — `/to-issues` is a skill; its gate is `slicer-critic`.
- **Authority:** [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D2 (5-stage pipeline), D3 (N=3 at slicer + single revision loop), D6 (skills vs subagents); [ADR-0013](../../../decisions/0013-slicer-n3-contract-refined.md) (N=1 degenerate carveout).

## Edges

- **part_of:** [[topics/pipeline-stages]]
- **related_to:** [[entities/skills/ship]]
- **related_to:** [[entities/skills/to-prd]]
- **related_to:** [[entities/subagents/slicer]]
- **related_to:** [[entities/subagents/slicer-critic]]
- **related_to:** [[entities/subagents/implementer]]
- **related_to:** [[concepts/glossary/prd]]
- **related_to:** [[concepts/glossary/slice]]
- **related_to:** [[concepts/glossary/invest]]
