---
title: SC-NO-RABBIT-HOLES — slicer-critic criterion 5, no slice may chase a PRD §6 rabbit-hole
summary: The slicer-critic rule that no slice in the decomposition chases a PRD §6 rabbit-hole; any chase FAILs the decomposition.
tags: [rule, slicer-critic-rubric]
type: concept
last_updated: 2026-05-26
sources:
  - .claude/agents/slicer-critic.md criterion 5
  - .claude/skills/to-prd/SKILL.md
---

# SC-NO-RABBIT-HOLES

**SC-NO-RABBIT-HOLES** is criterion 5 in the [`slicer-critic`](../../../.claude/agents/slicer-critic.md) rubric. It enforces that no slice in the decomposition chases a PRD §6 rabbit-hole. Any chase is a hard **FAIL** for the decomposition.

## What

Mechanics:

- Read PRD §6 (Rabbit-holes & Open questions) — extract the bullet list of identified rabbit-holes.
- For each slice, check "What ships" against the rabbit-hole list.
- Any slice that materially advances into a listed rabbit-hole → FAIL.

A rabbit-hole differs from a non-goal: a non-goal is "we won't do this here"; a rabbit-hole is "this is tempting but dangerous; expect it to consume disproportionate effort if we let it in." Common rabbit-holes in this project:

- Over-perfecting a primitive before integration (violates walking-skeleton).
- Adding configurability for hypothetical future cases (violates YAGNI).
- Refactoring adjacent areas "while we're here" (boy-scout drift).
- Deep cross-PRD harmonization deferred to a future PRD.

## Why

This rule exists because **rabbit-holes are the most expensive scope drift category**. Unlike non-goal violations (which usually represent a clear contract breach), rabbit-hole chases feel productive ("I'm improving the area") while consuming the slice's LoC budget and time on work the PRD explicitly de-prioritized. The cost is double: the slice over-runs its scope AND the planned scope ships incompletely.

The rabbit-hole list in PRD §6 is the PRD-author's pre-commitment to leaving certain attractive-looking work alone. Slicer-critic enforces that pre-commitment by FAILing decompositions that re-introduce the work the PRD specifically warned about.

The FAIL severity is intentional: catching a rabbit-hole at slicing time is cheap (one revision); catching it after slice issues are posted is expensive (implementer may have already grabbed and started).

## How to check

For each candidate decomposition:

1. Extract PRD §6 bullet list of rabbit-holes.
2. For each slice, read "What ships" and Notes.
3. Semantic-match each shipped item against the rabbit-hole list.
4. Cite slice + rabbit-hole + diagnosis if matched.

Watch for paraphrasing: implementers and slicers can re-label a rabbit-hole task ("we're not chasing X — we're just laying groundwork for X"). The check resolves through behavior: does the slice materially advance the rabbit-hole, regardless of label?

## Examples

- **PRD §6 lists "deep CLAUDE.md slim" as rabbit-hole; slice 2 removes 200 lines from CLAUDE.md** → FAIL.
- **PRD §6 lists "behavioral changes to slicer-critic" as rabbit-hole; slice 3 adds a new rubric criterion** → FAIL (also criterion 4).
- **PRD §6 lists "cross-PR cascade-doc harmonization" as rabbit-hole; slice 2 only updates the cascade-docs the current PRD's slices add** → PASS (in-scope cascade only).

## Edges

- **part_of:** [[entities/subagents/slicer-critic]]
- **related_to:** [[concepts/glossary/prd]]
- **related_to:** [[concepts/rules/sc-no-non-goals]]
- **related_to:** [[concepts/rules/r-yagni]]
- **related_to:** [[concepts/rules/r-boy-scout]]
