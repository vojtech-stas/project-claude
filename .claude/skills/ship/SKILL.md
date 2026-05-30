---
name: ship
description: Run the autonomous pipeline from grilled context to posted PRD-and-slices on GitHub. Use after /grill-me when the user says "ship it", "/ship", "turn this into a PRD and slices", or otherwise asks to hand off the grilled idea to the autonomous pipeline.
---

# /ship — autonomous pipeline orchestrator

Chains `/to-prd → prd-critic (+ adr-critic) → /to-issues → slicer → slicer-critic → gh issue create → implementer (DAG-aware parallel) → reviewer (auto-merge)` so the human only needs two commands per feature: `/grill-me` to define the *what*, then `/ship` to drive it through PRD authoring, slice decomposition, per-slice implementation, and auto-merge.

Full role synthesis (chain rationale, forward-block semantics, terminal-state collection): this file. Stage-by-stage operational logic (what each hook does, hook contract, "what the pipeline deliberately does NOT do"): pipeline-stages (see CLAUDE.md). Vocabulary: prd, slice, joint-approve-gate, walking-skeleton (see CLAUDE.md glossary).

## When NOT to use this skill

- Mid-grill, before the user has explicitly said the design is settled — run `/grill-me` first.
- For trivial one-line fixes — use the `hotfix/<thing>` lane (I3).
- When there is no conversation context to synthesize — `/ship` consumes context, it does not interview.

## Step-by-step procedure

1. **Confirm grilled context.** Scan history for a settled design (typically a recent `/grill-me` session). If the design is thin or open, STOP and ask the user to grill further. Do NOT invent a PRD.

2. **Stage 2 — `/to-prd`.** Invoke [`.claude/skills/to-prd/SKILL.md`](../to-prd/SKILL.md) unchanged. It runs `prd-critic` (+ `adr-critic` under shared round counter when a macro-ADR is drafted) internally per [ADR-0004](../../../decisions/0004-bypass-prevention.md) D1's joint-APPROVE gate, then publishes via `gh issue create`. Capture the PRD issue number.

3. **Stage 2.5 verification.** Verify `to-prd` reported APPROVE — the posted PRD body should end with `> **Pipeline metadata** — Approved by prd-critic round <N>/3.` (extended with `; adr-critic round <N>/3 (ADR-NNNN)` when an ADR was drafted). On round-3 BLOCK or `ESCALATE: needs-human` from either critic, STOP — do NOT proceed to stage 3. Surface findings and recommend re-grilling. Macro-ADRs ship as files in slice 1's PR per [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D8, not as separate issues.

