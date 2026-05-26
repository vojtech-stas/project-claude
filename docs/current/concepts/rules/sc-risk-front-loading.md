---
title: SC-RISK-FRONT-LOADING — slicer-critic criterion 8, biggest risk lands in slice 1 or 2
summary: The slicer-critic rule that the biggest risk identified across slices should land in slice 1 or 2; a riskiest mechanic buried at the end earns a WARN (not FAIL — defensible in some PRDs).
tags: [rule, slicer-critic-rubric]
type: concept
last_updated: 2026-05-26
sources:
  - .claude/agents/slicer-critic.md criterion 8
  - CLAUDE.md cross-cutting rule #2
---

# SC-RISK-FRONT-LOADING

**SC-RISK-FRONT-LOADING** is criterion 8 in the [`slicer-critic`](../../../.claude/agents/slicer-critic.md) rubric. It enforces that the biggest risk identified across the decomposition's slices lands in slice 1 or slice 2. If the riskiest mechanic is buried at the end (e.g., slice 5 of 6), the criterion earns a **WARN** (not FAIL — defensible in some PRDs, but should be flagged for human/agent judgment).

## What

Mechanics:

- Read each slice's risk indicators: high LoC estimate, novel mechanism, unknown integration point, "first use of X" markers.
- Rank slices by risk (qualitative — slicer-critic uses judgment).
- Check whether the top-risk slice is positioned at slice 1 or 2.
- If the top-risk slice is at position 3+ → WARN with explicit naming of the riskier mechanic and where it should ideally land.

Risk indicators in this project:

- Slice that wires a new subagent for the first time.
- Slice that introduces a new ADR (decision uncertainty).
- Slice that touches the autonomous pipeline (`/ship`, `implementer`, `reviewer`).
- Slice with a high LoC estimate relative to siblings.
- Slice that exercises an unproven cross-PR mechanism (e.g., parallel sibling-PR rebase).

## Why

This rule exists because **discovering a risk late in a multi-slice PRD wastes the slices already shipped**. If slice 5 turns out to be infeasible as decomposed, slices 1-4 may need to be reworked or have their assumptions invalidated — and they're already merged. Front-loading risk into slice 1 or 2 means: if the risky mechanism doesn't pan out, only one or two slices need rework before the PRD pivots.

This complements [SC-WALKING-SKELETON](sc-walking-skeleton.md) (criterion 2) — the skeleton-first rule says slice 1 must cut every layer; the risk-front-loading rule says slice 1 (or 2) should also carry the biggest unknown. Together they ensure the project's earliest signal is also its most informative.

WARN-not-FAIL is intentional: occasionally a PRD's structure genuinely requires building foundations before the risky integration (e.g., "slice 1 creates the schema; slice 2 is the risky migration"). The WARN flags the asymmetry for explicit acknowledgment rather than auto-blocking.

## How to check

For each candidate decomposition:

1. Read each slice's "What ships" and Notes; identify risk markers.
2. Qualitatively rank slices by risk (1 = riskiest).
3. Check position of rank-1 slice in ordering.
4. If at position 3+, WARN: "riskiest mechanic (slice X) buried at position Y; consider reordering or splitting".

## Examples

- **PRD ships a new subagent in slice 1 (walking-skeleton) and refines its prompt in slices 2-3** → PASS (risk front-loaded).
- **PRD does 3 slices of doc setup then introduces the new subagent at slice 4** → WARN (subagent integration is the risk; should be earlier).
- **PRD has uniformly low-risk slices (pure doc migration)** → criterion not applicable; PASS.

## Edges

- **part_of:** [[entities/subagents/slicer-critic]]
- **related_to:** [[concepts/rules/sc-walking-skeleton]]
- **related_to:** [[concepts/rules/sc-dep-ordering]]
- **related_to:** [[patterns/walking-skeleton]]
