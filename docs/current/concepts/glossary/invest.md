---
title: INVEST — Bill Wake's six-property check for a well-formed user story
summary: Bill Wake's six-property check for a well-formed user story (Independent, Negotiable, Valuable, Estimable, Small, Testable) used here as the shape criterion for a slice.
tags: [glossary, slicing, external-standard, methodology]
type: concept
last_updated: 2026-05-26
sources:
  - decisions/0003-autonomous-pipeline-with-critics.md
  - CLAUDE.md
  - https://xp123.com/articles/invest-in-good-stories-and-smart-tasks/
---

# INVEST

**INVEST** is Bill Wake's six-property mnemonic for a well-formed user story — **I**ndependent, **N**egotiable, **V**aluable, **E**stimable, **S**mall, **T**estable. This project adopts INVEST as the shape criterion for a slice per [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D1: slicer and slicer-critic check candidate decompositions against the six properties.

**Edges**

- **related-to:** [[concepts/glossary/slice]]
- **related-to:** [[concepts/glossary/spidr]]

## What

The six properties:

- **Independent** — the slice can ship without waiting on other slices; ordering between slices is a convenience, not a constraint.
- **Negotiable** — the slice's scope can be revised mid-PRD without breaking the PRD's goal; rigid step-by-step plans fail this property.
- **Valuable** — the slice ships value to the consumer (end-user OR a downstream pipeline stage); pure-infrastructure slices fail this property.
- **Estimable** — the implementer can predict the slice's size and complexity with sufficient confidence to commit; high-uncertainty slices become SPIDR-S spike slices first.
- **Small** — the slice fits in one PR within the R-LOC 300-LoC runtime-artifact cap.
- **Testable** — the slice has mechanically verifiable acceptance criteria; aspirational success criteria fail this property.

## Why

INVEST is the shape contract for the slice tier. Without it, "slice" degrades to "arbitrary subdivision". The properties together ensure that (a) the pipeline can run slices in parallel where possible (Independent), (b) the reviewer can mechanically litigate scope (Testable + Small), (c) the slice has business meaning rather than being a horizontal-layer fragment (Valuable), and (d) implementers can commit to estimated work (Estimable).

INVEST is paired with the **hamburger method** (vertical not horizontal) and **SPIDR** (split fallbacks when a slice is too large). The three together form the project's slicing methodology, with the canonical overview living in [`CLAUDE.md`](../../../CLAUDE.md) "Slicing logic" and the operational application in [`.claude/agents/slicer.md`](../../../.claude/agents/slicer.md) + [`.claude/agents/slicer-critic.md`](../../../.claude/agents/slicer-critic.md).

The `slicer-critic` rubric's first criteria check the INVEST properties on each candidate slice; failing any property triggers a BLOCK with a specific revision instruction (e.g., "slice 2's Independent fails — it depends on slice 3's file rename; reorder or merge").

## Examples from this project

- **Slice #246 (this slice)** — Independent (no sibling slices in flight, verified per slice body); Negotiable (the 5 chosen terms could have been a different 5); Valuable (downstream stages consume the atomic notes); Estimable (~5 small files + minor adjustments); Small (well under R-LOC); Testable (acceptance criteria all greppable).
- **PRD #3 slice 1** — failed Negotiable when first drafted (too rigid step-by-step); slicer-critic blocked, slicer re-cut to a walking-skeleton shape.

## Anti-patterns

- **Horizontal-layer slice** — fails Valuable (ships no end-to-end value); hamburger-method criterion catches it.
- **Speculative slice** — fails Estimable (too many unknowns); split into a SPIDR-S spike slice first.
- **Aspirational acceptance criteria** — fails Testable; reviewer cannot litigate scope.

## Scope

(b) external standard adopted

## Authority

[ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D1

## References

- [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D1 — INVEST as the slice shape criterion.
- [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D2 — slicing methodology overview (hamburger + SPIDR + INVEST).
- Bill Wake, "INVEST in Good Stories and SMART Tasks": https://xp123.com/articles/invest-in-good-stories-and-smart-tasks/
- [`.claude/agents/slicer.md`](../../../.claude/agents/slicer.md) — operational application of INVEST during decomposition.
- [`.claude/agents/slicer-critic.md`](../../../.claude/agents/slicer-critic.md) — rubric checks INVEST properties per candidate.
