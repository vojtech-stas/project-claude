---
title: SC-NO-NON-GOALS — slicer-critic criterion 4, no slice may chase a PRD §3 non-goal
summary: The slicer-critic rule that every slice traces to a PRD §2 success criterion and none chases a §3 non-goal; any violation FAILs the decomposition.
tags: [rule, slicer-critic-rubric]
type: concept
last_updated: 2026-05-26
sources:
  - .claude/agents/slicer-critic.md criterion 4
  - .claude/skills/to-prd/SKILL.md
---

# SC-NO-NON-GOALS

**SC-NO-NON-GOALS** is criterion 4 in the [`slicer-critic`](../../../.claude/agents/slicer-critic.md) rubric. It enforces that every slice in the decomposition traces to one of the PRD's §2 success criteria, and that no slice's "What ships" chases a §3 non-goal. Any violation is a hard **FAIL** for the decomposition.

## What

Mechanics:

- Read PRD §3 (Non-goals / Out of scope) — extract the bullet list of explicit non-goals.
- For each slice in the decomposition, read "What ships" and "Acceptance criteria".
- For each item shipped by a slice, check it does not appear in §3 non-goals (literally or semantically).
- Any match → FAIL.

The criterion catches two patterns:

1. **Explicit overlap** — slice ships exactly what §3 says it won't (rare; usually caught by prd-critic).
2. **Semantic creep** — slice ships an adjacent capability that effectively implements a non-goal under a different name (more common; this is what the critic must catch).

## Why

This rule exists because **§3 non-goals are the PRD's commitment to bounded scope**. When PRD authoring decides "we're not building X in this PRD," that decision is load-bearing: it sets the appetite (§4), constrains the solution sketch (§5), and tells the human reader what NOT to expect. A slice that ships a §3 non-goal silently reneges on that commitment, expanding scope without ever passing back through `to-prd`/`prd-critic` re-review.

Catching this at slicing time matters because by the time a slice issue is posted, the implementer reads it as authoritative — they will build whatever it asks. Slicer-critic is the last gate that compares slice intentions back against the PRD's explicit refusal list.

The rule is FAIL (not WARN) because chasing a non-goal is not an edge case — it's a contract violation. The slicer must respin.

## How to check

For each candidate decomposition:

1. Extract PRD §3 bullet list into a checklist.
2. For each slice, read "What ships" + "Acceptance criteria" + first paragraph of body.
3. For each shipped item, semantic-match against §3 list: does this slice effectively implement what §3 said we wouldn't?
4. Cite the offending slice number + the §3 bullet + the diagnosis if violated.

## Examples

- **PRD §3 says "no behavioral changes to slicer-critic"; slice 2 adds a new rubric criterion** → FAIL (criterion 4 violation; behavioral change to slicer-critic).
- **PRD §3 says "no new ADR"; slice ships `decisions/0032-*.md`** → FAIL (literal violation).
- **PRD §3 says "skill thinning deferred to T5"; slice 3 thins a skill body** → FAIL (T5 scope encroachment).

## Edges

- **part_of:** [[entities/subagents/slicer-critic]]
- **related_to:** [[concepts/glossary/prd]]
- **related_to:** [[concepts/rules/sc-no-rabbit-holes]]
- **related_to:** [[concepts/rules/r-yagni]]
- **related_to:** [[concepts/rules/r-scope]]
