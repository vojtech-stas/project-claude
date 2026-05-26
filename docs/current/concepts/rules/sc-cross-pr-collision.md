---
title: SC-CROSS-PR-COLLISION — slicer-critic criterion 10, cross-PR cascade-doc collision check
summary: The slicer-critic rule that when a slice's cascade-doc edits intersect with files touched by currently-open PRs, emit WARN naming the in-flight PRs and recommend sequencing OR a deferred-trivial-lane back-ref pattern.
tags: [rule, slicer-critic-rubric]
type: concept
last_updated: 2026-05-26
sources:
  - .claude/agents/slicer-critic.md criterion 10
  - backlog #194
  - PRD #210
---

# SC-CROSS-PR-COLLISION

**SC-CROSS-PR-COLLISION** is criterion 10 in the [`slicer-critic`](../../../.claude/agents/slicer-critic.md) rubric. When a slice's announced cascade-doc edits (per criterion 9 / [SC-CASCADE-DOCS-COVERED](sc-cascade-docs-covered.md)) intersect with files touched by currently-open PRs, the critic emits a **WARN** naming the in-flight PR(s) and recommends either sequencing OR the deferred-trivial-lane back-ref pattern (ship the skill/subagent body now; ship cross-skill back-refs in a separate I3 trivial-lane PR after sibling PRs merge).

## What

Mechanics:

- Read slice's "Cascade-docs identified" row → parse out discrete file paths.
- Run `gh pr list --state open --json number,title,files | jq -r '.[] | {n: .number, t: .title, f: [.files[].path]}'`.
- Intersect the slice's cascade-doc file set with each open PR's file set.
- For each non-empty intersection → WARN with the offending file(s) + the in-flight PR number(s).
- If the slicer's emission is loose prose (not discrete paths), fall back to manual comparison: read the slicer's listed cascade-docs verbatim and compare against `gh pr list --state open --json files`.

WARN severity (not FAIL) is intentional: collisions are sometimes acceptable (the in-flight PR will obviously merge first; sequencing is operational). The WARN surfaces the conflict for human/agent judgment; it does not hard-block.

**PASS** if no intersection, OR if the decomposition explicitly notes "no open PR touches the cascade-doc files (verified via `gh pr list`)".

## Why

This rule exists because **parallel sibling PRs that both touch the same cascade-doc rebase-conflict on merge**. The pattern was surfaced from the PR #183 + PR #186 collision: both PRs added CLAUDE.md Map rows for new skills; whichever merged second hit a hand-resolvable conflict. Multiplied across the autonomous-pipeline's parallel-dispatch model (per [ADR-0010](../../../decisions/0010-implementer-subagent-auto-pipeline.md) D3), the cost compounds — every parallel batch with cascade-doc collisions becomes a rebase round-trip.

The deferred-trivial-lane back-ref pattern is the canonical mitigation: ship the new skill/subagent body in the current slice (no back-refs); then after all sibling PRs merge, open a single I3 trivial-lane PR adding all the cross-skill back-refs. Sequencing one trivial PR is cheaper than rebasing N feature PRs.

WARN-not-FAIL acknowledges that some collisions are benign (the colliding PR merges first; the slice can rebase trivially). The rule's job is to surface, not to gate.

## How to check

For each candidate decomposition:

1. Extract slice's cascade-doc file paths (or names if prose).
2. Run `gh pr list --state open --json number,title,files`.
3. Intersect; build a per-slice collision list.
4. For each collision: WARN with PR # + file + recommended mitigation (sequence vs deferred-trivial-lane).

The mechanical fallback (loose prose case) is acceptable but degraded: slicer-critic does best-effort comparison and notes the input shape limitation.

## Examples

- **Slice cascades `CLAUDE.md` Map row; open PR #186 also touches `CLAUDE.md`** → WARN: "Sequence after PR #186 merges, OR defer Map-row addition to a trivial-lane back-ref PR".
- **Slice cascades `docs/current/topics/pipeline-stages.md`; no open PR touches that file** → PASS.
- **Decomposition explicitly notes "verified `gh pr list` — no open PR touches the cascade-doc files"** → PASS.

## Edges

- **part_of:** [[entities/subagents/slicer-critic]]
- **related_to:** [[concepts/rules/sc-cascade-docs-covered]]
- **related_to:** [[patterns/cascade-doc-check]]
- **related_to:** [[concepts/glossary/trivial-lane]]
