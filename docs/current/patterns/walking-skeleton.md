---
title: Walking-skeleton — smallest end-to-end first
summary: Build the smallest end-to-end version of the whole pipeline first; iterate on the weakest stage rather than perfecting one primitive in isolation.
tags: [methodology, slicing, yagni, walking-skeleton]
type: pattern
last_updated: 2026-05-26
sources:
  - decisions/0001-foundational-design.md
  - CLAUDE.md cross-cutting rule #2
  - decisions/0031-knowledge-architecture-v2.md
---

# Walking-skeleton

The dogfood atomic-notes pattern for this KB. Walking-skeleton is the project's rule-#2 cross-cutting practice and the slicing-time anti-anti-pattern. This note is itself an example of a walking-skeleton output: PRD #242's first slice cuts ALL knowledge-architecture-v2 layers (structure + content + reader + cascade-docs + ADR + dogfood) in one PR rather than building each primitive in isolation.

**Edges**

- **defines:** [[../../../CLAUDE.md]] (cross-cutting rule #2 is the canonical statement of the practice in this project)
- **depends-on:** [[concepts/glossary/yagni]] (rule #1; walking-skeleton is meaningless without rule-#1 scope discipline — link points to future content per [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D6 forward-binding)
- **related-to:** [[concepts/glossary/walking-skeleton-glossary]] (glossary entry for this practice; back-ref so cascade-finder surfaces this pattern as a dependent)
- **related-to:** [[cascade-doc-check]] (sister slicing-time practice; future pattern note)
- **part-of:** [[../topics/slicing]] (the slicing topic synthesis; future content)
- **references:** [[../../../decisions/0001-foundational-design.md]] (D10 — original adoption of the practice)


## What

Build the smallest possible end-to-end version of the whole pipeline first, then iterate on the weakest stage. The walking-skeleton is *thin* (each layer is minimally functional) but *complete* (every layer is touched in the first slice).

The opposite is **horizontal layering**: build all of layer 1 perfectly, then all of layer 2 perfectly, then all of layer 3 perfectly — discovering at integration time that layer 1's output shape is wrong for layer 3's input.

## Why

Three reinforcing reasons:

1. **Integration risk surfaces early.** Connecting layers always reveals impedance mismatches; a walking-skeleton finds them at slice 1 when the cost of fixing is one slice's worth of work, not at the end when it is the project's worth.
2. **Real-world feedback at minimum cost.** A thin end-to-end run produces real artifacts (a real PR opened, a real reviewer verdict posted, a real merge happening) that reveal which layer is weakest. Without that signal, optimization energy is allocated by intuition rather than evidence.
3. **YAGNI discipline.** Building each primitive perfectly before the next means building primitives that downstream stages will not actually use, or will use differently. The walking-skeleton constrains every layer to "only what slice 1 needs" — purely-speculative work is rejected by construction.

## How

When decomposing a feature into slices, slice 1 MUST cut every layer end-to-end. Subsequent slices iterate per the weakness signal from slice 1's actual operation. For this project specifically:

- **For PRDs with multiple subagents:** slice 1 ships ONE minimal end-to-end flow exercising every subagent. Subsequent slices add depth.
- **For PRDs with new file structure:** slice 1 creates the structure AND ships one populated example per structural slot (one concept, one entity, one topic, one pattern — not just the directories).
- **For PRDs with new tooling:** slice 1 wires the tool through one real consumer's path. No tool ships without a consumer in the same slice.

Slicing checks the cut against the hamburger-method criterion (vertical not horizontal). [`slicer-critic`](../../../.claude/agents/slicer-critic.md)'s rubric criterion 1 enforces.

## Anti-pattern — horizontal layering

The recurring anti-pattern: "let's build the whole schema first, then write the readers, then wire the consumers." Symptoms:

- Slice 1 ships pure structure (empty directories, frontmatter schema doc, no consumers wired)
- Slice 2 ships readers that have nothing real to read
- Slice 3 wires consumers and discovers the schema does not fit consumer needs
- Refactor required, time lost

The fix is constitutional: at slicing time, REJECT any slice 1 that does not exercise every layer. Slicer + slicer-critic gate this; reviewer's R-BOY-SCOUT (per [ADR-0018](../../../decisions/0018-boy-scout-reviewer-rule.md)) catches drift post-hoc.

## Examples from this project

- **PRD #3 (pipeline bootstrap)** — slice 1 of #3 wired `to-prd → prd-critic → slicer → slicer-critic → /ship` end-to-end with stub stages, then subsequent slices replaced each stub with the real subagent. The pipeline was operational (if minimal) from slice 1 forward.
- **PRD #80 (implementer auto-pipeline)** — the `implementer` subagent shipped with a single real slice walkthrough alongside the subagent definition; the orchestrator was extended to dispatch it in the same PR. Per [ADR-0010](../../../decisions/0010-implementer-subagent-auto-pipeline.md), the walking-skeleton cut both subagent introduction AND its first orchestrator integration in slice 1.
- **PRD #242 / this PR (knowledge architecture v2)** — slice 1 ships ALL KB v2 layers: directory structure (`docs/raw/`, four `docs/current/` subdirs) + one populated example per structural slot (`patterns/walking-skeleton.md` this very file, `topics/knowledge-architecture.md`, `topics/kb-schema.md`) + reader extension (`current-state-reader` path-dispatch + edge-resolution) + cascade-doc updates (CLAUDE.md KB-schema section, `decisions/README.md` row) + the foundational ADR (`decisions/0031-knowledge-architecture-v2.md`) + dogfood evidence in PR body. Per [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D15, all layers are touched; T1-T9 follow-up PRDs migrate existing content into the proven structure.


## References

- [CLAUDE.md](../../../CLAUDE.md) cross-cutting rule #2 — the canonical project statement of the practice.
- [ADR-0001](../../../decisions/0001-foundational-design.md) D10 — original adoption of walking-skeleton.
- [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D15 — this PR's enumeration of the cut layers.
- [ADR-0010](../../../decisions/0010-implementer-subagent-auto-pipeline.md) — implementer-subagent walking-skeleton example.
- Hamburger method (Gojko Adzic): https://gojko.net/2012/05/01/the-hamburger-method/
