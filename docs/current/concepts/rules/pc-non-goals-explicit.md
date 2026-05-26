---
title: PC-NON-GOALS-EXPLICIT — prd-critic criterion 2, non-goals are named with one-line reasons
summary: The prd-critic rule that the Non-goals section explicitly names specific things deliberately not done with one-line reasons; empty, "TBD", or aspirational non-goals ("not too much scope") FAIL the rule.
tags: [rule, prd-critic-rubric]
type: concept
last_updated: 2026-05-26
sources:
  - .claude/agents/prd-critic.md criterion 3 (non-goals explicit)
  - decisions/0003-autonomous-pipeline-with-critics.md D1
---

# PC-NON-GOALS-EXPLICIT

**PC-NON-GOALS-EXPLICIT** is the prd-critic rubric criterion that enforces the Non-goals / Out-of-scope section names **specific things deliberately not done**, each with a one-line reason. Empty non-goals, "TBD" placeholders, or aspirational non-goals ("don't go too broad") FAIL the rule. The output of this section is the input contract for the [`slicer-critic`](../../../.claude/agents/slicer-critic.md) [SC-NO-NON-GOALS](sc-no-non-goals.md) rule — a missing non-goal at PRD time becomes an undetectable scope-creep at slicing time.

## What

The rule fires on every draft PRD's Non-goals section. Mechanics:

- Verify section is present (covered by PC-PRD-COMPLETENESS).
- Read each bullet: each one is a **specific deliverable + one-line reason**.
- Acceptable shape: "X — not in this PRD because Y (defer to future PRD-N / belongs in T-cluster / non-goal of the appetite)".
- Unacceptable shapes:
  - "TBD" or "to be determined".
  - "Don't add too much" / "keep scope tight" (aspirational, not specific).
  - Single bullet "out of scope: a bunch of stuff".
  - Negation of the Goal ("not adding bugs") — meaningless.

A PRD will drift without explicit non-goals. The rule is the upstream cousin of [SC-NO-NON-GOALS](sc-no-non-goals.md) — slicer-critic checks that no slice chases a §3 non-goal, but only if §3 actually lists non-goals worth chasing.

## Why

This rule exists because **scope creep is the largest single source of PRD failure**. A non-explicit non-goal is invisible until it becomes a slice — at which point the slicer-critic has nothing to compare against. Catching aspirational non-goals at PRD time costs one revision round; catching scope drift at slicing time costs a regenerated decomposition; catching scope drift at PR time costs a closed PR and a respin.

The "one-line reason" requirement is YAGNI's enforcement at the PRD layer: stating *why* something is deferred forces the author to confront whether it actually is deferred or is silently in-scope. Many "deferrals" collapse when challenged.

## How to check

For each draft PRD:

1. Read every bullet in §3 Non-goals.
2. For each bullet, verify: (a) names a specific deliverable, (b) gives a one-line reason.
3. If section is empty / "TBD" / aspirational-only → FAIL.
4. If any bullet lacks a reason → FAIL with the offending bullet quoted.

## Examples

- **"Non-goals: TBD"** → FAIL.
- **"Don't make the PRD too big"** → FAIL (aspirational, not specific).
- **"qa-tester subagent split — out of scope; belongs in T-cluster slice 7 per ADR-0031 D10"** → PASS.
- **"New ADRs — out; pure execution per ADR-0031"** → PASS (specific + reason).

## Edges

- **part_of:** [[entities/subagents/prd-critic]]
- **related_to:** [[concepts/rules/pc-prd-completeness]]
- **related_to:** [[concepts/rules/sc-no-non-goals]]
- **related_to:** [[concepts/glossary/yagni]]
