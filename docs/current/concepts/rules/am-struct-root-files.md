---
title: AM-STRUCT-ROOT-FILES — audit-meta structure check, root README.md and CLAUDE.md presence (STRUCT-9 + STRUCT-10)
summary: The audit-meta structure-subcommand mechanical check pair enforcing that root README.md (STRUCT-9) and root CLAUDE.md (STRUCT-10) exist and are non-empty — the two load-bearing root docs every project requires.
tags: [rule, audit-meta-rubric, structure]
type: concept
last_updated: 2026-05-27
sources:
  - .claude/skills/audit-meta/SKILL.md STRUCT-9
  - .claude/skills/audit-meta/SKILL.md STRUCT-10
  - decisions/0017-audit-meta-consolidation.md D2
---

# AM-STRUCT-ROOT-FILES

**AM-STRUCT-ROOT-FILES** is the [`/audit-meta`](../../entities/skills/audit-meta.md) `--structure` subcommand check pair covering presence of the two load-bearing root docs per [ADR-0017](../../../decisions/0017-audit-meta-consolidation.md) D2:

- **STRUCT-9** — root `README.md` exists and is non-empty.
- **STRUCT-10** — root `CLAUDE.md` exists and is non-empty.

Both FAIL on missing or empty; both are the cheapest possible existence checks in the rubric but matter disproportionately because the two files are the project's universal entry points.

## What

The checks fire under the `structure` subcommand. Mechanics:

- **STRUCT-9:** `test -s README.md` → PASS; else FAIL.
- **STRUCT-10:** `test -s CLAUDE.md` → PASS; else FAIL.

The `test -s` flag returns true if the file exists AND is non-empty (size > 0). An empty README.md or CLAUDE.md FAILs the check just as decisively as a missing one — an empty file is worse than a missing file because it suggests the file was intentionally created but then truncated.

## Why

These two files are the **universal entry-point contract**:

- **`README.md`** is what GitHub renders on the repo landing page; it's the first thing a human visitor sees. A missing or empty README is a hard signal of repo abandonment or misconfiguration.
- **`CLAUDE.md`** is what Claude Code auto-loads on every session in this repo; it's the first thing every AI agent sees. A missing or empty CLAUDE.md means agents operate without project rules, conventions, and the load-bearing glossary — they default to generic behavior.

Both checks are trivially cheap (one syscall each) but extremely consequential. They're in the structure rubric (not the docs rubric) because they're about **structural presence**, not content currency.

## How to check

When `--structure` is active:

1. Run `test -s README.md`. PASS if exit 0; FAIL if exit non-zero.
2. Run `test -s CLAUDE.md`. PASS if exit 0; FAIL if exit non-zero.

## Examples

- **Repo with both files populated** → STRUCT-9 PASS, STRUCT-10 PASS.
- **Repo with `README.md` deleted** → STRUCT-9 FAIL.
- **Repo with `CLAUDE.md` accidentally truncated to zero bytes** → STRUCT-10 FAIL.
- **Repo with `Readme.md` (wrong case) instead of `README.md`** → STRUCT-9 FAIL (case-sensitive on case-sensitive filesystems).

## Edges

- **part_of:** [[entities/skills/audit-meta]]
- **related_to:** [[concepts/rules/am-struct-naming]]
- **related_to:** [[concepts/rules/am-docs-claude-md-map]]
