---
title: AM-STRUCT-NAMING — audit-meta structure check, naming and structure invariants (STRUCT-6 + STRUCT-7 + STRUCT-8)
summary: The audit-meta structure-subcommand mechanical check family enforcing canonical naming and single-SKILL.md structure across .claude/agents/, .claude/skills/, and decisions/.
tags: [rule, audit-meta-rubric, structure]
type: concept
last_updated: 2026-05-27
sources:
  - .claude/skills/audit-meta/SKILL.md STRUCT-6
  - .claude/skills/audit-meta/SKILL.md STRUCT-7
  - .claude/skills/audit-meta/SKILL.md STRUCT-8
  - decisions/0017-audit-meta-consolidation.md D2
---

# AM-STRUCT-NAMING

**AM-STRUCT-NAMING** is the [`/audit-meta`](../../entities/skills/audit-meta.md) `--structure` subcommand check family covering three naming / structure invariants per [ADR-0017](../../../decisions/0017-audit-meta-consolidation.md) D2:

- **STRUCT-6** — every file under `.claude/agents/*.md` matches the kebab-case `[a-z-]+(-critic)?\.md` pattern.
- **STRUCT-7** — every `.claude/skills/*/` directory contains exactly one `SKILL.md` and no other `.md` files at that depth (single-SKILL.md convention).
- **STRUCT-8** — every `decisions/NNNN-*.md` file matches the `NNNN-<kebab-slug>.md` pattern (where NNNN is exactly 4 digits).

Each FAILs (not WARNs) on violation — naming is a hard contract per the broader project conventions.

## What

The checks fire under the `structure` subcommand. Mechanics:

- **STRUCT-6:** `ls .claude/agents/ | grep -vE '^[a-z-]+\.md$'` → empty → PASS; non-empty → FAIL (list offenders).
- **STRUCT-7:** `find .claude/skills -mindepth 2 -maxdepth 2 -name "*.md" -not -name "SKILL.md"` → empty → PASS; non-empty → FAIL.
- **STRUCT-8:** `ls decisions/ | grep -E '\.md$' | grep -vE '^[0-9]{4}-[a-z0-9-]+\.md$|^README\.md$'` → empty → PASS; non-empty → FAIL (list offenders).

All three use negative-grep (`grep -v`) patterns: list everything, exclude what matches the pattern, anything left over is the violation set.

## Why

Naming invariants exist because they encode the project's auto-discovery contracts:

- **STRUCT-6** — the `[a-z-]+(-critic)?\.md` shape is how the [ADR-0011](../../../decisions/0011-subagent-quality-framework.md) D3 classifier distinguishes critics from generators. A file named `Reviewer.md` (uppercase) or `prd_critic.md` (snake_case) breaks the classifier.
- **STRUCT-7** — the one-SKILL.md-per-directory convention is the Claude Code skills runtime contract. A skill directory with multiple `.md` files at depth 2 will either not load the skill correctly OR load the wrong file as the entry point.
- **STRUCT-8** — the `NNNN-<kebab-slug>.md` shape is how ADR cross-references resolve. An ADR named `0011_skill_quality.md` (underscore) will not match the [ADR-NNNN](decisions/NNNN-*.md) link pattern that propagates through every other doc.

The README.md carve-out in STRUCT-8 accommodates the `decisions/README.md` index file (the only non-NNNN .md legitimately in that directory).

## How to check

When `--structure` is active:

1. Run STRUCT-6 grep. Empty → PASS. Non-empty → FAIL with offender list.
2. Run STRUCT-7 find. Empty → PASS. Non-empty → FAIL with offender list.
3. Run STRUCT-8 grep. Empty → PASS. Non-empty → FAIL with offender list.

## Examples

- **All agent files named `prd-critic.md`, `reviewer.md`, `slicer.md`, etc.** → STRUCT-6 PASS.
- **An agent file `Reviewer-Critic.md`** → STRUCT-6 FAIL.
- **Every skill directory has exactly one SKILL.md** → STRUCT-7 PASS.
- **`.claude/skills/ship/NOTES.md` exists** → STRUCT-7 FAIL.
- **All ADRs follow `0017-audit-meta-consolidation.md` pattern** → STRUCT-8 PASS.
- **`decisions/draft-something.md` exists** → STRUCT-8 FAIL (not 4-digit prefix).

## Edges

- **part_of:** [[entities/skills/audit-meta]]
- **related_to:** [[concepts/rules/am-struct-counts]]
- **related_to:** [[concepts/rules/am-struct-root-files]]
