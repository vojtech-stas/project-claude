---
title: GC-SCOPE-TAGGED — glossary-critic rule 1, scope category fits exactly one of a/b/c
summary: The glossary-critic rule that every draft entry declares a scope category — (a) project jargon coined here, (b) external standard adopted, or (c) common word with narrowed meaning here — and that the declared category is defensible; industry-background terms with their standard meaning intact, missing categories, or mis-declared categories FAIL the rule.
tags: [rule, glossary-critic-rubric]
type: concept
last_updated: 2026-05-26
sources:
  - .claude/agents/glossary-critic.md rule 1 (scope category fits a/b/c)
  - decisions/0007-vocabulary-glossary-and-grill-me-extension.md D3
---

# GC-SCOPE-TAGGED

**GC-SCOPE-TAGGED** is rule 1 in the [`glossary-critic`](../../../.claude/agents/glossary-critic.md) rubric. It enforces that every draft entry declares a scope category from the closed three-category set per [ADR-0007](../../../decisions/0007-vocabulary-glossary-and-grill-me-extension.md) D3:

- **(a) Project jargon coined here** — e.g., `PRD`, `slice`, `walking-skeleton`, `R-LOC`.
- **(b) External standards adopted** — e.g., `INVEST`, `SPIDR`, `hamburger method`, `ADR`, `Conventional Commits`.
- **(c) Common words with narrowed meaning here** — e.g., `slice` (vs general "piece"), `critic` (vs general "reviewer"), `trivial` (vs casual meaning).

Industry-background terms with their standard meaning intact ("TypeScript", "CI", "JSON"), missing categories, or mis-declared categories all FAIL the rule.

## What

The rule fires on every draft entry's scope field. Mechanics:

- Locate the declared scope category. If absent → FAIL with `"scope: entry missing required category (a/b/c) per ADR-0007 D3"`.
- Read the category and the definition; verify the category fits:
  - (a) requires the term to be coined here (not in any external glossary).
  - (b) requires the term to be a recognized industry standard adopted here.
  - (c) requires the term to have a NARROWED meaning here that differs from its casual sense.
- If the term is industry background with no narrowed meaning ("JSON", "git", "regex") → FAIL with `"scope: term '<X>' is industry background with no narrowed meaning here; does not fit a/b/c"`.
- If two categories are plausible, the picked one must be defensible (e.g., `slice` is both project jargon AND a narrowed common word — the project picks (c) because the underlying word predates the project). If indefensible → FAIL with `"scope: term '<X>' claims category <Y> but fits <Z> better; revise"`.

## Why

The three-category taxonomy exists because the glossary serves three different consumer needs that benefit from category-aware reading:

- Project jargon (a) entries are **load-bearing** — readers MUST learn them to operate; the authority points to the project-internal source.
- External standard (b) entries are **bridge** — readers may know the term elsewhere but need the project's specific application; authority points to the external canonical source.
- Narrowed-common (c) entries are **trap-prevention** — readers think they know the word; the entry exists to disambiguate; authority anchors the narrowing.

Industry-background terms with no project-specific spin ("JSON") are **noise** — they bloat the glossary without giving the reader anything they didn't already have. The rule is the front-line defense against the glossary degrading into a generic computing dictionary.

## How to check

For each draft entry:

1. Locate the `*Scope:*` field. If missing → FAIL.
2. Read the claimed category letter.
3. Apply the three fit-tests above against the term + definition.
4. If the term is generic industry-background, FAIL with the standard message.
5. If two categories fit, verify the picked one is defensible; if not, FAIL with the better-fit suggestion.

## Examples

- **`*Scope:* (a) project jargon coined here` for term "R-LOC"** → PASS (the reviewer rule ID was coined in this project).
- **`*Scope:* (b) external standard adopted` for term "Conventional Commits"** → PASS (recognized industry spec adopted with project-specific tightening).
- **`*Scope:* (c) common word with narrowed meaning here` for term "critic"** → PASS (general word, narrowed here to "adversarial-audit subagent emitting APPROVE/BLOCK verdicts").
- **`*Scope:* (a)` for term "TypeScript"** → FAIL (industry-background; no narrowed meaning here).
- **No scope field** → FAIL.

## Edges

- **part_of:** [[entities/subagents/glossary-critic]]
- **related_to:** [[concepts/rules/gc-canonical-shape]]
- **related_to:** [[concepts/rules/gc-no-duplicate]]
- **related_to:** [[concepts/rules/gc-citation-threshold]]
