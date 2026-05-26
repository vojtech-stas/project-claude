---
title: SPIDR — Mike Cohn's five slice-split fallback techniques
summary: Mike Cohn's five split-fallback techniques (Spike, Path, Interface, Data, Rules) used here as split hints when a slice approaches the LoC cap, with S/I/R most applicable to this agent-workflow domain.
tags: [glossary, slicing, external-standard, methodology]
type: concept
last_updated: 2026-05-26
sources:
  - decisions/0005-output-shape-and-slicing-methodology.md
  - CLAUDE.md
  - https://www.mountaingoatsoftware.com/blog/five-simple-but-powerful-ways-to-split-user-stories
---

# SPIDR

**SPIDR** is Mike Cohn's mnemonic for five techniques to split a user story that is too large — **S**pike, **P**ath, **I**nterface, **D**ata, **R**ules. This project adopts SPIDR as split-fallback hints when a slice approaches the R-LOC 300-LoC cap, per [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D2. The slicer-critic recommends a specific SPIDR letter when the picked decomposition has a slice trending oversize.

**Edges**

- **related-to:** [[concepts/glossary/slice]]
- **related-to:** [[concepts/glossary/invest]]
- **part-of:** [[topics/slicing]]

## What

The five fallbacks:

- **S — Spike** — extract a research/learning slice when the work has too much unknown to estimate; the spike answers the unknowns, then the real slice ships next.
- **P — Path** — split by user paths (happy path / error path / edge path); rarely fits this project's agent-workflow domain.
- **I — Interface** — split by interface (one CLI command per slice, one API endpoint per slice, one subagent per slice); the highest-fit fallback for this project.
- **D — Data** — split by data variation (one row shape per slice, one input type per slice); rarely fits this project.
- **R — Rules** — split by business rule (one rubric criterion per slice, one validation per slice); high-fit when adding rules to an existing critic.

For this project's agent-workflow domain, **S, I, R** are the dominant fallbacks; P and D rarely fit and are deferred per [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D2.

## Why

SPIDR exists because the R-LOC 300-LoC cap is hard, but slice-shape is soft. When a candidate slice is too large, the slicer cannot just shrink the scope — it must split along an axis that preserves INVEST (especially Valuable and Testable). SPIDR names the five common axes so the slicer-critic's recommendations are concrete ("split per SPIDR-I: one slice per subagent") rather than vague ("split it somehow").

The SPIDR letter chosen also signals downstream consumers what the resulting slices have in common. SPIDR-I slices share an interface contract; SPIDR-R slices share a rule shape — useful when the implementer needs to know how much context to share between slices. SPIDR-S spike slices ship NO production code; they produce a learning artifact (a report, a test result, a benchmark) that informs the subsequent non-spike slices.

Each slice body's "Notes for the implementer" section names the **SPIDR fallback hint** the slicer attached at decomposition time, so if the implementer hits the R-LOC cap mid-implementation they have a pre-blessed split path rather than needing to re-grill the slicer.

## Examples from this project

- **PRD #245 → 3 slices** — split per SPIDR-D-like grouping (5 most edge-rich terms / 9 general terms / 8 convention-name terms + INDEX cleanup), each cluster a coherent chunk.
- **PRD #3 → 5 slices** — split per SPIDR-I (one pipeline-stage interface per slice).
- **Slice #246 SPIDR fallback hint** — if the 5 atomic notes overrun, slicer recommended SPIDR-D split into 1a (3 notes + scaffold) + 1b (2 notes), both still walking-skeleton-shaped.

## Anti-patterns

- **Splitting without picking a SPIDR axis** — produces incoherent slices ("the first 50 LoC" is not a SPIDR split); reviewer cannot reason about cross-slice dependencies.
- **SPIDR-P or SPIDR-D in agent-workflow domain** — usually a smell here (no user paths; no rich data variation); prefer S/I/R.
- **Spike slice that ships production code** — defeats the purpose; a spike is purely investigative.

## Scope

(b) external standard adopted

## Authority

[ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D2

## References

- [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D2 — SPIDR adoption + S/I/R fit notes for this project's domain.
- Mike Cohn, "Five Simple but Powerful Ways to Split User Stories": https://www.mountaingoatsoftware.com/blog/five-simple-but-powerful-ways-to-split-user-stories
- [`.claude/agents/slicer-critic.md`](../../../.claude/agents/slicer-critic.md) — emits SPIDR-letter recommendations on candidate decompositions.
- [CLAUDE.md](../../../CLAUDE.md) "Slicing logic — what makes a good slice" — methodology overview.
- [[invest]] — the shape contract SPIDR splits must preserve.
