---
title: SC-WALKING-SKELETON — slicer-critic criterion 2, slice 1 must cut every layer end-to-end
summary: The slicer-critic rule that exactly one slice in the decomposition is tagged walking-skeleton, that slice is slice 1, and it exercises every pipeline stage end-to-end (even if crudely); horizontal layering FAILs.
tags: [rule, slicer-critic-rubric]
type: concept
last_updated: 2026-05-26
sources:
  - .claude/agents/slicer-critic.md criterion 2
  - CLAUDE.md cross-cutting rule #2
---

# SC-WALKING-SKELETON

**SC-WALKING-SKELETON** is criterion 2 in the [`slicer-critic`](../../../.claude/agents/slicer-critic.md) rubric. It enforces walking-skeleton-first decomposition: exactly one slice is tagged `walking-skeleton: yes`, that slice is **slice 1**, and slice 1 exercises every pipeline stage end-to-end — even if crudely, via pass-through stubs. The opposite (slice 1 builds one layer thoroughly while later slices wire the rest) is **horizontal layering** and is banned by CLAUDE.md cross-cutting rule #2.

## What

Mechanics:

- Slicer-critic reads each slice's tags and ordering.
- Verify exactly one slice carries `walking-skeleton: yes`.
- Verify that slice is the first in ordering.
- Verify slice 1's "What ships" cuts every layer the PRD names (schema + logic + reader + consumer + cascade-docs + ADR + dogfood if the PRD is structural; subagent + orchestrator wire + dispatch if the PRD adds a subagent; etc.).
- If slice 1 builds only one layer (e.g., "ship the schema; consumers wire later") → FAIL.

The check is for **vertical** vs **horizontal** cuts (per the hamburger method). The walking-skeleton is *thin* (minimal per-layer functionality) but *complete* (every layer present).

## Why

This rule exists because **integration risk surfaces only when layers connect**. A horizontal decomposition discovers at slice N that slice 1's output shape doesn't match slice N's input — at which point fixing the upstream costs an entire slice's rework AND breaks any in-flight slices that depended on the wrong shape. A walking-skeleton catches the impedance mismatch in slice 1, when fixing is cheap.

The rule is also a YAGNI forcing function: building each primitive perfectly first means building primitives that downstream stages won't actually use the way you imagined. Constraining slice 1 to "only what end-to-end needs" rejects speculative work by construction.

Slice 1 being the walking-skeleton (not just *some* slice) matters because the project's pipeline assumes slice 1's PR is the first feedback signal. A walking-skeleton at slice 3 leaves the project blind for two slices.

## How to check

For each candidate decomposition:

1. Grep slice tags for `walking-skeleton: yes` — exactly one match required.
2. Verify that match is slice 1.
3. Read slice 1's "What ships" — does it enumerate every layer the PRD names? If only one layer present → FAIL.
4. Cross-check against PRD §5 solution sketch: which layers does the PRD imply exist? Does slice 1 touch each?

## Examples

- **PRD #242 (knowledge architecture v2) slice 1** — cuts directory structure + populated example per slot + reader extension + cascade-docs + ADR + dogfood in ONE PR → PASS (canonical example documented in [[patterns/walking-skeleton]]).
- **Decomposition where slice 1 ships only "create directory structure"** → FAIL (horizontal layering; no consumer wired).
- **Decomposition where slice 2 carries `walking-skeleton: yes`** → FAIL (skeleton must be slice 1; ordering violation).

## Edges

- **part_of:** [[entities/subagents/slicer-critic]]
- **related_to:** [[concepts/glossary/walking-skeleton-glossary]]
- **related_to:** [[patterns/walking-skeleton]]
- **related_to:** [[concepts/glossary/hamburger-method]]
- **related_to:** [[concepts/rules/sc-invest]]
