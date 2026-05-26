---
title: PRD — feature-sized Product Requirements Document
summary: A feature-sized Product Requirements Document captured as a GitHub Issue labeled `prd`, with the 6-section template; the top tier of the PRD-Slice-PR hierarchy.
tags: [glossary, pipeline, hierarchy, project-jargon]
type: concept
last_updated: 2026-05-26
sources:
  - decisions/0003-autonomous-pipeline-with-critics.md
  - CLAUDE.md
---

# PRD

A **PRD** (Product Requirements Document) is the top tier of this project's PRD-Slice-PR delivery hierarchy. Each PRD captures ONE feature-sized deliverable as a GitHub Issue labeled `prd`, written to the 6-section template (Problem / Goal / Non-goals / Appetite / Solution sketch / Rabbit-holes & Open questions). The canonical template lives in [`.claude/skills/to-prd/SKILL.md`](../../../.claude/skills/to-prd/SKILL.md) per [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D1.

**Edges**

- **related-to:** [[concepts/glossary/slice]]
- **related-to:** [[concepts/glossary/critic]]
- **part-of:** [[topics/pipeline-stages]]

## What

A PRD is a GitHub Issue with the `prd` label that scopes ONE feature-sized deliverable. Its body follows the 6-section template introduced by [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D1 and operationalized by the [`/to-prd`](../../../.claude/skills/to-prd/SKILL.md) skill:

1. **Problem** — the trigger; what is broken or missing today. Concrete recent instances cited; abstract problem statements rejected.
2. **Goal / Success criteria** — mechanically verifiable outcomes the PRD must produce. Each criterion is a greppable check or a discrete artifact-exists check.
3. **Non-goals / Out of scope** — explicit list of what this PRD will NOT do (drift defense). Becomes the reviewer's scope citation later.
4. **Appetite** — rough sizing; typically named in terms of expected slice count and runtime LoC ballpark.
5. **Solution sketch** — high-level shape of the answer, not the implementation; leaves room for slicer judgment.
6. **Rabbit-holes & Open questions** — pre-named risks, deferred decisions, recurring-defect watchlist.

Multi-feature PRDs are a smell — if the appetite implies more than one PRD's worth of work, split into multiple PRDs. The `prd` label is load-bearing: `slicer-critic`, `reviewer`, and `/qa-plan` all dispatch on it.

## Why

PRDs are the unit at which **scope is locked**. Slices are negotiable within a PRD; the PRD itself names the boundary. Without a PRD, scope drift is invisible because there is nothing to drift FROM. The 6-section template forces the author to name the non-goals up front, so the reviewer can later cite the original Non-goals list when blocking out-of-scope additions during PR review.

PRDs also anchor the autonomous pipeline. [`/grill-me`](../../../.claude/skills/grill-me/SKILL.md) produces a PRD draft; [`prd-critic`](../../../.claude/agents/prd-critic.md) judges it (jointly with [`adr-critic`](../../../.claude/agents/adr-critic.md) when a macro-ADR ships alongside per [ADR-0004](../../../decisions/0004-bypass-prevention.md) D1); [`/ship`](../../../.claude/skills/ship/SKILL.md) consumes the approved PRD as input to slicing. Every downstream stage references the parent PRD by issue number, and [`/qa-plan`](../../../.claude/skills/qa-plan/SKILL.md) closes the loop by extracting acceptance criteria from PRD §2 once all child slices merge.

## Examples from this project

- **PRD #3** — the foundational pipeline-bootstrap PRD that introduced the PRD-Slice-PR hierarchy itself.
- **PRD #242** — knowledge-architecture-v2 (the macro-ADR PRD whose successor sequence runs T1-T9 to migrate inlined content into the KB).
- **PRD #245** — the parent of this very slice; migrates 22 glossary terms into atomic concept notes across 3 sibling slices.

## Anti-patterns

- **Multi-feature PRDs.** "PRD: add hooks AND migrate glossary AND ship new critic" — split into 3 PRDs. Each PRD must close cleanly when its goal is met.
- **Aspirational success criteria.** "Goal: improve developer experience" — not mechanically verifiable. The `prd-critic` rubric BLOCKs on this.
- **Missing Non-goals.** An empty Non-goals section is a drift trap; the reviewer has nothing to cite when scope creep arrives.

## Scope

(a) project jargon coined here

## Authority

[ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D1

## References

- [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D1 — PRD-Slice-PR hierarchy lock.
- [ADR-0004](../../../decisions/0004-bypass-prevention.md) D1 — joint-APPROVE gate when a macro-ADR ships alongside a PRD.
- [`.claude/skills/to-prd/SKILL.md`](../../../.claude/skills/to-prd/SKILL.md) — canonical home of the 6-section PRD template.
- [`.claude/skills/grill-me/SKILL.md`](../../../.claude/skills/grill-me/SKILL.md) — the upstream interview that produces a PRD draft.
- [`.claude/skills/ship/SKILL.md`](../../../.claude/skills/ship/SKILL.md) — the downstream orchestrator that consumes an approved PRD.
- [CLAUDE.md](../../../CLAUDE.md) "Hierarchy — PRD → Slice → PR (3-tier)" — operating shape of the hierarchy.
