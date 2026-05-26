---
title: R-ADR-CONFLICT — reviewer hard-block on PR contradicting an accepted ADR
summary: The reviewer rule that BLOCKs any PR whose changes contradict a decision recorded in an existing ADR, unless the same PR ships a new ADR that explicitly supersedes the old one.
tags: [rule, reviewer-rubric, hard-block]
type: concept
last_updated: 2026-05-26
sources:
  - .claude/agents/reviewer.md rule 8
  - decisions/0001-foundational-design.md D8
---

# R-ADR-CONFLICT

**R-ADR-CONFLICT** is rule 8 in the [`reviewer`](../../../.claude/agents/reviewer.md) rubric. It hard-blocks any PR whose changes contradict a decision recorded in an existing ADR, UNLESS the same PR ships a new ADR that explicitly supersedes the old one. The rule enforces ADR immutability (per `decisions/README.md`) at PR review time and complements the supersession workflow defined in [ADR-0001](../../../decisions/0001-foundational-design.md) D8.

## What

The rule fires on every PR. Mechanics:

- Reviewer reads relevant ADRs via `Glob decisions/*.md` then `Read` per area of the PR.
- For each ADR's D-IDs, cross-checks: does the diff contradict any explicit decision?
- If yes AND no superseding ADR ships in the same PR → BLOCK with `R-ADR-CONFLICT: PR contradicts decision <ADR-NNNN> D<N> but no superseding ADR is included`.

What counts as a contradiction:

- Diff alters a behavior the ADR explicitly DECIDED (e.g., changes the auto-merge condition the ADR locked).
- Diff adds a convention the ADR explicitly REJECTED (e.g., re-introduces a path the ADR's "alternatives rejected" section ruled out).
- Diff edits an immutable ADR file directly (a separate immutability violation; doubles as an R-ADR-CONFLICT trigger).

What does NOT count:

- Diff respects all ADR decisions but adds new content beyond their scope: PASS.
- Diff supersedes via a new ADR file in the same PR (the new ADR explicitly cites the old by D-ID and rationale): PASS — supersession is the legitimate path.

## Why

R-ADR-CONFLICT exists because **decisions accumulate; agents drift unless mechanically anchored**. Without it, future implementers can silently override past decisions, leaving the ADR record incoherent with the actual codebase. The supersession workflow (per ADR-0001 D8) is the explicit safety valve: contradicting an ADR is allowed, but only if you write a new ADR explaining why — making the decision-flip visible to future readers.

The hard-block default reflects the asymmetric cost: a false-positive BLOCK costs one revision cycle (implementer either revises the diff or writes the superseding ADR); a false-negative APPROVE permanently corrupts the ADR record's accuracy.

## How to check

```bash
git diff origin/main..HEAD --name-only | grep -E '^decisions/[0-9]+-' || true
```

If the diff doesn't add a new ADR, but DOES alter behavior covered by an existing ADR, BLOCK. For each ADR in the area of the PR:

```bash
grep -E '^### D[0-9]+' decisions/<NNNN>-<slug>.md
```

Read each D-ID and check whether the diff alters the decided behavior.

## Exemptions

- **PR ships a superseding ADR** that explicitly cites the old ADR's D-ID + supersession rationale: PASS.
- **PR ships content the ADR explicitly authorized as forward-binding** (e.g., walking-skeleton slice 1 forward-binding edges per [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D10): PASS.

## Recovery

If R-ADR-CONFLICT fires legitimately (the implementer wants to change a decision):

1. Pause the current slice.
2. Open a `/grill-me` session to draft a new ADR superseding the old one.
3. Land the new ADR in its own PR (or as the slice's first commit).
4. Resume the slice; R-ADR-CONFLICT now passes because the new ADR is in the diff.

## Examples

- **PR removes the 300-LoC R-LOC cap without writing a superseding ADR**: BLOCK — [R-LOC](r-loc.md) is locked by [ADR-0001](../../../decisions/0001-foundational-design.md) D11 family / reviewer.md rule 9; needs supersession.
- **PR ships a 7th critic without a new ADR justifying it**: BLOCK — [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7 locks the 6-critic-cap and requires explicit ADR-superseding-D7 to add a 7th.
- **PR ships ADR-0032 superseding ADR-0008 D7 to add a 7th critic**: PASS — the superseding ADR is the legitimate path.

## Edges

- **part_of:** [[entities/subagents/reviewer]]
- **related_to:** [[concepts/glossary/adr]]
- **related_to:** [[concepts/rules/r-meta]]
- **part_of:** [[topics/reviewer-philosophy]]
