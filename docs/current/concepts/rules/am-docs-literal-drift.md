---
title: AM-DOCS-LITERAL-DRIFT — audit-meta docs check, named-literal drift detectors (DOCS-5 N=3, DOCS-6 GLOSSARY.md)
summary: The audit-meta docs-subcommand mechanical check pair detecting two specific stale-literal drifts — DOCS-5 catches the `N=3` literal in README.md (post-ADR-0013 fix) and DOCS-6 catches GLOSSARY.md references anywhere in *.md files (post-ADR-0012 file deletion).
tags: [rule, audit-meta-rubric, docs]
type: concept
last_updated: 2026-05-27
sources:
  - .claude/skills/audit-meta/SKILL.md DOCS-5
  - .claude/skills/audit-meta/SKILL.md DOCS-6
  - decisions/0017-audit-meta-consolidation.md D3
  - decisions/0012-glossary-consolidation-single-tier.md
  - decisions/0013-slicer-n3-contract-refined.md
---

# AM-DOCS-LITERAL-DRIFT

**AM-DOCS-LITERAL-DRIFT** is the [`/audit-meta`](../../entities/skills/audit-meta.md) `--docs` subcommand check pair detecting **named-literal drift** — specific text strings that should NOT appear because the convention they referenced has been superseded:

- **DOCS-5** — no `N=3` literal references in `README.md` (post-[ADR-0013](../../../decisions/0013-slicer-n3-contract-refined.md) drift detector; PR #125 fix).
- **DOCS-6** — no `GLOSSARY.md` references anywhere in `*.md` files (post-[ADR-0012](../../../decisions/0012-glossary-consolidation-single-tier.md) drift detector; the file was deleted).

Both check for absence of a known-bad literal; either non-empty match FAILs.

## What

The checks fire under the `docs` subcommand. Mechanics:

- **DOCS-5:** `grep -cF "N=3" README.md` == 0 → PASS; ≥ 1 → FAIL.
- **DOCS-6:** `grep -rlF "GLOSSARY.md" --include="*.md" . | grep -v "^./.git/"` → empty → PASS; non-empty → FAIL (list offending files).

Both use fixed-string matching (`-F`) for speed and to avoid regex false-positives. DOCS-5 is scoped to README.md only (the file that historically carried the wrong literal); DOCS-6 is repo-wide because GLOSSARY.md could be referenced anywhere.

## Why

The named-literal drift pattern catches a specific failure mode: **a convention is superseded, the ADR is written, the canonical file is updated, but cross-references in OTHER files retain the stale literal.** This is exactly what happened with:

- **`N=3`** — [ADR-0013](../../../decisions/0013-slicer-n3-contract-refined.md) refined the slicer's N-decompositions contract; PR #125 fixed the README but the literal could regress. DOCS-5 ensures it stays gone.
- **`GLOSSARY.md`** — [ADR-0012](../../../decisions/0012-glossary-consolidation-single-tier.md) consolidated the glossary into CLAUDE.md and deleted the standalone `GLOSSARY.md` file. Any remaining reference to that filename is dead — either a broken link or a stale instruction.

Each check is **purpose-built for a known regression**, not a general convention. As new conventions supersede old ones, new DOCS-* literal-drift checks may be added (each cheap, each focused on one named literal).

## How to check

When `--docs` is active:

1. Run DOCS-5: `grep -cF "N=3" README.md`. PASS if 0; FAIL if ≥ 1.
2. Run DOCS-6: `grep -rlF "GLOSSARY.md" --include="*.md" .` excluding `.git/`. PASS if empty; FAIL with file list otherwise.

## Examples

- **`README.md` describes slicer N as "default 3" without the literal `N=3`** → DOCS-5 PASS.
- **`README.md` still contains `N=3` somewhere** → DOCS-5 FAIL.
- **No file references `GLOSSARY.md`** → DOCS-6 PASS.
- **An older subagent file still says "see GLOSSARY.md for vocabulary"** → DOCS-6 FAIL.
- **A file mentions GLOSSARY.md inside a quoted historical block** → DOCS-6 FAIL (default-conservative per skill prompt).

## Edges

- **part_of:** [[entities/skills/audit-meta]]
- **related_to:** [[concepts/rules/am-docs-backlog-surfacing]]
- **related_to:** [[concepts/rules/am-docs-glossary-cap]]
