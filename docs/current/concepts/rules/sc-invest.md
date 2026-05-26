---
title: SC-INVEST — slicer-critic criterion 1, every slice satisfies all six INVEST letters
summary: The slicer-critic rule that every slice in a candidate decomposition must satisfy all six INVEST letters (Independent, Negotiable, Valuable end-to-end, Estimable, Small, Testable); a single FAIL anywhere fails the decomposition.
tags: [rule, slicer-critic-rubric]
type: concept
last_updated: 2026-05-26
sources:
  - .claude/agents/slicer-critic.md criterion 1
  - decisions/0003-autonomous-pipeline-with-critics.md D1
---

# SC-INVEST

**SC-INVEST** is criterion 1 in the [`slicer-critic`](../../../.claude/agents/slicer-critic.md) rubric. It enforces that every slice in a candidate decomposition satisfies all six INVEST letters: **I**ndependent, **N**egotiable, **V**aluable end-to-end, **E**stimable, **S**mall enough to fit the LoC cap, **T**estable. A single FAIL on any letter for any slice causes the entire decomposition to FAIL this criterion.

## What

The rule fires on every candidate decomposition. Mechanics:

- For each slice in the decomposition, slicer-critic checks all six INVEST letters.
- A FAIL on any letter for any slice → the whole decomposition FAILs criterion 1 (not just that slice).

The letters as applied in this project:

- **Independent** — slices have no circular or implicit dependencies; ordering is honest.
- **Negotiable** — the slice body leaves room for implementer judgment; not over-prescribed.
- **Valuable end-to-end** — slice ships *something* that exercises a real path, not pure scaffolding (the V is what walking-skeleton rule SC-WALKING-SKELETON enforces in concert with this one).
- **Estimable** — the slice has a defensible LoC estimate; if the implementer can't predict size within ~50%, it isn't estimable.
- **Small** — fits under R-LOC (≤300 runtime-artifact LoC); if a slice estimate is ≥250 LoC the slicer-critic typically WARNs and asks for a SPIDR split.
- **Testable** — acceptance criteria are mechanically verifiable; "looks good" is not testable.

## Why

INVEST exists because **slice quality is the upstream determinant of pipeline success**. A non-Independent slice creates rebase conflicts; a non-Valuable slice ships scaffolding that future slices have to rework; a non-Testable slice means the reviewer cannot mechanically gate it. The slicer-critic catches these at slicing time when the cost is a revision loop — catching them at reviewer time costs a closed PR and a respin.

Putting all six letters on one criterion (rather than splitting into six) keeps the rubric compact and forces the critic to consider the slice as a whole rather than score each letter in isolation. The "any FAIL → criterion FAILs" rule is asymmetric on purpose: false-positive APPROVE is more expensive than false-negative BLOCK.

## How to check

For each slice in the candidate decomposition:

1. Independent — does any other slice's `Depends on:` row name this slice without genuine prerequisite? (If so, the dependency is arbitrary serialization; FAIL.)
2. Negotiable — does the slice body over-specify the implementation (line-by-line code), removing implementer judgment? FAIL if yes.
3. Valuable — does the slice exercise a real path end-to-end, or only build infrastructure for future slices? FAIL if pure scaffolding.
4. Estimable — is the LoC estimate present and defensible? FAIL if missing or wildly off.
5. Small — is the estimate ≤300 runtime-artifact LoC? FAIL if over.
6. Testable — are acceptance criteria mechanically checkable? FAIL if subjective-only.

## Examples

- **Slice ships an empty schema file** → V FAIL (no end-to-end exercise) → criterion 1 FAIL.
- **Three slices each `Depends on:` the others in a cycle** → I FAIL → criterion 1 FAIL → typically also criterion 6 FAIL.
- **Slice estimate is "around 500 LoC"** → S FAIL (over cap) AND E borderline → criterion 1 FAIL; require SPIDR split.

## Edges

- **part_of:** [[entities/subagents/slicer-critic]]
- **related_to:** [[concepts/glossary/invest]]
- **related_to:** [[concepts/rules/sc-walking-skeleton]]
- **related_to:** [[concepts/rules/sc-slice-count-loc]]
- **related_to:** [[concepts/rules/r-loc]]
