---
title: PC-PRD-COMPLETENESS — prd-critic criterion 1, all six PRD template sections present and concretely populated
summary: The prd-critic rule that every draft PRD has all six template sections (Problem / Goal / Non-goals / Appetite / Solution sketch / Rabbit-holes & Open questions) populated with concrete content; empty, "TBD", or vague-prose sections FAIL the rule.
tags: [rule, prd-critic-rubric]
type: concept
last_updated: 2026-05-26
sources:
  - .claude/agents/prd-critic.md criterion 1
  - decisions/0003-autonomous-pipeline-with-critics.md D1
  - .claude/skills/to-prd/SKILL.md 6-section template
---

# PC-PRD-COMPLETENESS

**PC-PRD-COMPLETENESS** is criterion 1 in the [`prd-critic`](../../../.claude/agents/prd-critic.md) rubric. It enforces that every draft PRD populates all six sections of the canonical template — **Problem**, **Goal / Success criteria**, **Non-goals**, **Appetite**, **Solution sketch**, **Rabbit-holes & Open questions** — with concrete content. Empty sections, "TBD" placeholders, or one-line vague-prose ("we should improve X") FAIL the rule.

The **Problem** sub-check sub-test of this criterion is the most adversarial: it names who is hurting, how, and why now. A Problem section that hand-waves the user impact ("the codebase has some inconsistencies") is the most common rejection reason at round 1.

## What

The rule fires on every draft PRD. Mechanics:

- Read all six section headers verbatim; verify each is present with non-empty body.
- For each section, apply its specific concreteness test:
  - **Problem** — names who is hurting, how, and why now.
  - **Goal** — has at least one bullet (the PC-GOAL-VERIFIABILITY rule scores each bullet individually).
  - **Non-goals** — has at least one explicit bullet with reasoning (scored deeper by PC-NON-GOALS-EXPLICIT).
  - **Appetite** — names a slice budget, time, LoC cap, or no-new-deps stance (scored deeper by PC-APPETITE-BOUNDED).
  - **Solution sketch** — sketches an approach the slicer can decompose (scored deeper by PC-SOLUTION-SKETCH-ACTIONABLE).
  - **Rabbit-holes & Open questions** — has at least one rabbit-hole and at least one OQ OR explicit "none known" with rationale (scored deeper by PC-RABBIT-HOLES-NAMED).
- Any section missing or vague-only → FAIL.

## Why

The 6-section template exists because each section answers a downstream consumer's question:
- Problem grounds the value claim (consumer: `prd-critic` itself + `slicer-critic` rubric).
- Goal sets acceptance criteria (consumer: `qa-plan`).
- Non-goals prevents scope drift (consumer: `slicer-critic` SC-NO-NON-GOALS rule).
- Appetite anchors slice budget (consumer: `slicer-critic` SC-SLICE-COUNT-LOC rule).
- Solution sketch enables decomposition (consumer: `slicer`).
- Rabbit-holes & OQs surfaces known traps (consumer: `slicer-critic` SC-NO-RABBIT-HOLES rule).

A PRD missing any section silently strips downstream stages of their input. The rule is asymmetric on purpose: catching incompleteness at PRD time costs one revision round; catching it later costs slice rework and possibly a closed PR.

## How to check

For each draft PRD:

1. Read section by section in order. Verify all six headers present (`## 1. Problem` through `## 6. Rabbit-holes & Open questions` or equivalent).
2. For each section, verify body length ≥ 2 sentences AND concreteness test (above) passes.
3. If any section is `TBD`, empty, or single vague sentence → FAIL with the offending section number.

## Examples

- **Problem section is "We should improve the slicer"** → FAIL (no who/how/why-now).
- **Non-goals section is "TBD"** → FAIL (will drift; slicer-critic SC-NO-NON-GOALS depends on this content).
- **All six sections present, each with 3+ concrete sentences** → PASS.

## Edges

- **part_of:** [[entities/subagents/prd-critic]]
- **related_to:** [[concepts/rules/pc-non-goals-explicit]]
- **related_to:** [[concepts/rules/pc-appetite-bounded]]
- **related_to:** [[concepts/rules/pc-solution-sketch-actionable]]
- **related_to:** [[concepts/rules/pc-rabbit-holes-named]]
- **related_to:** [[concepts/rules/pc-acceptance-mechanically-verifiable]]
- **related_to:** [[concepts/glossary/prd]]
