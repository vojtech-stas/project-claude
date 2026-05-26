---
title: BC-ACTIONABLE — backlog-critic criterion 1, item describes a concrete action against a named artifact
summary: The backlog-critic rule that a captured item must describe a doable action (verb) against an identifiable artifact (file path, subagent name, skill name, ADR D-ID, label); pure observations or vague targets ("the system", "the codebase") FAIL.
tags: [rule, backlog-critic-rubric]
type: concept
last_updated: 2026-05-26
sources:
  - .claude/agents/backlog-critic.md criterion 1 (actionable)
  - decisions/0008-workflow-autolog-bootstrap-and-naming.md D4
---

# BC-ACTIONABLE

**BC-ACTIONABLE** is the backlog-critic rubric criterion that enforces a `captured`-labeled item describes something *doable* — an action verb plus an identifiable target artifact — rather than a feeling, observation, or vague gesture. A future implementer (or `/grill-me` Q1) must be able to start work without a separate "what does this mean" conversation. Comment-only captures and unnameable targets FAIL the rule.

## What

The rule fires on every fresh `captured`-labeled issue. Mechanics:

- Look for an **action verb** (add, fix, refactor, document, replace, rename, split, extract, thin, audit, etc.) — explicit or strongly implied.
- Look for an **identifiable artifact** the verb targets: a file path (`.claude/agents/foo.md`), a subagent name, a skill name, an ADR D-ID, a label, a rule ID. Anything `Read`-able or `gh issue view`-able.
- A body that names only the symptom ("the prompts feel inconsistent"; "this is confusing"; "we should improve testing") with no action verb or artifact → FAIL.
- A body with an action verb but a vague target ("fix the system", "improve the codebase", "clean up the agents") → FAIL — the slicer cannot localize the work.

## Why

This rule exists because **the captured tier is zero-friction by design** (per [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D2's asymmetric-default), which means agents will write items at the moment of irritation, often as a half-formed complaint. The backlog tier is the curated forward queue from which `/grill-me` picks PRDs — if the backlog contains comment-only items, every `/grill-me` invocation pays the cost of re-translating them into action shapes. Catching at promotion time pushes the translation back to the capturing agent (via BLOCK) where the originating context is still loaded.

The "unnameable target" sub-check is the more adversarial half: many captures pass the verb test but name "the system" or "the codebase". These items pretend to be actionable but cannot be assigned to a single PRD scope.

## How to check

For each captured-tier item:

1. Read the body. Identify (a) the action verb (explicit or implied), (b) the target artifact.
2. If no action verb is present and the body is observation-only → FAIL with `"actionable: body is observation-only; rewrite as a concrete action against a named artifact"`.
3. If an action verb is present but the target is vague ("the system", "the codebase", "the agents", "the prompts") → FAIL with `"actionable: target is vague; name the specific file path, subagent, skill, or ADR"`.
4. If both present and concrete → PASS.

## Examples

- **"Fix the reviewer thing — it's blocking too aggressively"** → FAIL (no specific artifact; "the reviewer thing" is vague).
- **"Rename `R-CLOSES` rule heading in `.claude/agents/reviewer.md` for consistency with `R-LOC`"** → PASS (verb + file path + specific rule).
- **"The prompts feel inconsistent"** → FAIL (observation-only; no verb, no artifact).
- **"Split `.claude/agents/qa-tester.md` rubric section into atomic rule notes per ADR-0031 D12"** → PASS (verb + file + ADR-D-ID anchor).
- **"Improve testing"** → FAIL (verb present but target vague).

## Edges

- **part_of:** [[entities/subagents/backlog-critic]]
- **related_to:** [[concepts/rules/bc-scoped]]
- **related_to:** [[concepts/rules/bc-clear]]
- **related_to:** [[concepts/glossary/captured]]
