---
title: ship — autonomous pipeline orchestrator (grilled-context → posted PRD → merged slices)
summary: Stage-2-through-4 orchestrator that chains to-prd → prd-critic → to-issues → slicer → slicer-critic → implementer → reviewer, dispatching slices in DAG-aware parallel batches with forward-block failure handling; single human command per feature after /grill-me.
tags: [skill, pipeline, orchestrator, ship]
type: entity
last_updated: 2026-05-27
sources:
  - .claude/skills/ship/SKILL.md
  - decisions/0003-autonomous-pipeline-with-critics.md
  - decisions/0010-implementer-subagent-auto-pipeline.md
  - decisions/0002-autonomous-merge-policy.md
---

# /ship

The `/ship` skill is the **autonomous pipeline orchestrator** that takes a grilled conversation context and drives it end-to-end through PRD authoring, slice decomposition, and per-slice implementation + auto-merge. It is the single human-issued command per feature after `/grill-me`; the only remaining human checkpoint is `/qa-plan` at PRD acceptance per [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D4 (as refined by [ADR-0020](../../../decisions/0020-qa-automation-writer-executor.md) D10).

## Role and responsibility

`/ship` is the chain — it does not author PRDs, does not decompose slices, does not write code. Its job is sequencing and gating:

1. **Verify grilled context exists.** If conversation is thin or design is still open, STOP and ask the user to grill further. Do NOT invent a PRD.
2. **Chain stages 2 through 4** in order, each gated by its critic's APPROVE before the next stage starts. Halt on any unrecoverable BLOCK; surface critic findings to the user.
3. **Dispatch stage 4 in DAG-aware parallel batches** per [ADR-0010](../../../decisions/0010-implementer-subagent-auto-pipeline.md) D3 — independent slices run concurrently; chained slices wait for upstream merges; failed slices forward-block their downstream cone per D4.
4. **Emit the canonical [GENERATOR trailer](../../concepts/glossary/generator-trailer.md)** with `SLICE_COUNT`, `IMPLEMENTATION_PRS`, `BLOCKED_SLICES`, `IN_FLIGHT_AT_FAILURE` per-agent extensions naming what shipped, what's stuck, and what was concurrent at the moment of any failure.

## The chain

```
grill-me (done by user before /ship)
   |
   v
to-prd → prd-critic (+ adr-critic if macro-ADR) → gh issue create (PRD)
   |
   v
to-issues → slicer → slicer-critic → gh issue create (slices)
   |
   v
implementer (per-batch, DAG-aware parallel) → reviewer (per slice, auto-merge on APPROVE)
   |
   v
all slices merged (or forward-blocked downstream of a needs-human slice)
```

Stage 4 (implementer + reviewer per slice) is filled per [ADR-0010](../../../decisions/0010-implementer-subagent-auto-pipeline.md) D2 (sequential walking-skeleton baseline) and D3 (parallel-where-independent DAG batching). Stage 5 (`/qa-plan`) remains the terminal human checkpoint per [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D4 and is out of `/ship`'s scope.

## Invocation contract

- **Caller:** the user, typically immediately after a `/grill-me` session settles the design.
- **Input:** no positional arguments. The skill scans the conversation context for a recently-grilled design.
- **Output:** terminal report (PRD URL + slice URLs + merged/open PR URLs + any forward-block summary) plus the canonical GENERATOR trailer with 4 per-agent extensions (`SLICE_COUNT`, `IMPLEMENTATION_PRS`, `BLOCKED_SLICES`, `IN_FLIGHT_AT_FAILURE`).
- **Tool boundaries:** main-agent context (so it can invoke other skills + the `Agent` tool for `implementer` + `reviewer` dispatch).

## Forward-block failure handling (per [ADR-0010](../../../decisions/0010-implementer-subagent-auto-pipeline.md) D4)

When a slice fails (BLOCKED, INVALID_INPUT, or reviewer round-3 BLOCK):

1. Apply `needs-human` label to the failed slice (no-op if reviewer already applied it on round-3 BLOCK).
2. Compute transitive downstream set; move them all from `pending` to `blocked` (they stay open; orchestrator does not retry, does not close).
3. Post summary comment on the parent PRD issue naming the failed slice + downstream-blocked slices.
4. **In-flight parallel siblings finish normally** — do NOT cancel them. The dispatch loop's next iteration awaits their completion; their PRs proceed to reviewer per the normal path.
5. **Slices with OTHER unmet deps proceed normally** through their natural batches once those deps merge. Failure is locally contained to the failed slice's downstream cone.

## Relationship to other skills and agents

- **Calls** [`to-prd`](to-prd.md) at stage 2, [`to-issues`](to-issues.md) at stage 3 — both unchanged.
- **Auto-invokes** the [`implementer`](../subagents/implementer.md) subagent at stage 4a per [ADR-0010](../../../decisions/0010-implementer-subagent-auto-pipeline.md) D2.
- **Auto-invokes** the [`reviewer`](../subagents/reviewer.md) subagent at stage 4b per [ADR-0010](../../../decisions/0010-implementer-subagent-auto-pipeline.md) D8; reviewer auto-merges on APPROVE per [ADR-0002](../../../decisions/0002-autonomous-merge-policy.md).
- **Sibling to** [`qa-plan`](qa-plan.md) — the terminal human checkpoint that runs AFTER all `/ship`-dispatched PRs have merged.
- **Honors the 6-critic-cap** per [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7 — `/ship` is a skill (orchestrator), not a critic.
- **Authority:** [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D2 (5-stage pipeline), D4 (no human gates between stages), D7 (`/ship` orchestrator skill, lightweight v1); [ADR-0010](../../../decisions/0010-implementer-subagent-auto-pipeline.md) D2/D3/D4 (auto-invoke implementer; DAG parallel; forward-block).

## Edges

- **part_of:** [[topics/pipeline-stages]]
- **related_to:** [[entities/skills/to-prd]]
- **related_to:** [[entities/skills/to-issues]]
- **related_to:** [[entities/skills/qa-plan]]
- **related_to:** [[entities/subagents/implementer]]
- **related_to:** [[entities/subagents/reviewer]]
- **related_to:** [[topics/output-shapes]]
- **related_to:** [[concepts/glossary/prd]]
- **related_to:** [[concepts/glossary/slice]]
- **related_to:** [[concepts/glossary/walking-skeleton-glossary]]
