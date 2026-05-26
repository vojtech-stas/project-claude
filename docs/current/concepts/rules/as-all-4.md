---
title: AS-ALL-4 — audit-subagents check, surfacing-convention prose uses captured-label not backlog-label
summary: The audit-subagents drift detector (the #93 fix) that flags any subagent body using the backlog-label idiom (`backlog`-labeled prose or `--label backlog` literal) instead of the captured-tier surfacing convention; non-empty match FAILS the check; backlog-critic.md is allowlisted because its domain IS the backlog tier.
tags: [rule, audit-subagents-rubric]
type: concept
last_updated: 2026-05-27
sources:
  - .claude/skills/audit-subagents/SKILL.md ALL-4
  - decisions/0011-subagent-quality-framework.md D4
  - decisions/0008-workflow-autolog-bootstrap-and-naming.md D8
  - decisions/0009-discipline-tightening.md D2
---

# AS-ALL-4

**AS-ALL-4** is the [`/audit-subagents`](../../entities/skills/audit-subagents.md) rubric check (scope: `all`) that detects the **#93 surfacing-convention drift**: subagent bodies that still tell agents to surface deferred work via `--label backlog` or describe issues as ``\`backlog\`-labeled`` in prose, when the post-[ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D8 / [ADR-0009](../../../decisions/0009-discipline-tightening.md) D2 convention is to capture into the `captured` tier and let [`backlog-critic`](../../entities/subagents/backlog-critic.md) promote to `backlog`.

## What

The check fires on every `.claude/agents/*.md` file. Mechanics:

- Run the drift-detection grep: ``grep -cE "(\\\`backlog\\\`-labeled|--label backlog)" <file>``.
- If the count is 0 → **PASS** (no drift idiom present).
- If the count is ≥ 1 → **FAIL** (drift detected).

The `excludes:` field on this check allowlists `backlog-critic.md` (whose domain IS the backlog tier per [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D2, so it legitimately mentions the backlog label without being the drift idiom this check detects). Excluded pair renders as `N/A (excluded per rubric)`.

**Default-conservative rendering** per the skill prompt: if a match appears anywhere in the file — including inside example / quoted blocks — FAIL. The cost of a spurious FAIL is one user-glance round; the cost of a missed real drift is the #93 failure mode itself (deferred work surfaced directly into the curated `backlog` queue, bypassing `backlog-critic`'s quality gate).

## Why

The captured-vs-backlog two-tier surfacing convention exists because **agents are noisy**: capturing every observation directly into `backlog` would force `backlog-critic` to BLOCK duplicates and noise on every promotion. The `captured` tier is the raw firehose; `backlog-critic` filters one into the other. Subagents whose prose still says "capture as `backlog`-labeled" instruct agents to skip the gate — the exact regression #93 catches.

The mechanical grep cannot distinguish "this file's subject IS the backlog label" from "this file is using the backlog label as the surfacing idiom (the drift)", so the `backlog-critic.md` allowlist is required. Without it, the only critic whose JOB it is to enforce the convention would itself FAIL the check that codifies the convention.

## How to check

For each `.claude/agents/*.md` file (excluding `backlog-critic.md`):

1. Run ``grep -cE "(\\\`backlog\\\`-labeled|--label backlog)" <file>``.
2. If count = 0 → PASS.
3. If count ≥ 1 → FAIL; the report should flag the file and the matching line(s).
4. For `backlog-critic.md` specifically → render `N/A (excluded per rubric)`; do NOT include in FAIL enumeration.

## Examples

- **`reviewer.md` with no backlog-label idiom** → PASS.
- **`slicer.md` saying "capture deferred work as `captured`-labeled issues"** → PASS (uses correct surfacing convention).
- **An older subagent file with `gh issue create --label backlog`** → FAIL (drift detected).
- **A subagent file with ``\`backlog\`-labeled`` in a quoted example** → FAIL (default-conservative).
- **`backlog-critic.md` legitimately mentioning `` `backlog`-labeled `` in domain prose** → `N/A (excluded per rubric)`.

## Edges

- **part_of:** [[entities/skills/audit-subagents]]
- **related_to:** [[concepts/rules/am-docs-backlog-surfacing]]
- **related_to:** [[entities/subagents/backlog-critic]]
