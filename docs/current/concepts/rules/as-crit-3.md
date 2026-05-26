---
title: AS-CRIT-3 — audit-subagents critic check, CRITIC trailer spec present (VERDICT/REASON/ROUND)
summary: The audit-subagents critic-only mechanical check that every critic body contains the three canonical CRITIC trailer fields (VERDICT:, REASON:, ROUND:) per ADR-0005 D1b; missing any of the three FAILS the check.
tags: [rule, audit-subagents-rubric]
type: concept
last_updated: 2026-05-27
sources:
  - .claude/skills/audit-subagents/SKILL.md CRIT-3
  - decisions/0011-subagent-quality-framework.md D4
  - decisions/0005-output-shape-and-slicing-methodology.md D1b
---

# AS-CRIT-3

**AS-CRIT-3** is the [`/audit-subagents`](../../entities/skills/audit-subagents.md) rubric check (scope: `critic`) that enforces every critic body documents the canonical [CRITIC trailer](../glossary/critic-trailer.md) field schema — the three required fields `VERDICT:`, `REASON:`, and `ROUND:` — per [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D1b. A critic file missing any one of the three FAILS the check.

## What

The check fires on every critic file. Mechanics:

- Run three fixed-string greps and require ALL three to match:
  - `grep -cF "VERDICT:" <file>` ≥ 1 AND
  - `grep -cF "REASON:" <file>` ≥ 1 AND
  - `grep -cF "ROUND:" <file>` ≥ 1.
- If all three counts are ≥ 1 → **PASS**.
- If any one count is 0 → **FAIL** (trailer spec incomplete).

The check verifies the trailer is *documented in the critic body*, not that the trailer is actually emitted at runtime — the latter is the critic's responsibility per its own rubric, not an audit-subagents concern.

## Why

The CRITIC trailer is the project's machine-parsable verdict-output contract: downstream consumers (`/ship`, future orchestrators, audit pipelines) parse it to determine APPROVE/BLOCK and route accordingly. A critic that does not document the trailer in its body will either omit it at runtime (silent break) or invent a non-canonical shape (parser break) — both of which manifest as orchestration failures downstream.

Checking all three fields together (rather than just one) catches a common drift pattern: copy-pasting a partial trailer template. If a critic has `VERDICT:` and `REASON:` but missing `ROUND:`, the trailer is technically present but useless for the ≤3-round loop that critics participate in.

## How to check

For each critic file:

1. Run `grep -cF "VERDICT:" <file>`.
2. Run `grep -cF "REASON:" <file>`.
3. Run `grep -cF "ROUND:" <file>`.
4. If all three counts are ≥ 1 → PASS.
5. If any count = 0 → FAIL; the report should flag the file and the missing field(s).
6. For generators → render `—` (the GENERATOR trailer has its own check, AS-GEN-1).

## Examples

- **`prd-critic.md` with a fenced CRITIC trailer block listing all three fields** → PASS.
- **`reviewer.md` documenting the trailer in its "Output format" section** → PASS.
- **A critic file with `VERDICT:` and `REASON:` but no `ROUND:`** → FAIL (missing ROUND).
- **A critic file with the trailer described in prose ("returns a verdict, reason, and round") but no literal `VERDICT:` token** → FAIL.

## Edges

- **part_of:** [[entities/skills/audit-subagents]]
- **related_to:** [[concepts/rules/as-crit-4]]
- **related_to:** [[concepts/rules/as-gen-1]]
- **related_to:** [[concepts/glossary/critic-trailer]]
