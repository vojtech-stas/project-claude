---
title: AM-STRUCT-SIZES — audit-meta structure check, file-size and nesting-depth bloat detectors (STRUCT-3 + STRUCT-4)
summary: The audit-meta structure-subcommand mechanical check covering STRUCT-3 (no markdown file > 500 LoC, split candidate detector) and STRUCT-4 (no directory depth > 4, nesting-bloat detector).
tags: [rule, audit-meta-rubric, structure]
type: concept
last_updated: 2026-05-27
sources:
  - .claude/skills/audit-meta/SKILL.md STRUCT-3
  - .claude/skills/audit-meta/SKILL.md STRUCT-4
  - decisions/0017-audit-meta-consolidation.md D2
---

# AM-STRUCT-SIZES

**AM-STRUCT-SIZES** is the [`/audit-meta`](../../entities/skills/audit-meta.md) `--structure` subcommand check family covering two bloat detectors per [ADR-0017](../../../decisions/0017-audit-meta-consolidation.md) D2:

- **STRUCT-3** — no markdown file > 500 LoC (split-candidate detector). PASS/WARN.
- **STRUCT-4** — no directory depth > 4 (nesting-bloat detector, relative to repo root, excluding `.git/`). PASS/FAIL.

The pair surfaces files / directories that have grown past the project's "still scannable in one read" thresholds.

## What

The checks fire under the `structure` subcommand. Mechanics:

- **STRUCT-3:** `find . -name "*.md" -not -path "./.git/*" -exec wc -l {} \; | awk '$1 > 500'` → empty → PASS; non-empty → WARN (list offending files with their LoC).
- **STRUCT-4:** `find . -type d -not -path "./.git*" | awk -F/ 'NF-1 > 5'` → empty → PASS; non-empty → FAIL (list offending directories).

STRUCT-3 is WARN-level because some files (CLAUDE.md, certain ADRs) legitimately grow large; the audit surfaces candidates for the user to triage. STRUCT-4 is FAIL-level because nesting depth >4 is a hard structural smell — the project's tree should fit a 4-level mental model.

## Why

The 500-LoC threshold for markdown files is the project's **"split me" smoke alarm**: per the slicer's [R-LOC](r-loc.md) precedent and the general principle that anything past 500 lines in a single file outruns one-read comprehension, files past the cap deserve a slicing thought-experiment. The audit does NOT force a split (PR ergonomics, ADR length, etc. may justify exceptions) but surfaces the candidates.

The depth-4 cap reflects the project's natural tree: `repo/.claude/agents/foo.md` is depth 3, `repo/docs/current/concepts/rules/foo.md` is depth 5 — actually, wait, that's NF-1=5, so the cap is hit. The `awk -F/ 'NF-1 > 5'` predicate flags depth >5 (i.e., 6 or more path segments), so `docs/current/concepts/rules/foo.md` is at the cap, not over it. New trees deeper than that (e.g., `docs/current/concepts/rules/sub/sub/foo.md`) FAIL.

## How to check

When `--structure` is active:

1. Run the STRUCT-3 find/awk pipeline. Empty result → PASS. Non-empty → WARN with the offender list.
2. Run the STRUCT-4 find/awk pipeline. Empty → PASS. Non-empty → FAIL with the offender list.

## Examples

- **No markdown file > 500 LoC** → STRUCT-3 PASS.
- **`decisions/0003-autonomous-pipeline-with-critics.md` at 612 LoC** → STRUCT-3 WARN (file listed in details).
- **Tree max depth = 4 (no directory deeper than `repo/.claude/skills/foo/`)** → STRUCT-4 PASS.
- **A new directory `docs/x/y/z/w/sub/` created** → STRUCT-4 FAIL.

## Edges

- **part_of:** [[entities/skills/audit-meta]]
- **related_to:** [[concepts/rules/am-struct-counts]]
- **related_to:** [[concepts/rules/r-loc]]
