---
title: AC-CONVENTION-COMPLIANCE — adr-critic criterion 1, required ADR sections present and non-empty
summary: The adr-critic rule that every draft ADR carries the six required sections per `decisions/README.md` (Status, Date, Context, Decisions, Consequences, Alternatives considered), each populated with concrete content; one-line-empty or missing required sections FAIL.
tags: [rule, adr-critic-rubric]
type: concept
last_updated: 2026-05-26
sources:
  - .claude/agents/adr-critic.md criterion 1
  - decisions/README.md (ADR conventions)
  - decisions/0004-bypass-prevention.md D1
---

# AC-CONVENTION-COMPLIANCE

**AC-CONVENTION-COMPLIANCE** is criterion 1 in the [`adr-critic`](../../../.claude/agents/adr-critic.md) rubric. It enforces that every draft ADR carries the six required sections per `decisions/README.md` — **Status**, **Date**, **Context**, **Decisions**, **Consequences**, **Alternatives considered** — each populated with concrete content. Optional sections (Open questions deferred, Future direction, References) are encouraged but their absence is not a FAIL.

This rule exists because the ADR template is a load-bearing contract for downstream consumers: missing a Context section strips reviewers of decision-making framing; missing Consequences strips future ADRs of cited evidence; missing Alternatives considered hides the reasoning the supersession-by-D-ID mechanism later relies on. The rule is a structural pre-condition for all other rubric criteria — without the sections present, rules 2-6 have nothing to check against.

## What

The rule fires on every draft ADR. Mechanics:

- Scan section headings verbatim; verify each of the six required sections is present (`## Status`, `## Date`, `## Context`, `## Decisions`, `## Consequences`, `## Alternatives considered` or close-equivalent).
- For each section, verify body length ≥ 2 sentences AND non-vague content (no `TBD`, no single-line stub).
- Any required section missing or one-line-empty → FAIL with `"missing required section: <name>"` or `"empty required section: <name>"`.
- Optional sections absent → no finding.

## Why

The 6-section template exists because each section answers a downstream consumer's question:
- **Status** grounds supersession-by-D-ID enforcement (consumer: AC-SUPERSEDES-BY-D-ID).
- **Date** anchors temporal ordering for bootstrap-mode policy (consumer: AC-BOOTSTRAP-MODE-ACKNOWLEDGED).
- **Context** establishes the theme that AC-NO-SCOPE-CREEP rule checks each Decision against.
- **Decisions** is the load-bearing payload; everything else exists to frame it.
- **Consequences** lets future ADRs cite trade-offs accepted here without rediscovering them.
- **Alternatives considered** prevents future ADRs from re-litigating settled rejections.

A draft ADR missing any required section silently strips downstream stages of their input. Catching at draft time costs one revision round; an absent Context section discovered later causes scope-creep rule false-negatives.

## How to check

For each draft ADR:

1. Scan the H2 headings in order. Verify all six required section headers are present.
2. For each required section, verify body ≥ 2 sentences AND no `TBD` placeholder.
3. If any required section is missing → FAIL with `"missing required section: <name>"`.
4. If any required section is `TBD`/empty → FAIL with `"empty required section: <name>"`.

## Examples

- **Draft has no `## Alternatives considered` section** → FAIL (missing required section).
- **`## Context` body is "TBD"** → FAIL (empty required section).
- **All six sections present with concrete multi-sentence bodies** → PASS.

## Edges

- **part_of:** [[entities/subagents/adr-critic]]
- **related_to:** [[concepts/rules/ac-cross-adr-consistency]]
- **related_to:** [[concepts/rules/ac-supersedes-by-d-id]]
- **related_to:** [[concepts/rules/ac-no-scope-creep]]
- **related_to:** [[concepts/glossary/adr]]
