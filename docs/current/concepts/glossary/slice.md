---
title: slice — INVEST-shaped vertical sub-issue under a PRD
summary: A single INVEST-shaped vertical sub-issue under a PRD (labeled `slice`), completable in one PR with at most 300 LoC runtime-artifact diff; the middle tier of the PRD-Slice-PR hierarchy.
tags: [glossary, pipeline, hierarchy, common-word-narrowed]
type: concept
last_updated: 2026-05-26
sources:
  - decisions/0003-autonomous-pipeline-with-critics.md
  - CLAUDE.md
---

# slice

A **slice** is the middle tier of this project's PRD-Slice-PR delivery hierarchy. Each slice is a GitHub sub-issue under a parent PRD (linked via the native GitHub sub-issue mechanism), labeled `slice`, shaped to be INVEST-compliant, and bounded so that ONE PR can close it with at most 300 LoC of runtime-artifact diff (R-LOC cap per [`reviewer.md`](../../../.claude/agents/reviewer.md) rule 9).

**Edges**

- **related-to:** [[concepts/glossary/prd]]
- **related-to:** [[concepts/glossary/invest]]
- **part-of:** [[topics/pipeline-stages]]

## What

A slice is a vertical cut through a feature: end-to-end value in one PR, not a horizontal layer. The [`slicer`](../../../.claude/agents/slicer.md) subagent produces N candidate decompositions from a PRD (per [ADR-0013](../../../decisions/0013-slicer-n3-contract-refined.md) D1 — N typically 3); [`slicer-critic`](../../../.claude/agents/slicer-critic.md) picks the best of N and runs a single revision loop. Each slice carries:

- A title following Conventional Commits shape (`feat:`, `fix:`, `docs:`, …) with a parent reference prefix like `slice N of PRD #M:`.
- A body naming the parent PRD, the files to ship, the mechanically-verifiable acceptance criteria, the "Blocked by" forward-binding dependencies, and explicit out-of-scope notes.
- The `slice` label (load-bearing — reviewer's R-CLOSES enforces; slicer-critic criterion 10 checks the parent linkage).

Slices map 1:1 to PRs: one slice → one branch → one PR → one squash-merge commit on `main`.

## Why

Slicing exists because **PR review attention is the scarce resource**. A 1000-LoC PR receives shallow review; a 100-LoC PR receives mechanical, exhaustive review. The 300-LoC R-LOC cap is calibrated to the reviewer's actual attention budget. Slices also enable the walking-skeleton pattern (see [[../patterns/walking-skeleton]]): slice 1 of any PRD must cut every layer end-to-end, so integration risk surfaces at slice-1 time rather than at integration time when the cost of fixing is the PRD's worth, not one slice's.

The slice tier also creates a natural unit for **scope litigation**. When a PR threatens to grow beyond its slice body's acceptance criteria, reviewer cites the slice body as the spec contract and BLOCKs the drift — without slices, "while I'm here" additions would silently expand every PR. Slices also enable per-slice ownership claims via the I2 slice-grabbing protocol (`gh issue edit <N> --add-assignee @me`).

## Examples from this project

- Slice **#4** of PRD #3 — `/ship` orchestrator skeleton (walking-skeleton).
- Slice **#246** — this very slice; migrates 5 pipeline-cluster glossary terms + INDEX scaffold + path adjusters.
- Trivial-lane "slices" (e.g., `hotfix/<n>-fix-typo`) are NOT slice-labeled; they skip the slice ceremony per I3.

## Anti-patterns

- **Horizontal slice 1.** "Ship the schema first; consumers come in slice 2" — fails the walking-skeleton rule and inflates integration risk. Slicer-critic criterion 1 BLOCKs.
- **Slice without acceptance criteria.** Body has "What to build" but no mechanically-verifiable check — reviewer cannot litigate scope at PR time.
- **Slice growing past R-LOC mid-PR.** Reviewer BLOCKs; implementer must split via SPIDR rather than negotiate the cap upward.

## Scope

(c) common word with narrowed meaning here

## Authority

[ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D1

## References

- [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D1 — slice tier and PRD-Slice-PR hierarchy lock.
- [ADR-0013](../../../decisions/0013-slicer-n3-contract-refined.md) D1 — slicer N-candidate contract.
- [`.claude/agents/reviewer.md`](../../../.claude/agents/reviewer.md) rule 9 — R-LOC 300-LoC cap canonical definition.
- [`.claude/agents/reviewer.md`](../../../.claude/agents/reviewer.md) rule 10 — R-CLOSES; the slice-label dispatch.
- [CLAUDE.md](../../../CLAUDE.md) I2 — slice-grabbing protocol via `gh issue edit --add-assignee @me`.
- [CLAUDE.md](../../../CLAUDE.md) I4 — slice size cap and 7-day staleness rule.
