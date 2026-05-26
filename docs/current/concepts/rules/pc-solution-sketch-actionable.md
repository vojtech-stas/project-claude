---
title: PC-SOLUTION-SKETCH-ACTIONABLE — prd-critic criterion 4, solution sketch enables slicer decomposition
summary: The prd-critic rule that the Solution sketch enumerates discrete work-units the slicer can decompose into vertical slices, stays within the PRD's stated feature, and implies a walking-skeleton slice-1 cut; vague prose ("we'll figure out the architecture") or horizontal-layer sketches FAIL the rule.
tags: [rule, prd-critic-rubric]
type: concept
last_updated: 2026-05-26
sources:
  - .claude/agents/prd-critic.md criterion 8 (scope discipline)
  - .claude/agents/prd-critic.md criterion 9 (walking-skeleton coherence)
  - decisions/0003-autonomous-pipeline-with-critics.md D1
---

# PC-SOLUTION-SKETCH-ACTIONABLE

**PC-SOLUTION-SKETCH-ACTIONABLE** is the prd-critic rubric criterion that enforces the Solution sketch (§5) is actionable by the [`slicer`](../../../.claude/agents/slicer.md): it enumerates discrete work-units, stays within the PRD's stated feature (no scope expansion), and implies a walking-skeleton-first decomposition. Vague prose ("we'll figure out the architecture in slice 1"), scope-expanded sketches ("while we're in there, also fix Y"), or horizontal-layer sketches ("slice 1: build all the modules; slice 2: wire them up") FAIL the rule.

This rule consolidates two upstream prd-critic concerns — scope discipline (no expansion past the stated feature) and walking-skeleton coherence (slice 1 is a vertical cut, not a horizontal layer) — because both fail in the Solution sketch and the fix shape (rewrite the sketch) is the same.

## What

The rule fires on every draft PRD's §5 Solution sketch. Mechanics:

- **Enumerable work-units:** the sketch enumerates discrete deliverables (entity notes, subagent thinnings, atomic notes, slices) that the slicer can map 1:1 or N:1 to slices. Pure prose without enumerable shape → FAIL.
- **Scope discipline:** every work-unit advances the PRD's stated feature (from §1 Problem + §2 Goal). Any work-unit that doesn't is **scope expansion** — call it out and FAIL.
- **Walking-skeleton coherence:** slice-1 guidance (or the implied first cut) is a thin end-to-end vertical, not a horizontal layer. "Slice 1 ships the schema; slice 2 wires consumers" → FAIL (horizontal). "Slice 1 ships one entity end-to-end including reader extension + cascade-docs + ADR + dogfood" → PASS (walking-skeleton).

## Why

This rule exists because **the Solution sketch is the slicer's spec contract**. A sketch the slicer cannot decompose forces either (a) the slicer to invent structure (introducing variance the prd-critic was meant to gate against) or (b) round-1 slicer-critic BLOCK on SC-INVEST/SC-WALKING-SKELETON. Both cost a round-trip.

Scope discipline at PRD time is the cheapest place to catch the "while we're in there" anti-pattern. Once a work-unit becomes a slice, removing it costs slice-issue cleanup; once it becomes a PR, removing it costs reviewer BLOCK + implementer rework. Catch at the sketch.

Walking-skeleton coherence is the structural commitment that distinguishes vertical-slicing PRDs from horizontal-layering ones (per CLAUDE.md rule #2). Catching horizontal-layering at the sketch costs a sketch rewrite; catching at slicing-time costs a decomposition regenerate.

## How to check

For each draft PRD:

1. Count work-units in the sketch (entity notes / thinnings / files / slices enumerated).
2. For each work-unit, verify it traces to §1 Problem or §2 Goal. If not → scope expansion → FAIL.
3. Identify the implied slice-1 cut (either explicit "slice 1:" guidance or the first work-unit listed).
4. Test slice-1 for verticality: does it cut every layer the PRD names (schema + logic + reader + consumer + cascade-docs + dogfood) — even if crudely?
5. If slice-1 builds one layer only → FAIL (horizontal layering).
6. If sketch is pure prose without enumerable work-units → FAIL.

## Examples

- **Sketch enumerates 7 subagent thinnings + 1 cluster split; slice-1 implied is "prd-critic dogfood (KB + entity + thin) — slice 1 of 10"** → PASS (work-units enumerable; slice-1 is vertical dogfood).
- **Sketch says "we'll figure out architecture in slice 1"** → FAIL (no enumeration; slicer cannot decompose).
- **Sketch enumerates 5 work-units + 1 "while we're in there, refactor X"** → FAIL on the 6th (scope expansion).
- **Sketch says "slice 1: build all the rule notes; slice 2: thin each subagent body; slice 3: wire entity edges"** → FAIL (horizontal layering; slice 1 builds no end-to-end value).

## Edges

- **part_of:** [[entities/subagents/prd-critic]]
- **related_to:** [[concepts/rules/pc-appetite-bounded]]
- **related_to:** [[concepts/rules/sc-walking-skeleton]]
- **related_to:** [[concepts/rules/sc-invest]]
- **related_to:** [[concepts/glossary/walking-skeleton-glossary]]
- **related_to:** [[concepts/glossary/hamburger-method]]
