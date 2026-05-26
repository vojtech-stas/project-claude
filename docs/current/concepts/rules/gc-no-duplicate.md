---
title: GC-NO-DUPLICATE — glossary-critic rule 2, term must not already exist in the consolidated glossary
summary: The glossary-critic rule that a draft term must not already appear as an entry in either the CLAUDE.md `## Glossary` section (the index) or the `docs/current/concepts/glossary/*.md` atomic notes (the canonical bodies); duplicates FAIL the rule.
tags: [rule, glossary-critic-rubric]
type: concept
last_updated: 2026-05-26
sources:
  - .claude/agents/glossary-critic.md rule 2 (no duplicate)
  - decisions/0012-glossary-consolidation-single-tier.md D1
  - decisions/0031-knowledge-architecture-v2.md D2
---

# GC-NO-DUPLICATE

**GC-NO-DUPLICATE** is rule 2 in the [`glossary-critic`](../../../.claude/agents/glossary-critic.md) rubric. It enforces that a draft term must not already exist as an entry in either location of the consolidated-and-migrated glossary surface:

- The `## Glossary` section of `CLAUDE.md` (the auto-loaded index, per [ADR-0012](../../../decisions/0012-glossary-consolidation-single-tier.md) D1).
- The atomic notes under `docs/current/concepts/glossary/*.md` (the canonical bodies, per [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D2 + D10 step 1 from PRD #245).

A matching entry in either location → FAIL.

## What

The rule fires on every draft entry's term. Mechanics:

- `Grep` the literal term (case-insensitive, whole-word) against BOTH:
  - The `## Glossary` section of `CLAUDE.md`.
  - All files matching `docs/current/concepts/glossary/*.md`.
- If a matching entry exists in either location → FAIL with `"duplicate: '<X>' already exists in <CLAUDE.md glossary INDEX | docs/current/concepts/glossary/<slug>.md atomic note>; this PR would create a second entry"`.
- Transitional note per PRD #245: the still-inline CLAUDE.md entries (those that have not yet been migrated to atomic notes) count as existing entries for duplicate-detection purposes — the migration is ongoing, but duplicate prevention applies against the union of current state.

The check is whole-word + case-insensitive to catch e.g. a draft for "PRD" colliding with the existing index entry, while not false-flagging a substring match like "prd-critic" against "PRD".

## Why

A duplicate glossary entry is worse than no entry — it creates two definitions that drift apart over time, and forces the reader to choose. The reader can't tell which is canonical. Authority anchors then point in two directions for the same term.

The "two locations" structure exists because [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D2 splits the glossary into a CLAUDE.md index (load-bearing for every session) and per-term atomic notes (canonical bodies). Both layers must stay deduplicated against each other AND internally; otherwise the index → atomic note resolution mechanism breaks.

The rule is cheap to enforce (one `grep` invocation), expensive to repair after merge (every downstream reference becomes ambiguous), so it lives at the critic gate.

## How to check

For each draft entry's term:

1. Run `grep -i -w "<term>" CLAUDE.md` (or read the `## Glossary` section directly and scan).
2. Run `grep -i -w "<term>" docs/current/concepts/glossary/*.md` (filename match also counts — the slug is the term).
3. If either returns a match within an entry definition (not an incidental mention) → FAIL with the location quoted.
4. The reverse — a passing mention of the term in a different entry's definition — does NOT count as duplication; only an own-entry collision does.

## Examples

- **Draft term "slice" — CLAUDE.md `## Glossary` already has `## slice` entry** → FAIL (index collision).
- **Draft term "boy-scout-rule" — `docs/current/concepts/glossary/boy-scout-rule.md` already exists** → FAIL (atomic-note collision).
- **Draft term "kb-maintainer" — no match in either location** → PASS (assuming other rules pass).
- **Draft term "appetite" — the word appears inside the `PRD` entry's definition** → PASS (incidental mention is not its own entry; passes rule 2; rule 5 citation count still applies).

## Edges

- **part_of:** [[entities/subagents/glossary-critic]]
- **related_to:** [[concepts/rules/gc-scope-tagged]]
- **related_to:** [[concepts/rules/gc-citation-threshold]]
