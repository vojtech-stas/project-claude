---
title: GC-CANONICAL-SHAPE — glossary-critic rule 3, definition is a single declarative sentence
summary: The glossary-critic rule that the definition body of a draft entry is a single declarative sentence — multi-sentence creep, tutorial-shaped padding, vague "things related to X" prose, fragments without verbs, and markdown-formatted lists FAIL the rule.
tags: [rule, glossary-critic-rubric]
type: concept
last_updated: 2026-05-26
sources:
  - .claude/agents/glossary-critic.md rule 3 (one-sentence definition)
  - decisions/0007-vocabulary-glossary-and-grill-me-extension.md D2
  - decisions/0012-glossary-consolidation-single-tier.md D4
---

# GC-CANONICAL-SHAPE

**GC-CANONICAL-SHAPE** is rule 3 in the [`glossary-critic`](../../../.claude/agents/glossary-critic.md) rubric. It enforces that the definition body of every draft glossary entry is exactly **one declarative sentence**, mirroring the canonical entry shape defined in [ADR-0007](../../../decisions/0007-vocabulary-glossary-and-grill-me-extension.md) D2 (term + 1-sentence definition + scope + authority + see-also). Multi-sentence definitions, tutorial-shaped padding, vague "things related to X" prose, fragments without verbs, and markdown-formatted lists FAIL the rule.

The shape exists because the consolidated CLAUDE.md glossary auto-loads on every session per [ADR-0007](../../../decisions/0007-vocabulary-glossary-and-grill-me-extension.md) D1 — every extra sentence per entry compounds across the ~35-entry soft cap (per [ADR-0012](../../../decisions/0012-glossary-consolidation-single-tier.md) D5) into measurable context-budget waste.

## What

The rule fires on every draft entry's definition body. Mechanics:

- Locate the definition field (between the term and the trailing scope/authority/see-also fields).
- Count sentence-terminating punctuation (`.`, `!`, `?`) outside any embedded code spans.
- If >1 terminator → FAIL with `"definition: '<X>' uses <N> sentences; must be exactly one declarative sentence per ADR-0007 D2"`.
- If the definition is a fragment with no verb (e.g., "A type of slice."), or a list, or markdown-formatted prose (bullets, sub-headings) → FAIL with `"definition: '<X>' is not a declarative sentence"`.
- The single sentence may use parenthetical clauses, semicolons, or em-dashes — what counts is one main predicate.

## Why

A one-sentence definition cap is the cheapest discipline that keeps the glossary at glance-readable density. Every entry the reader scans on session-start gets ~5 seconds of attention; an entry that demands a paragraph either gets skipped (defeating the purpose) or steals attention from the next entry (compounding cost across all 35).

Tutorial-shaped definitions ("This concept is important because...") also smuggle Why content into a What slot — Why belongs in the cited authority (the ADR's rationale section), not in the glossary entry. The discipline forces the author to confront whether the term actually has a single referent or is being used as a hand-wave umbrella for multiple concepts.

## How to check

For each draft entry's definition body:

1. Read the field; identify start and end (term colon to scope category line).
2. Count `.`/`!`/`?` outside code spans. If >1 → FAIL.
3. Verify the field is a complete declarative clause (subject + verb + object/complement). If fragment or list → FAIL.
4. Verify no embedded markdown structure (bullets, sub-headings, fenced blocks).

## Examples

- **"PRD — a feature-sized Product Requirements Document captured as a GitHub Issue labeled `prd`, with the 6-section template (Problem / Goal / Non-goals / Appetite / Solution sketch / Rabbit-holes & Open questions); the top tier of the PRD → Slice → PR hierarchy."** → PASS (one sentence, parenthetical + semicolon-coordinated).
- **"slice — a vertical sub-issue of a PRD. It must satisfy INVEST. It fits in one PR."** → FAIL (3 sentences).
- **"backlog — things that are queued"** → FAIL (vague + fragment, no concrete predicate).
- **"critic — see critic"** → FAIL (no actual definition; self-reference).

## Edges

- **part_of:** [[entities/subagents/glossary-critic]]
- **related_to:** [[concepts/rules/gc-scope-tagged]]
- **related_to:** [[concepts/rules/gc-authority-resolvable]]
