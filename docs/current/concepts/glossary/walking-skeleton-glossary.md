---
title: walking-skeleton — smallest end-to-end version first
summary: The practice of shipping the smallest possible end-to-end version of the whole pipeline first and then iterating on the weakest stage, rather than perfecting each primitive in isolation.
tags: [glossary, methodology, external-standard, slicing]
type: concept
last_updated: 2026-05-26
sources:
  - decisions/0001-foundational-design.md
  - CLAUDE.md
  - https://wiki.c2.com/?WalkingSkeleton
---

# walking-skeleton

The **walking-skeleton** is the practice of shipping the smallest possible end-to-end version of the whole pipeline first, then iterating on the weakest stage as evidence reveals which stage IS the weakest. Per [ADR-0001](../../../decisions/0001-foundational-design.md) D10 and CLAUDE.md cross-cutting rule #2, this is the project's primary slicing-time anti-anti-pattern: horizontal layering ("build all of layer A first, then all of layer B") is rejected at slicing time in favor of vertical end-to-end-thin-first slices. This glossary entry is the *concept-level vocabulary*; the *pattern-level note* at [[patterns/walking-skeleton]] documents the practice as applied to this project's KB architecture.

**Edges**

- **defines:** [[patterns/walking-skeleton]]
- **related-to:** [[concepts/glossary/yagni]]
- **related-to:** [[concepts/glossary/hamburger-method]]

## What

The walking-skeleton is *thin* (each layer is minimally functional, often stubbed) but *complete* (every layer is touched in the first slice). The practice originates outside this project — it has been part of agile/XP folklore since at least the early 2000s — and is adopted here as one of the three foundational slicing-methodology pillars (alongside the hamburger method for slice shape and SPIDR for split fallbacks). The pattern note at `docs/current/patterns/walking-skeleton.md` (shipped in PRD #242 slice 1) documents the project's specific operationalization; this glossary entry is the vocabulary definition the rest of the KB cross-references.

The duality — one concept entry, one pattern entry, both at `walking-skeleton`-named files — is deliberate per [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D2. Concept nodes define terms; pattern nodes document applications. They link via the `defines:` edge (concept → pattern) and the pattern's reciprocal references to the concept.

## Why

The walking-skeleton practice exists because **integration risk dominates feature risk** in any multi-layer system. Building each primitive perfectly before the next means discovering at integration time that primitive A's output shape is wrong for primitive C's input — and that discovery costs the full project's worth of rework rather than one slice's worth. A thin end-to-end run surfaces the mismatch at slice 1 when the cost of fixing is bounded.

The pairing with YAGNI is load-bearing: walking-skeleton says "ship the smallest end-to-end first"; YAGNI says "don't add to it speculatively". Together they keep slice scope honest. Without YAGNI, walking-skeleton drifts toward "ship one big slice that does everything"; without walking-skeleton, YAGNI drifts toward "ship just the foundation; the consumers come in slice 4". Both rules are needed; neither alone is sufficient.

For an autonomous agent pipeline specifically, walking-skeleton has a third benefit: each slice produces real artifacts that the reviewer can judge against the PRD's success criteria. Horizontal slice-1s (pure structure, no consumers) give the reviewer nothing to judge.

## Examples from this project

- **PRD #3 slice 1 (`/ship` skeleton)** — the canonical walking-skeleton example in this codebase. Wired `to-prd → prd-critic → slicer → slicer-critic → /ship` end-to-end with stub stages, then subsequent slices replaced each stub with the real subagent.
- **PRD #242 (knowledge architecture v2)** — slice 1 cut ALL KB v2 layers in one PR (directory structure + one populated example per slot + reader extension + cascade-docs + foundational ADR + dogfood). See [[patterns/walking-skeleton]] for the layer enumeration.
- **PRD #80 (implementer subagent)** — slice 1 shipped the subagent body PLUS one real slice walkthrough PLUS the orchestrator integration in the same PR.

## Anti-patterns

- **Horizontal slice 1** — "ship the schema; consumers come in slice 2". Fails the walking-skeleton property; `slicer-critic` BLOCKs.
- **Foundation-only slice** — code that ships only types/interfaces with no consumer in the same slice. The reviewer cannot judge value; the slice fails INVEST's Valuable property.
- **"Big-bang integration slice"** — building primitives in isolation across many slices, then a single "wire it all together" slice at the end. Defeats the integration-risk-surfacing benefit.

## Scope

(b) external standard adopted

## Authority

[ADR-0001](../../../decisions/0001-foundational-design.md) D10

## References

- [ADR-0001](../../../decisions/0001-foundational-design.md) D10 — adoption of walking-skeleton as cross-cutting rule #2.
- [CLAUDE.md](../../../CLAUDE.md) cross-cutting rule #2 — the canonical project statement of the practice.
- [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D2 — concept-vs-pattern node-type distinction that justifies the dual entry shape.
- [[patterns/walking-skeleton]] — the pattern-level note documenting the project's KB-architecture application of the practice.
- [[concepts/glossary/yagni]] — the companion rule #1 that constrains walking-skeleton from drifting toward "ship everything in slice 1".
- [[concepts/glossary/hamburger-method]] — the closely-related vertical-slicing technique by Gojko Adzic.
- WardWiki, "WalkingSkeleton": https://wiki.c2.com/?WalkingSkeleton
