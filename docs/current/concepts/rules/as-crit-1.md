---
title: AS-CRIT-1 — audit-subagents critic check, "Default conservative" clause present
summary: The audit-subagents critic-only mechanical check that every critic body contains the literal "Default conservative" string — the ADR-0009 D3 default-BLOCK clause that biases ambiguous critic verdicts toward BLOCK rather than APPROVE.
tags: [rule, audit-subagents-rubric]
type: concept
last_updated: 2026-05-27
sources:
  - .claude/skills/audit-subagents/SKILL.md CRIT-1
  - decisions/0011-subagent-quality-framework.md D4
  - decisions/0009-discipline-tightening.md D3
---

# AS-CRIT-1

**AS-CRIT-1** is the [`/audit-subagents`](../../entities/skills/audit-subagents.md) rubric check (scope: `critic` — applies only to files classified as critic per [ADR-0011](../../../decisions/0011-subagent-quality-framework.md) D3) that enforces every critic body contains the literal string **"Default conservative"**. Per [ADR-0011](../../../decisions/0011-subagent-quality-framework.md) D4 + [ADR-0009](../../../decisions/0009-discipline-tightening.md) D3, this is the canonical **default-BLOCK clause**: when a critic is uncertain about a rubric criterion, the verdict should be BLOCK, not APPROVE.

## What

The check fires on every `.claude/agents/*-critic.md` file plus `reviewer.md` (per [ADR-0011](../../../decisions/0011-subagent-quality-framework.md) D3 classifier). Mechanics:

- Run the literal grep: `grep -cF "Default conservative" <file>`.
- If the count is ≥ 1 → **PASS** (the default-BLOCK clause is present).
- If the count is 0 → **FAIL** (clause missing).

The `-F` flag forces fixed-string matching (no regex interpretation); the literal must appear verbatim somewhere in the file.

## Why

[ADR-0009](../../../decisions/0009-discipline-tightening.md) D3 establishes the **asymmetric-cost principle** for critic verdicts: a spurious BLOCK costs one human-prompt round to refute; a wrong APPROVE lets a real defect ship into a merged PR (much more expensive to revert). Critics must therefore bias their default toward BLOCK on ambiguity.

Hard-coding "Default conservative" as a literal string check (rather than a semantic check) is a deliberate trade-off per the [ADR-0011](../../../decisions/0011-subagent-quality-framework.md) D2 mechanical-only rubric: the grep catches critic prompts that were edited to remove the clause OR copy-pasted from a pre-[ADR-0009](../../../decisions/0009-discipline-tightening.md) template OR drifted into permissive defaults. A FAIL here is a strong signal the critic will silently flip APPROVE in close cases.

## How to check

For each `.claude/agents/*-critic.md` file AND `reviewer.md`:

1. Run `grep -cF "Default conservative" <file>`.
2. If ≥ 1 → PASS.
3. If 0 → FAIL; the report should flag the file as missing the default-BLOCK clause.
4. For generators (per the [ADR-0011](../../../decisions/0011-subagent-quality-framework.md) D3 classifier) → render `—` (em-dash, scope-not-applicable).

## Examples

- **`prd-critic.md` with `**Default conservative.** When uncertain about...`** → PASS.
- **`reviewer.md` with the default-BLOCK clause documented near the top of the body** → PASS.
- **A critic file with "default-conservative" (lowercase + hyphen, not the literal phrase)** → FAIL (case-sensitive `-F` grep).
- **`slicer.md` (generator)** → `—` (scope-not-applicable).

## Edges

- **part_of:** [[entities/skills/audit-subagents]]
- **related_to:** [[concepts/rules/as-crit-2]]
- **related_to:** [[concepts/rules/as-crit-3]]