4. **Stage 3 — `/to-issues`.** Invoke [`.claude/skills/to-issues/SKILL.md`](../to-issues/SKILL.md) unchanged with the PRD issue number from step 2. Internally it invokes `slicer` (N=3 alternative decompositions per [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D3, or N=1 carveout per [ADR-0013](../../../decisions/0013-slicer-n3-contract-refined.md)) and `slicer-critic` (best-of-N with single revision loop). On BLOCK, surface and STOP — do NOT post slices. On APPROVE, capture the slice issue numbers in dependency order.

5. **Stage 4 — implementer + reviewer (DAG-aware parallel batches).** Per [ADR-0010](../../../decisions/0010-implementer-subagent-auto-pipeline.md) D2/D3/D4:
   - **5a. Build the DAG.** Parse each slice's `## Depends on` (slicer-critic-verified per [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D3). Topologically sort; ties broken by issue number ascending. On parse failure or cycle, STOP with `RESULT: INVALID_INPUT` in the trailer.
   - **5b. Dispatch loop.** Maintain four sets — `pending`, `in_flight`, `merged`, `blocked`. Each iteration: compute the **ready batch** (every `pending` slice whose deps are all in `merged` AND has no dep in `blocked`); slices with a `blocked` dep move directly to `blocked` (forward-block). **Dispatch the ready batch in parallel** by invoking the [`implementer`](../../agents/implementer.md) subagent via the `Agent` tool with `subagent_type: "implementer"` (fallback `general-purpose` with the implementer prompt loaded inline) for each slice; move each to `in_flight`. **When the ready batch has size ≥ 2, each `implementer` `Agent` call MUST pass `isolation: "worktree"` so every implementer runs in its own harness-created, auto-cleaned worktree — this prevents the shared-worktree `git checkout -b` race (#322). Batch size 1 needs no isolation** (single-slice PRDs trivially reduce to batch size 1 — no separate code path; per **ADR-0035 D1**). Await batch completion; handle outcomes per 5c. Loop until `pending` and `in_flight` are both empty.
   - **5c. Per-slice outcome.** `RESULT: SUCCESS` → reviewer takes over per [ADR-0002](../../../decisions/0002-autonomous-merge-policy.md) (auto-merge on APPROVE via `gh pr merge --squash --delete-branch`; round-3 BLOCK applies `needs-human` and forward-blocks per 5d). On reviewer APPROVE+merge → `merged`. On reviewer round-3 BLOCK or implementer `RESULT: BLOCKED` / `RESULT: INVALID_INPUT` → forward-block per 5d.
   - **5d. Forward-block** (per [ADR-0010](../../../decisions/0010-implementer-subagent-auto-pipeline.md) D4). Apply `needs-human` to the failed slice; move transitive-downstream slices from `pending` → `blocked`; post one summary comment per failure event on the parent PRD (mirrors reviewer's I5 surface). **In-flight parallel siblings finish normally** — do NOT cancel. **Slices with other unmet deps proceed normally** through their natural batches; failure is locally contained to the failed slice's downstream cone.
   - **5e. Terminal-state collection.** Capture each `PR_URL` from SUCCESS slices (merged or under-review), the `blocked` set, and the snapshot of `in_flight` at the moment the FIRST failure was observed.

6. **Report back.** Print the PRD URL, slice URLs, merged/open implementation PR URLs, and any forward-block summary (failed slice + downstream blocked + needs-human PRs). Free-form narrative; not itself a canonical template per PRD #28 §6 OQ#2. End with the canonical GENERATOR trailer as a fenced block (schema per ADR-0005 D1c):

   ```
   RESULT: SUCCESS | STOPPED | INVALID_INPUT
   REASON: <one sentence>
   ARTIFACTS: <PRD URL>, <slice URLs comma-separated>
   SLICE_COUNT: <N>
   IMPLEMENTATION_PRS: <comma-separated PR URLs from implementer invocations; empty if pipeline halted before stage 4>
   BLOCKED_SLICES: <comma-separated slice numbers in the `blocked` set per 5d; empty if no failures>
   IN_FLIGHT_AT_FAILURE: <comma-separated slice numbers in `in_flight` at the moment of FIRST failure per 5e; empty if no failures>
   ```

   `SLICE_COUNT` / `IMPLEMENTATION_PRS` / `BLOCKED_SLICES` / `IN_FLIGHT_AT_FAILURE` are per-agent extensions appended after `ARTIFACTS` so human triage and post-run audits find every stuck slice without re-parsing. On `STOPPED` / `INVALID_INPUT`, `ARTIFACTS` may be partial or empty; the extensions are `0` / empty.

## References

- Full role synthesis (invocation contract, edges): this file. Pipeline stages synthesis: pipeline-stages (see CLAUDE.md).
- [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) — D2 (5-stage pipeline), D4 (no human gates between stages; closed end-to-end by ADR-0010), D7 (`/ship` orchestrator skill, lightweight v1), D8 (ADR placement at slice 1).
- [ADR-0010](../../../decisions/0010-implementer-subagent-auto-pipeline.md) — D2 (auto-invoke implementer), D3 (DAG-aware parallel batching), D4 (forward-block failure handling), D5 (sequential walking-skeleton baseline).
- [ADR-0035](../../../decisions/0035-worktree-isolation-parallel-dispatch.md) — D1 (per-agent `isolation: "worktree"` for ready batches ≥ 2, eliminating the shared-worktree race); D2 (isolation lives in orchestrator; implementer unchanged).
- [ADR-0002](../../../decisions/0002-autonomous-merge-policy.md) — reviewer auto-merge on APPROVE; the handoff target after implementer SUCCESS.
- Sibling skills the chain calls: [`.claude/skills/to-prd/SKILL.md`](../to-prd/SKILL.md), [`.claude/skills/to-issues/SKILL.md`](../to-issues/SKILL.md). Subagent dispatched at stage 4: [`.claude/agents/implementer.md`](../../agents/implementer.md). Sibling skill (terminal human checkpoint): [`.claude/skills/qa-plan/SKILL.md`](../qa-plan/SKILL.md).

## Local vocabulary

Per [ADR-0014](../../../decisions/0014-skill-local-vocabulary-and-auto-fold.md) D1. Folded to CLAUDE.md by [`/glossary-fold`](../glossary-fold/SKILL.md) when entries pass the [ADR-0012](../../../decisions/0012-glossary-consolidation-single-tier.md) D2 citation threshold and `glossary-critic` rubric.

- **pipeline metadata footer** — the one-line `> **Pipeline metadata** — Approved by prd-critic round <N>/3...` audit trailer that `/to-prd` appends to every posted PRD body so `/ship` and downstream critics can mechanically verify upstream APPROVE without re-running the loop.
  - *Scope:* (a) project jargon coined here
  - *Authority:* `ADR-0003 D8`
  - *See also:* `/to-prd`; `/ship`; prd-critic
