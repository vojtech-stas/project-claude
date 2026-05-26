---
title: SC-SPIDR-SPLITABILITY — slicer-critic criterion 3, risky/near-cap slices need a plausible SPIDR fallback
summary: The slicer-critic rule that any slice flagged as risky or near the LoC cap must have a plausible SPIDR split fallback (Spike, Path, Interface, Data, Rules); a near-cap slice with no plausible split fallback earns a WARN.
tags: [rule, slicer-critic-rubric]
type: concept
last_updated: 2026-05-26
sources:
  - .claude/agents/slicer-critic.md criterion 3
  - decisions/0005-output-shape-and-slicing-methodology.md D2
---

# SC-SPIDR-SPLITABILITY

**SC-SPIDR-SPLITABILITY** is criterion 3 in the [`slicer-critic`](../../../.claude/agents/slicer-critic.md) rubric. For any slice flagged as risky or near the [R-LOC](r-loc.md) cap, the slicer-critic asks: *can this be SPIDR-split (**S**pike, **P**ath, **I**nterface, **D**ata, **R**ules) if it overruns at implementation time?* A near-cap slice with no plausible split fallback earns a **WARN** (not FAIL — the split is operational defense, not gate).

## What

Mechanics:

- Identify slices with LoC estimate ≥ ~250 (within 50 of cap) OR explicitly tagged as risky.
- For each such slice, check whether the slice body names a SPIDR fallback in its "What ships" or "Notes for implementer" section.
- If a plausible SPIDR fallback is named (e.g., "if cap pressure, split into Interface=skill vs Interface=subagent halves") → PASS.
- If no fallback is named AND the slice is near cap → WARN.
- A WARN does not block; it surfaces an operational risk for human/agent judgment.

SPIDR letters as applicable here:

- **S**pike — research/learning slice carved off first.
- **P**ath — different user paths (rarely fits this agent-workflow domain).
- **I**nterface — split by interface/CLI/API surface.
- **D**ata — different data variations (rarely fits).
- **R**ules — different business rules.

Per [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D2, S/I/R are most applicable in this project; P/D rarely fit.

## Why

This rule exists because **slices that approach the cap during planning frequently breach it during implementation**. Implementation discovery (a missed dependency, a more complex API than planned, an unexpected cascade-doc) commonly adds 50-100 LoC. A slice estimated at 290 with no split plan becomes a 350-LoC PR that the [reviewer](../../../.claude/agents/reviewer.md) BLOCKs under [R-LOC](r-loc.md), forcing a mid-PR pivot under time pressure.

Pre-naming the split fallback at slicing time gives the implementer a known escape hatch: when the cap pressure hits, they execute the named SPIDR split rather than improvising one. The cost of naming the fallback up-front is one sentence in the slice body; the cost of improvising mid-PR is hours of rework.

WARN-not-FAIL is intentional: not every near-cap slice needs a split (sometimes the estimate is conservative). The WARN forces explicit acknowledgment without hard-blocking.

## How to check

For each slice with LoC estimate ≥ 250 OR risk flag:

1. Grep the slice body for SPIDR keywords (`Spike`, `Interface split`, `Rules split`, etc.).
2. If absent, check if the slice body names ANY plausible split direction (even informal).
3. If no plan present → WARN with the slice number and recommended split direction.

## Examples

- **Slice estimated 280 LoC with "Notes: if overruns, interface-split into orchestrator-half vs critic-half"** → PASS (SPIDR-I fallback named).
- **Slice estimated 290 LoC with no fallback** → WARN: recommend pre-naming SPIDR-I or SPIDR-R fallback.
- **Slice estimated 120 LoC (well under cap)** → criterion not applicable; PASS by default.

## Edges

- **part_of:** [[entities/subagents/slicer-critic]]
- **related_to:** [[concepts/glossary/spidr]]
- **related_to:** [[concepts/rules/r-loc]]
- **related_to:** [[concepts/rules/sc-slice-count-loc]]
- **related_to:** [[concepts/rules/sc-invest]]
