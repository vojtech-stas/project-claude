---
title: SC-DEP-ORDERING — slicer-critic criterion 6, dependency edges form a DAG with real prerequisites only
summary: The slicer-critic rule that slice Depends-on edges form a DAG (no cycles), every dependency is a real prerequisite (not arbitrary serialization), and the walking-skeleton slice depends on None; any violation FAILs the decomposition.
tags: [rule, slicer-critic-rubric]
type: concept
last_updated: 2026-05-26
sources:
  - .claude/agents/slicer-critic.md criterion 6
  - decisions/0010-implementer-subagent-auto-pipeline.md D3
---

# SC-DEP-ORDERING

**SC-DEP-ORDERING** is criterion 6 in the [`slicer-critic`](../../../.claude/agents/slicer-critic.md) rubric. It enforces three sub-rules on slice dependency declarations: (a) `Depends on:` edges form a DAG (no cycles), (b) every declared dependency is a *real* prerequisite (not arbitrary serialization), and (c) the walking-skeleton slice depends on `None`. Any violation is a hard **FAIL**.

## What

Mechanics:

- Build a directed graph from each slice's `Depends on:` row → other slices.
- Topological-sort: any cycle → FAIL (cycle violates DAG).
- For each declared dependency edge, ask: "could the dependent slice's implementer realistically grab and start this slice with only the dependency's PR merged?" If the dependency is actually a separate file or separate concern → FAIL (arbitrary serialization, blocks parallel dispatch).
- Walking-skeleton slice (per SC-WALKING-SKELETON) must have `Depends on: None` — if anything is upstream of slice 1, slice 1 isn't the skeleton.

The `Depends on:` declaration is load-bearing for the [`/ship`](../../../.claude/skills/ship/SKILL.md) orchestrator at stage 4: per [ADR-0010](../../../decisions/0010-implementer-subagent-auto-pipeline.md) D3, the orchestrator dispatches ready slices in DAG-aware parallel batches. A wrong dependency edge serializes work that could have parallelized; a cycle deadlocks the dispatch.

## Why

This rule exists because **dependency declarations directly drive autonomous-pipeline parallelism**. Per ADR-0010 D3, the implementer subagent is dispatched in DAG-aware parallel batches at stage 4 of `/ship`; an arbitrary `Depends on:` edge collapses the DAG into a chain, eliminating the parallelism that makes the autonomous pipeline viable for multi-slice PRDs.

The "real prerequisite" check is the most-violated part of this criterion. Slicers (and humans) tend to declare dependencies for narrative reasons ("slice 2 logically comes after slice 1") rather than mechanical ones ("slice 2 reads files that slice 1 creates"). The mechanical test is: *can the implementer claim and start slice 2 the instant slice 1 merges?* If yes, the edge is real. If slice 2 actually only depends on a portion of slice 1's output that's already on origin/main, the edge is arbitrary.

DAG-not-cycle is obvious but the check must still run mechanically — accidental circular dependencies happen when slices reference each other across complex PRDs.

## How to check

For each candidate decomposition:

1. Parse all `Depends on:` rows into a graph.
2. Run topological sort; FAIL if cycle detected.
3. For each edge A → B, ask: does B mechanically read files A creates, OR depend on a behavior A wires up? If neither → FAIL (arbitrary serialization).
4. Verify walking-skeleton slice has `Depends on: None`.

## Examples

- **Slice 2 `Depends on: slice 1`; slice 2 reads `docs/current/entities/subagents/slicer.md` which slice 1 creates** → PASS (real prerequisite).
- **Slice 3 `Depends on: slice 2`; slice 3 only touches files in `.claude/agents/` while slice 2 only touches files in `docs/current/`** → FAIL (arbitrary serialization; could run parallel).
- **Slice 2 `Depends on: slice 3`; slice 3 `Depends on: slice 2`** → FAIL (cycle).

## Edges

- **part_of:** [[entities/subagents/slicer-critic]]
- **related_to:** [[concepts/rules/sc-walking-skeleton]]
- **related_to:** [[concepts/rules/sc-risk-front-loading]]
- **related_to:** [[concepts/rules/sc-invest]]
