---
title: AS-ALL-5 — audit-subagents check, every subagent has "Mandatory reading order" OR "When invoked" section
summary: The audit-subagents mechanical check that every subagent body contains either a "Mandatory reading order" or "When invoked" section heading — the entry-protocol convention shared across all 8 current subagents.
tags: [rule, audit-subagents-rubric]
type: concept
last_updated: 2026-05-27
sources:
  - .claude/skills/audit-subagents/SKILL.md ALL-5
  - decisions/0011-subagent-quality-framework.md D4
---

# AS-ALL-5

**AS-ALL-5** is the [`/audit-subagents`](../../entities/skills/audit-subagents.md) rubric check (scope: `all`) that enforces every subagent body contains either a "Mandatory reading order" or "When invoked" section heading. Per [ADR-0011](../../../decisions/0011-subagent-quality-framework.md) D4, this codifies the **entry-protocol convention** shared across all 8 current subagents — the section that tells the subagent (and a future human auditor) what to read FIRST before doing anything else.

## What

The check fires on every `.claude/agents/*.md` file. Mechanics:

- Run the literal grep: `grep -cE "^#+\s*(Mandatory reading order|When invoked)" <file>`.
- If the count is ≥ 1 → **PASS** (at least one of the two canonical entry-protocol section variants is present).
- If the count is 0 → **FAIL** (no entry protocol declared).

Either variant satisfies the check — `Mandatory reading order` (used by critics that must read parent artifacts before judging) or `When invoked` (used by generators that walk a clear process on each invocation).

## Why

Subagents run in isolated context windows; they do NOT inherit the main agent's context. Without an explicit "read this first" section, the subagent risks operating on stale assumptions, missing constraints that live in ADRs / parent PRDs / linked issues, or hallucinating context that the main agent had but the subagent does not.

The two-variant pattern reflects the two natural shapes:
- **Critics** typically have a "Mandatory reading order" because their job is to ground the verdict in linked artifacts (PRD body, ADRs, diff, parent issue).
- **Generators** typically have a "When invoked" because their job is to walk a deterministic process from a clear input to a clear output.

Either form serves the same purpose: forcing the subagent to load the right context before acting. Missing both is a strong signal the subagent will silently make wrong calls on cold-start invocations.

## How to check

For each `.claude/agents/*.md` file:

1. Run `grep -cE "^#+\s*(Mandatory reading order|When invoked)" <file>`.
2. If ≥ 1 → PASS.
3. If 0 → FAIL; the report should flag the file as missing the entry-protocol section.

## Examples

- **`reviewer.md` with `## Mandatory reading order`** → PASS.
- **`slicer.md` with `## When invoked`** → PASS.
- **`prd-critic.md` with both headings** → PASS (count = 2).
- **A subagent file with `## Reading order` (missing "Mandatory")** → FAIL (literal pattern requires "Mandatory reading order" exactly).
- **A subagent file with `## Process` describing entry behavior but no canonical heading** → FAIL.

## Edges

- **part_of:** [[entities/skills/audit-subagents]]
- **related_to:** [[concepts/rules/as-all-1]]
- **related_to:** [[concepts/rules/as-all-3]]
