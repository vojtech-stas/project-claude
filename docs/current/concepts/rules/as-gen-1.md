---
title: AS-GEN-1 — audit-subagents generator check, GENERATOR trailer spec present (RESULT/REASON/ARTIFACTS)
summary: The audit-subagents generator-only mechanical check that every generator body contains the three canonical GENERATOR trailer fields (RESULT:, REASON:, ARTIFACTS:) per ADR-0005 D1c; missing any of the three FAILS the check.
tags: [rule, audit-subagents-rubric]
type: concept
last_updated: 2026-05-27
sources:
  - .claude/skills/audit-subagents/SKILL.md GEN-1
  - decisions/0011-subagent-quality-framework.md D4
  - decisions/0005-output-shape-and-slicing-methodology.md D1c
---

# AS-GEN-1

**AS-GEN-1** is the [`/audit-subagents`](../../entities/skills/audit-subagents.md) rubric check (scope: `generator` — applies only to files classified as generator per [ADR-0011](../../../decisions/0011-subagent-quality-framework.md) D3) that enforces every generator body documents the canonical [GENERATOR trailer](../glossary/generator-trailer.md) field schema — the three required fields `RESULT:`, `REASON:`, and `ARTIFACTS:` — per [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D1c. A generator file missing any one of the three FAILS the check.

## What

The check fires on every generator file (currently `slicer.md` + `implementer.md`; `qa-tester.md` once classified). Mechanics:

- Run three fixed-string greps and require ALL three to match:
  - `grep -cF "RESULT:" <file>` ≥ 1 AND
  - `grep -cF "REASON:" <file>` ≥ 1 AND
  - `grep -cF "ARTIFACTS:" <file>` ≥ 1.
- If all three counts are ≥ 1 → **PASS**.
- If any one count is 0 → **FAIL** (trailer spec incomplete).

The check verifies the trailer is *documented in the generator body*, not that the trailer is actually emitted at runtime — the latter is the generator's responsibility per its own contract.

## Why

The GENERATOR trailer is the project's machine-parsable output-shape contract for non-critic agents: downstream consumers parse `RESULT: SUCCESS | STOPPED | INVALID_INPUT` to determine whether to chain, retry, or escalate. A generator that does not document the trailer in its body will either omit it at runtime (silent break) or invent a non-canonical shape (parser break).

The three required fields are the **minimum viable contract** per [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D1c. Generators MAY (and typically DO) add per-agent extension fields — e.g., `PR_URL`, `BRANCH_NAME`, `SLICE_ISSUE` for implementer; `SLICE_COUNT` for slicer; `SUBAGENTS_AUDITED` for audit-subagents itself — but the three core fields are non-negotiable.

## How to check

For each generator file:

1. Run `grep -cF "RESULT:" <file>`.
2. Run `grep -cF "REASON:" <file>`.
3. Run `grep -cF "ARTIFACTS:" <file>`.
4. If all three counts are ≥ 1 → PASS.
5. If any count = 0 → FAIL; the report should flag the file and the missing field(s).
6. For critics → render `—` (the CRITIC trailer has its own check, AS-CRIT-3).

## Examples

- **`slicer.md` with a fenced GENERATOR trailer block documenting all three fields plus `SLICE_COUNT`** → PASS.
- **`implementer.md` with the trailer documented in its "Output format" section** → PASS.
- **A generator file with `RESULT:` and `REASON:` but no `ARTIFACTS:`** → FAIL.
- **`reviewer.md` (critic)** → `—` (scope-not-applicable; reviewer emits the CRITIC trailer instead).

## Edges

- **part_of:** [[entities/skills/audit-subagents]]
- **related_to:** [[concepts/rules/as-crit-3]]
- **related_to:** [[concepts/glossary/generator-trailer]]
