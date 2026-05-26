---
title: AS-ALL-2 — audit-subagents check, every subagent has a "Tool boundaries" section heading
summary: The audit-subagents mechanical check that every subagent body contains an explicit "Tool boundaries" section heading naming which tools the subagent may and may not use; missing heading FAILS the check.
tags: [rule, audit-subagents-rubric]
type: concept
last_updated: 2026-05-27
sources:
  - .claude/skills/audit-subagents/SKILL.md ALL-2
  - decisions/0011-subagent-quality-framework.md D4
  - decisions/0001-foundational-design.md D6
---

# AS-ALL-2

**AS-ALL-2** is the [`/audit-subagents`](../../entities/skills/audit-subagents.md) rubric check (scope: `all`) that enforces every subagent body contains a "Tool boundaries" section heading. Per [ADR-0011](../../../decisions/0011-subagent-quality-framework.md) D4 + [ADR-0001](../../../decisions/0001-foundational-design.md) D6, the section is the canonical home for spelling out which tools the subagent may use (`Allowed:`) and which it may NOT use (`Forbidden:`) — separate from the YAML `tools:` frontmatter field (which the Claude Code runtime enforces) so a future reader can understand the *rationale* for each forbidden tool.

## What

The check fires on every `.claude/agents/*.md` file. Mechanics:

- Run the literal grep: `grep -cE "^#+\s*Tool boundaries" <file>`.
- If the count is ≥ 1 → **PASS** (at least one heading-shaped "Tool boundaries" section exists).
- If the count is 0 → **FAIL** (no such section).

The pattern matches anchored markdown-heading lines (`^#+`) followed by optional whitespace and the literal `Tool boundaries` phrase. Headings at any depth (H1, H2, H3, ...) satisfy the check.

## Why

The YAML `tools:` frontmatter field tells the runtime which tools to expose, but it carries no human-readable rationale. The "Tool boundaries" prose section is where the subagent author explains *why* — e.g., "Forbidden: `Agent` — no recursive subagent invocation per ADR-0010 D6" — so a future reader maintaining or auditing the subagent can verify the boundaries match the design intent, not just the runtime enforcement.

For critics in particular, the Tool boundaries section is also where the "no `Edit`/`Write` on tracked files" convention is documented (critics emit verdicts, they don't modify artifacts). Missing the section is a strong signal that either the author skipped the design discipline OR the subagent has drifted from its original tool-boundary contract.

## How to check

For each `.claude/agents/*.md` file:

1. Run `grep -cE "^#+\s*Tool boundaries" <file>`.
2. If ≥ 1 → PASS.
3. If 0 → FAIL; the report should flag the file as missing the canonical section.

## Examples

- **`reviewer.md` with `## Tool boundaries` H2** → PASS (count = 1).
- **`prd-critic.md` with `### Tool boundaries` H3 nested under another section** → PASS (still anchored heading, still matches).
- **`slicer.md` documenting tool boundaries inline in a "Process" section without its own heading** → FAIL (no heading match).
- **A subagent file containing "Tool boundaries" in prose but not as a heading** → FAIL (not anchored to `^#+`).

## Edges

- **part_of:** [[entities/skills/audit-subagents]]
- **related_to:** [[concepts/rules/as-all-1]]
- **related_to:** [[concepts/rules/as-all-3]]
