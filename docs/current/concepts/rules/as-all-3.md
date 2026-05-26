---
title: AS-ALL-3 — audit-subagents check, every subagent has a cross-reference section heading
summary: The audit-subagents mechanical check that every subagent body has at least one cross-reference section heading (References / Related / See also / Cross-refs, case-insensitive); zero such headings FAILS the check.
tags: [rule, audit-subagents-rubric]
type: concept
last_updated: 2026-05-27
sources:
  - .claude/skills/audit-subagents/SKILL.md ALL-3
  - decisions/0011-subagent-quality-framework.md D4
---

# AS-ALL-3

**AS-ALL-3** is the [`/audit-subagents`](../../entities/skills/audit-subagents.md) rubric check (scope: `all`) that enforces every subagent body carries at least one cross-reference section heading — `References`, `Related`, `See also`, or `Cross-refs` (case-insensitive). Per [ADR-0011](../../../decisions/0011-subagent-quality-framework.md) D4, this is the project's "no orphan subagents" rule: every subagent must explicitly link back to the ADRs, sibling agents, or skills that ground its design.

The pattern was **broadened from the original literal `^#+\s*References`** after PR #96 dogfood showed 7 of 8 subagents FAILing because the convention is "any heading-shaped cross-link section", not the exact word "References". The current pattern accepts all four enumerated variants.

## What

The check fires on every `.claude/agents/*.md` file. Mechanics:

- Run the literal grep: `grep -ciE "^#+\s*.*(References|Related|See also|Cross-refs)" <file>`.
- If the count is ≥ 1 → **PASS** (at least one matching heading exists).
- If the count is 0 → **FAIL** (no cross-reference section).

The pattern is case-insensitive (`-i` flag) and matches anchored markdown headings (`^#+`) followed by optional content then any of the four enumerated variant words.

## Why

A subagent without a cross-reference section is a maintenance liability: future readers cannot trace the design constraints back to their ADRs, cannot find sibling agents whose rubrics or output shapes the subagent must align with, and cannot verify the subagent is consistent with the broader pipeline conventions.

The breadth of the pattern (4 variants, case-insensitive) is intentional — the rule cares about the *presence* of a back-link section, not the exact heading text. Earlier strictness produced false-positive FAILs that buried real findings under noise.

## How to check

For each `.claude/agents/*.md` file:

1. Run `grep -ciE "^#+\s*.*(References|Related|See also|Cross-refs)" <file>`.
2. If ≥ 1 → PASS.
3. If 0 → FAIL; the report should flag the file as having no cross-reference section.

## Examples

- **`reviewer.md` ending with `## References`** → PASS.
- **`slicer.md` with `## Related ADRs`** → PASS (matches "Related").
- **`prd-critic.md` with `### See also` H3** → PASS (case-insensitive).
- **A subagent file with all cross-references inline in prose but no heading-anchored section** → FAIL.

## Edges

- **part_of:** [[entities/skills/audit-subagents]]
- **related_to:** [[concepts/rules/as-all-2]]
- **related_to:** [[concepts/rules/as-all-5]]
