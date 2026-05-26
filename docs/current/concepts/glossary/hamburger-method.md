---
title: hamburger method — vertical-slicing technique
summary: A vertical-slicing technique (Gojko Adzic, 2012) that decomposes a feature into thin end-to-end slices cutting through every layer rather than building one horizontal layer at a time.
tags: [glossary, slicing, external-standard, methodology]
type: concept
last_updated: 2026-05-26
sources:
  - https://gojko.net/2012/05/01/the-hamburger-method/
  - decisions/0005-output-shape-and-slicing-methodology.md
  - CLAUDE.md
---

# hamburger method

The **hamburger method** is Gojko Adzic's vertical-slicing technique (originally written 2012) that decomposes a feature into thin end-to-end slices, each cutting through every layer of the system — schema, logic, UI, test — rather than building one horizontal layer at a time. This project adopts it as the slice-shape contract: **slice 1 of any PRD must satisfy the hamburger property**, and horizontal layering is rejected at slicing time per [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D2.

**Edges**

- **related-to:** [[concepts/glossary/spidr]]
- **related-to:** [[patterns/walking-skeleton]]
- **related-to:** [[concepts/glossary/slice]]

## What

Gojko's original mental model: think of a feature as a hamburger (bun / lettuce / patty / cheese / sauce / bun). The wrong way to ship it is layer-by-layer (all the buns first, then all the lettuce). The right way is to ship a *complete but minimal* hamburger first (one of each layer, even if thin), then iterate by adding more lettuce or upgrading the patty.

Operationalized for this project:

- A **vertical slice** cuts through every layer the feature touches, even if crudely.
- The first slice of any multi-slice PRD must be vertical — schema, logic, integration, and at least one consumer must all see the change.
- Subsequent slices can specialize (deepen one layer, add edge-case coverage) but the walking-skeleton end-to-end path stays alive throughout.

The [`slicer-critic`](../../../.claude/agents/slicer-critic.md) rubric's first criterion checks the hamburger property on the candidate decomposition. Horizontal-layer slice 1s ("build all the schemas; the UI comes in slice 4") get BLOCKed with a specific rewrite instruction.

The hamburger method is paired in this project with **INVEST** (the shape contract for slices) and **SPIDR** (split fallbacks when a slice approaches the R-LOC cap). The three together form the slicing methodology — canonical home in [CLAUDE.md](../../../CLAUDE.md) "Slicing logic" and operational application in [`.claude/agents/slicer.md`](../../../.claude/agents/slicer.md).

## Why

Horizontal layering is the dominant anti-pattern in green-field projects because it feels efficient — building each layer fully before moving to the next minimizes context-switching cost per layer. The hamburger method exists because that local efficiency creates **integration risk that compounds**: when the layers finally meet, mismatches surface late and forced rework is expensive. By slicing vertically, integration risk surfaces at slice-1 time when fixing costs one slice, not at PRD-completion time when fixing costs the PRD.

For an autonomous agent pipeline specifically, the hamburger method has a second benefit: each slice is a complete dogfood-able artifact. Reviewer can litigate scope and value at slice-1 time because slice 1 actually does something end-to-end. Horizontal slice-1s ("ship just the schema") give reviewer nothing to judge against the PRD's success criteria.

## Examples from this project

- **PRD #3 slice 1 (`/ship` skeleton)** — the canonical hamburger-method example in this codebase; one tiny end-to-end shipping run rather than "all the subagents first".
- **PRD #245 slice 1** — atomic-note schema validation across 5 terms PLUS CLAUDE.md INDEX scaffold PLUS path-adjuster body updates — every layer of the migration touched in slice 1.
- **This very slice (#247)** — 9 new atomic notes + CLAUDE.md INDEX rows + dogfood verification. Vertical, not "all the notes first then the INDEX later".

## Anti-patterns

- **Horizontal slice 1** — "ship the schema; consumers come in slice 2". Fails the hamburger property; slicer-critic BLOCKs.
- **Layer-perfection-first** — building the world's most polished one layer before slice 2 exists. Defeats the integration-risk-surfacing benefit.
- **"Foundation slice"** — code that ships only types/interfaces with no consumer in the same slice. The reviewer cannot judge value; the slice fails INVEST's Valuable property.

## Scope

(b) external standard adopted

## Authority

Gojko Adzic, "The Hamburger Method": https://gojko.net/2012/05/01/the-hamburger-method/

## References

- Gojko Adzic, "The Hamburger Method" (2012): https://gojko.net/2012/05/01/the-hamburger-method/
- [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D2 — adoption + paired-with-INVEST-and-SPIDR pattern.
- [CLAUDE.md](../../../CLAUDE.md) "Slicing logic — what makes a good slice" — methodology overview.
- [`.claude/agents/slicer.md`](../../../.claude/agents/slicer.md) — operational application.
- [`.claude/agents/slicer-critic.md`](../../../.claude/agents/slicer-critic.md) — rubric checks hamburger property on candidate decompositions.
- [[concepts/glossary/spidr]] — split-fallback companion when slices grow past R-LOC.
- [[patterns/walking-skeleton]] — the closely-related pattern this project ALSO adopts.
