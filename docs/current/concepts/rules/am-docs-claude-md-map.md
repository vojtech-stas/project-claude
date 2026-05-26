---
title: AM-DOCS-CLAUDE-MD-MAP — audit-meta docs check, CLAUDE.md Map row references resolve (DOCS-3 + DOCS-4)
summary: The audit-meta docs-subcommand mechanical check pair enforcing that every .claude/agents/*.md and .claude/skills/*/SKILL.md reference in the CLAUDE.md Map section resolves to an existing file (no dangling Map rows).
tags: [rule, audit-meta-rubric, docs]
type: concept
last_updated: 2026-05-27
sources:
  - .claude/skills/audit-meta/SKILL.md DOCS-3
  - .claude/skills/audit-meta/SKILL.md DOCS-4
  - decisions/0017-audit-meta-consolidation.md D3
---

# AM-DOCS-CLAUDE-MD-MAP

**AM-DOCS-CLAUDE-MD-MAP** is the [`/audit-meta`](../../entities/skills/audit-meta.md) `--docs` subcommand check pair enforcing that the CLAUDE.md Map section's file references resolve per [ADR-0017](../../../decisions/0017-audit-meta-consolidation.md) D3:

- **DOCS-3** — every `.claude/agents/*.md` referenced in CLAUDE.md Map exists (no dangling agent rows).
- **DOCS-4** — every `.claude/skills/*/SKILL.md` referenced in CLAUDE.md Map exists (no dangling skill rows).

Both FAIL on any missing target. Together they catch the regression where an agent or skill is renamed / deleted without updating the CLAUDE.md Map.

## What

The checks fire under the `docs` subcommand. Mechanics:

- **DOCS-3:** extract every `\.claude/agents/[a-z-]+\.md` reference from `CLAUDE.md`; for each, run `test -f`. All exist → PASS. Any missing → FAIL (list dangling refs).
- **DOCS-4:** extract every `\.claude/skills/[a-z-]+/SKILL\.md` reference from `CLAUDE.md`; for each, run `test -f`. All exist → PASS. Any missing → FAIL.

The patterns use lowercase-kebab-only classes for the directory / file segments, mirroring the AM-STRUCT-NAMING pattern. References to files outside that shape don't match the extraction (and would also FAIL the structure rubric, so they get caught upstream).

## Why

The CLAUDE.md Map is the project's **agent/skill discovery surface** for every Claude Code session. A dangling reference there means an agent goes looking for `/foo-skill`, the Map says it lives at `.claude/skills/foo-skill/SKILL.md`, the file does not exist, and the agent fails silently OR falls back to default behavior.

Unlike the ADR index (DOCS-1/DOCS-2 are bidirectional), the Map sync is checked **one direction only**: Map → file. The reverse (every agent/skill must be in the Map) is intentionally NOT checked because the Map is curated — some agents/skills are deliberately undocumented in the Map (experimental ones, deprecated stubs awaiting removal). The forward direction is the one that breaks discoverability.

## How to check

When `--docs` is active:

1. Run DOCS-3: extract agent-Map refs; check each exists. PASS / FAIL.
2. Run DOCS-4: extract skill-Map refs; check each exists. PASS / FAIL.

## Examples

- **CLAUDE.md Map lists `.claude/agents/reviewer.md`; file exists** → DOCS-3 PASS.
- **CLAUDE.md Map references `.claude/agents/deleted-critic.md`; file gone** → DOCS-3 FAIL.
- **CLAUDE.md Map lists `.claude/skills/ship/SKILL.md`; file exists** → DOCS-4 PASS.
- **A skill directory renamed from `audit-meta` to `audit` but Map still says `audit-meta`** → DOCS-4 FAIL.

## Edges

- **part_of:** [[entities/skills/audit-meta]]
- **related_to:** [[concepts/rules/am-docs-adr-index]]
- **related_to:** [[concepts/rules/am-struct-root-files]]
