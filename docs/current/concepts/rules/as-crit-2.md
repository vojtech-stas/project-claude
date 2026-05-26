---
title: AS-CRIT-2 — audit-subagents critic check, adversarial mindset block present
summary: The audit-subagents critic-only mechanical check that every critic body contains either "paranoid" or "Adversarial mindset" literal — the ADR-0009 D4 mindset clause that primes critics to scrutinize rather than rubber-stamp; backlog-critic.md is allowlisted because ADR-0009 D4 deliberately excluded it.
tags: [rule, audit-subagents-rubric]
type: concept
last_updated: 2026-05-27
sources:
  - .claude/skills/audit-subagents/SKILL.md CRIT-2
  - decisions/0011-subagent-quality-framework.md D4
  - decisions/0009-discipline-tightening.md D4
---

# AS-CRIT-2

**AS-CRIT-2** is the [`/audit-subagents`](../../entities/skills/audit-subagents.md) rubric check (scope: `critic`) that enforces every critic body contains either the literal string **"paranoid"** OR **"Adversarial mindset"**. Per [ADR-0011](../../../decisions/0011-subagent-quality-framework.md) D4 + [ADR-0009](../../../decisions/0009-discipline-tightening.md) D4, this is the canonical **adversarial mindset block** — prose that explicitly primes the critic to scrutinize the input rather than rubber-stamp it.

## What

The check fires on every critic file. Mechanics:

- Run the disjunctive grep: `grep -cE "(paranoid|Adversarial mindset)" <file>`.
- If the count is ≥ 1 → **PASS** (mindset block present in at least one of the two canonical forms).
- If the count is 0 → **FAIL** (mindset clause missing).

The `excludes:` field on this check allowlists `backlog-critic.md`. Rationale: [ADR-0009](../../../decisions/0009-discipline-tightening.md) D4 deliberately excluded `backlog-critic` from the mindset rollout because its single-fire autopilot semantics (per [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D2) differ from the ≤3-round critics that received the mindset block. Codifying the exception here matches the [ADR-0009](../../../decisions/0009-discipline-tightening.md) D4 table; flagging `backlog-critic.md` as a CRIT-2 FAIL would contradict the explicit ADR decision.

## Why

A critic's job is **adversarial audit** — by default, the reading-mode for an incoming artifact should be "find what's wrong", not "find what's right". The mindset block is the explicit prompt that flips the critic into scrutiny mode. Without it, critics drift toward leniency: they read the artifact as if checking comprehension rather than checking defects.

[ADR-0009](../../../decisions/0009-discipline-tightening.md) D4 introduces two canonical forms — "paranoid" (more visceral; used in the implementer subagent and several critics) and "Adversarial mindset" (more formal; used as a section heading in several critics). Either suffices; the grep accepts both. The deliberate `backlog-critic.md` exclusion exists because that critic fires once per item, has no revision loop, and serves a different role (gating quality of captured-tier promotions) than the adversarial-audit critics.

## How to check

For each critic file (excluding `backlog-critic.md`):

1. Run `grep -cE "(paranoid|Adversarial mindset)" <file>`.
2. If ≥ 1 → PASS.
3. If 0 → FAIL.
4. For `backlog-critic.md` → render `N/A (excluded per rubric)`; omit from FAIL enumeration.
5. For generators → render `—`.

## Examples

- **`prd-critic.md` with `## Adversarial mindset` section** → PASS.
- **`reviewer.md` describing itself as "paranoid critic"** → PASS.
- **A critic file with no mindset clause** → FAIL.
- **`backlog-critic.md` without mindset clause** → `N/A (excluded per rubric)`.
- **`slicer.md` (generator)** → `—`.

## Edges

- **part_of:** [[entities/skills/audit-subagents]]
- **related_to:** [[concepts/rules/as-crit-1]]
- **related_to:** [[entities/subagents/backlog-critic]]
