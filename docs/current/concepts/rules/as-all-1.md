---
title: AS-ALL-1 — audit-subagents check, every subagent has frontmatter with name/description/tools/model fields
summary: The audit-subagents mechanical check that every file under .claude/agents/*.md begins with a YAML frontmatter block declaring all four required fields (name, description, tools, model); missing or partial frontmatter FAILS the check.
tags: [rule, audit-subagents-rubric]
type: concept
last_updated: 2026-05-27
sources:
  - .claude/skills/audit-subagents/SKILL.md ALL-1
  - decisions/0011-subagent-quality-framework.md D4
  - decisions/0001-foundational-design.md D6
---

# AS-ALL-1

**AS-ALL-1** is the [`/audit-subagents`](../../entities/skills/audit-subagents.md) rubric check (scope: `all` — applies to every subagent regardless of critic/generator classification) that enforces every file under `.claude/agents/*.md` declares the four canonical frontmatter fields per [ADR-0001](../../../decisions/0001-foundational-design.md) D6: `name`, `description`, `tools`, `model`. Per [ADR-0011](../../../decisions/0011-subagent-quality-framework.md) D4, this is the foundational well-formedness check — a subagent missing any of the four fields will not load correctly via the `Agent` tool.

## What

The check fires on every `.claude/agents/*.md` file. Mechanics:

- Run the literal grep: `grep -cE "^(name|description|tools|model):" <file>`.
- If the count is ≥ 4 → **PASS** (all four fields present at the start of a line, in YAML-frontmatter shape).
- If the count is < 4 → **FAIL** (one or more required fields missing).

The pattern matches line-starts only (anchored `^`), so YAML fields embedded inside prose or example blocks do not satisfy the check — only true frontmatter declarations count.

## Why

[ADR-0001](../../../decisions/0001-foundational-design.md) D6 defines the canonical subagent shape: a YAML frontmatter block declaring identity (`name`), purpose (`description`, which drives auto-delegation), tool boundaries (`tools`), and model choice (`model`). The Claude Code runtime parses this frontmatter at subagent load time; a missing field either prevents the subagent from loading at all (`name`) or silently widens its capabilities beyond what the author intended (`tools` missing → default-broad).

This check is the cheapest, most-foundational drift detector: it catches subagents that were hand-edited to remove fields, copy-pasted from incomplete templates, or migrated from an older shape that pre-dates [ADR-0001](../../../decisions/0001-foundational-design.md). A FAIL here usually points to a partial migration that should be completed in a single corrective slice.

## How to check

For each `.claude/agents/*.md` file:

1. Open the file; locate the leading `---`-delimited YAML frontmatter block.
2. Run `grep -cE "^(name|description|tools|model):" <file>`.
3. If the count is ≥ 4 → PASS.
4. If the count is < 4 → FAIL; the report should list the file and the missing field(s).

## Examples

- **`reviewer.md` with `name:`, `description:`, `tools:`, `model:` all present in frontmatter** → PASS (count = 4).
- **`slicer.md` missing the `model:` field** → FAIL (count = 3).
- **`prd-critic.md` with `name`, `description`, `tools`, `model` documented in prose but no YAML frontmatter block** → FAIL (no anchored `^name:`-style line at file start).

## Edges

- **part_of:** [[entities/skills/audit-subagents]]
- **related_to:** [[concepts/rules/as-all-2]]
- **related_to:** [[concepts/rules/as-all-5]]
