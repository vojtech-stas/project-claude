---
name: ship
description: Run the autonomous pipeline from grilled context to posted PRD-and-slices on GitHub. Use after /grill-me when the user says "ship it", "/ship", "turn this into a PRD and slices", or otherwise asks to hand off the grilled idea to the autonomous pipeline.
---

# /ship — autonomous pipeline orchestrator (walking skeleton)

This skill chains the existing PRD-authoring and slice-decomposition skills end-to-end so the human only needs two commands per feature: `/grill-me` to define the *what*, then `/ship` to produce a posted PRD with sub-issued slices.

This is the **walking-skeleton version** (PRD #3, slice #4). It validates the orchestration plumbing before any critic logic exists. Future slices replace the named hook stages below with real adversarial critic loops without re-shaping the chain.

## When NOT to use this skill

- Mid-grill, before the user has explicitly said the design is settled. Run `/grill-me` first.
- For trivial one-line fixes (typo, label tweak). Use the `hotfix/<thing>` lane instead.
- When there is no conversation context to synthesize — `/ship` consumes context, it does not interview.

## The chain

```
grill-me  (already done by the user before invoking /ship)
   |
   v
to-prd ----------------- stage 2: PRD authoring
   |
   v
<prd-critic-hook>        stage 2.5: PRD adversarial critic
   |                       (FILLED slice #6: prd-critic + adr-critic (if ADR drafted)
   |                        loop inside to-prd; /ship verifies APPROVE before proceeding)
   v
gh issue create (PRD)    side-effect: PRD posted with label `prd`
   |
   v
to-issues --------------- stage 3: slice decomposition
   |
   v
<slicer-hook>            stage 3.5: alternative-decomposition generator
   |                       (slice #5: filled — `slicer` subagent produces
   |                        N=3 alternatives per ADR-0003 D3)
   v
<slicer-critic-hook>     stage 3.6: slice-quality critic
   |                       (slice #5: filled — `slicer-critic` picks best-of-N
   |                        with single revision loop per ADR-0003 D3)
   v
gh issue create (slices) side-effect: one sub-issue per slice with label `slice`
   |
   v
implementer (per batch) - stage 4a: slice → PR (FILLED slices 1-2 of PRD #80;
   |                       DAG-aware parallel batches for ≥2 slices,
   |                       sequential fallback for single-slice PRDs)
   v
reviewer (per slice) ---- stage 4b: PR audit + auto-merge on APPROVE
   |                       (existing flow per ADR-0002)
   v
all slices merged (or forward-blocked downstream of a needs-human slice)
```

Stage 4 (implementer + reviewer per slice) is **filled** per [ADR-0010](../../../decisions/0010-implementer-subagent-auto-pipeline.md) D2 (sequential, slice 1 of PRD #80) and D3/D4 (parallel/DAG batching + forward-block, slice 2 of PRD #80). Stage 5 (`qa-plan`) remains the terminal human checkpoint per ADR-0003 D4 and is out of `/ship`'s scope.

## Step-by-step procedure for the invoking agent

When the user invokes `/ship`:

1. **Confirm there is a grilled context to ship.**
   - Scan the conversation history for a settled design discussion (typically a recent `/grill-me` session).
   - If the context is thin or the design is still open, STOP and ask the user to grill the idea further first. Do NOT invent a PRD from nothing.

2. **Stage 2 — run `/to-prd`.**
   - Invoke the existing `to-prd` skill at `.claude/skills/to-prd/SKILL.md` unchanged.
   - Let `to-prd` synthesize the PRD from conversation context and publish it as a GitHub Issue. Capture the issue number.

3. **Stage 2.5 — `<prd-critic-hook>`.**
   - The `to-prd` skill now runs the `prd-critic` loop **internally** (≤3 rounds, APPROVE/BLOCK) before posting the PRD — see [`.claude/skills/to-prd/SKILL.md`](../to-prd/SKILL.md) and [`.claude/agents/prd-critic.md`](../../agents/prd-critic.md).
   - At this stage, verify that `to-prd` reported an APPROVE verdict (the posted PRD body should end with `> **Pipeline metadata** — Approved by prd-critic round <N>/3.`). If `to-prd` returned a round-3 BLOCK or `ESCALATE: needs-human`, STOP the pipeline — do NOT proceed to stage 3. Surface the critic's findings back to the user and recommend re-grilling.
   - Note: macro-ADRs drafted by `to-prd` ship as files alongside the PRD; they are NOT separately posted as issues. They will be committed in slice 1's PR by the implementer.

4. **Stage 3 — run `/to-issues` against the PRD issue.**
   - Invoke the existing `to-issues` skill at `.claude/skills/to-issues/SKILL.md` unchanged, passing the PRD issue number from step 2 as input.
   - Let `to-issues` produce the vertical-slice decomposition and publish one GitHub Issue per slice. Capture the slice issue numbers.

5. **Stage 3.5 — `<slicer-hook>` (filled by slice #5).**
   - Invoke the `slicer` subagent (file: `.claude/agents/slicer.md`) with the PRD issue number from step 2.
   - The subagent returns the "Slicer output for PRD #N" block — N=3 alternative decompositions per ADR-0003 D3. Pass this block forward to stage 3.6 without posting issues yet.
   - This stage is now invoked by `/to-issues` internally (per slice #5's rewrite); when `/ship` calls `/to-issues` at stage 3, this hook fires as part of that call. The hook name remains stable so future re-wiring can swap the implementation without re-shaping the orchestrator.

6. **Stage 3.6 — `<slicer-critic-hook>` (filled by slice #5).**
   - Invoke the `slicer-critic` subagent (file: `.claude/agents/slicer-critic.md`) with the PRD and the slicer's N=3 block from stage 3.5.
   - The critic scores all three decompositions, picks one with explicit tiebreak rationale, and runs **at most one** revision loop on the chosen decomposition (per ADR-0003 D3 — no re-sampling N=3 mid-loop).
   - On APPROVE: hand the `Final approved decomposition` to `/to-issues` for posting (one `gh issue create` per slice, labelled `slice`, in dependency order).
   - On BLOCK: surface the critic's blocking reasons to the user. Do NOT post slices. The autonomous pipeline halts here for this run; re-running `/ship` re-grills the slicer pair.

7. **Stage 4 — implementer + reviewer (DAG-aware parallel batches; FILLED slices 1-2 of PRD #80).**

   **7a. Build the dependency graph.** For each posted slice, parse its `## Depends on` section (slicer-critic-verified per [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D3's DAG check). Extract referenced slice issue numbers; build a directed graph (slice → its deps). Topologically sort the graph; ties between same-rank slices are broken by issue number ascending. If the parse fails or the graph has a cycle (slicer-critic should have prevented this), STOP and surface to user as `RESULT: INVALID_INPUT` in the terminal trailer — do NOT invoke any implementers.

   **7b. Dispatch loop (DAG batching per [ADR-0010](../../../decisions/0010-implementer-subagent-auto-pipeline.md) D3).** Maintain four sets: `pending` (all posted slices), `in_flight` (implementer running or PR open under reviewer), `merged` (PR merged via reviewer APPROVE), `blocked` (slice itself failed via BLOCKED/INVALID_INPUT, OR an upstream dep is in `blocked`). Loop:
     1. Compute the **ready batch**: every slice in `pending` whose `Depends on` set is a subset of `merged` (all deps merged) AND has no dep in `blocked`. Slices with a dep in `blocked` move from `pending` directly to `blocked` (forward-block — see 7d). Slices with deps still in `in_flight` stay in `pending`.
     2. **Dispatch the ready batch in parallel.** For each slice in the ready batch, invoke the `implementer` subagent via the `Agent` tool with `subagent_type: "implementer"`, passing the slice issue number. (If the subagent isn't auto-discovered, fallback to `general-purpose` with the implementer prompt loaded inline from `.claude/agents/implementer.md`.) Move each to `in_flight`. **Single-slice PRDs trivially have batch size 1** — the parallel path reduces to the sequential path naturally; no separate code path needed.
     3. **Await batch completion.** Collect each implementer's GENERATOR trailer per [ADR-0010](../../../decisions/0010-implementer-subagent-auto-pipeline.md) D7 plus the reviewer's downstream verdict for each `RESULT: SUCCESS` PR. Handle each per 7c.
     4. Loop until `pending` and `in_flight` are both empty.

   **7c. Per-slice outcome handling.** For each slice that completes within a batch:
     - **`RESULT: SUCCESS`** → PR is open with `Closes #<slice>`. Reviewer takes over per the existing ADR-0002 flow (reviewer is the gate; on APPROVE it auto-merges via `gh pr merge --squash --delete-branch`; on round-3 BLOCK it applies `needs-human` and surfaces). On reviewer APPROVE+merge → move slice from `in_flight` to `merged`. On reviewer round-3 BLOCK → treat as forward-block per 7d (the slice is now `needs-human`-labeled and its downstream must not proceed).
     - **`RESULT: BLOCKED`** → forward-block per 7d.
     - **`RESULT: INVALID_INPUT`** → forward-block per 7d. The slice is malformed and will not be retried.

   **7d. Forward-block failure handling (per [ADR-0010](../../../decisions/0010-implementer-subagent-auto-pipeline.md) D4).** When a slice fails (BLOCKED, INVALID_INPUT, or reviewer round-3 BLOCK):
     1. Apply `needs-human` label to the failed slice: `gh issue edit <N> --add-label needs-human` (skip if reviewer already applied it on round-3 BLOCK — `gh` will no-op).
     2. Compute the transitive downstream set: every slice in `pending` whose dep chain includes the failed slice. Move them all from `pending` to `blocked` (they stay open indefinitely — orchestrator does not retry, does not close).
     3. Post a summary comment on the parent PRD issue (one comment per failure event, not per blocked slice): `gh issue comment <PRD-N> --body "slice #<N> blocked: <reason from trailer>; downstream slices blocked: [#<M>, #<L>, ...]"`. Mirrors reviewer's I5 surface.
     4. **In-flight parallel siblings finish normally** — do NOT cancel them. The dispatch loop's next iteration awaits their completion; their PRs proceed to reviewer per the normal path. This honors ADR-0010 D4's "in-flight parallel slices finish normally" semantics.
     5. **Slices with OTHER unmet deps proceed normally** through their natural batches once those deps merge. Failure is locally contained to the failed slice's downstream cone.

   **7e. Collect terminal state.** For the terminal report (step 8), capture: each `PR_URL` from SUCCESS slices (whether merged or under-review), the `blocked` set (for `BLOCKED_SLICES`), and the snapshot of `in_flight` at the moment the FIRST failure was observed (for `IN_FLIGHT_AT_FAILURE` — empty if no failures occurred).

8. **Report back to the user.**
   - Print the PRD issue URL, the list of slice issue URLs, and the list of merged-or-open implementation PR URLs.
   - If any slice was BLOCKED, name the failed slice(s), the `needs-human` PR(s), and which downstream slices were skipped.
   - The free-form narrative above stays domain-shaped per PRD #28 §6 OQ#2 — `/ship`'s report body is **not** itself a canonical template.
   - End the terminal report with the canonical **GENERATOR trailer** (per [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D1c and the "Output-shape standard" section of CLAUDE.md), as a fenced code block:

   ```
   RESULT: SUCCESS | STOPPED | INVALID_INPUT
   REASON: <one sentence — e.g., "PRD posted with N slice sub-issues; M implementation PRs merged" or "prd-critic round-3 BLOCK; pipeline halted" or "no grilled context to ship" or "PRD posted; K slices merged, J slices forward-blocked by #N">
   ARTIFACTS: <PRD URL>, <slice URLs comma-separated>
   SLICE_COUNT: <N>
   IMPLEMENTATION_PRS: <comma-separated list of merged/open PR URLs returned by implementer invocations; empty if pipeline halted before stage 4>
   BLOCKED_SLICES: <comma-separated list of slice numbers in the `blocked` set per step 7d — failed slices PLUS forward-blocked downstream; empty if no failures>
   IN_FLIGHT_AT_FAILURE: <comma-separated list of slice numbers that were in `in_flight` at the moment the FIRST failure was observed per step 7e; empty if no failures>
   ```

   `SLICE_COUNT` and `IMPLEMENTATION_PRS` are **per-agent extensions** appended after `ARTIFACTS`; consumers read them to know how many sub-issues were posted and which PRs the auto-invoked implementer produced, without re-parsing `ARTIFACTS`. `BLOCKED_SLICES` and `IN_FLIGHT_AT_FAILURE` are **per-agent extensions added in slice 2 of PRD #80** (per [ADR-0010](../../../decisions/0010-implementer-subagent-auto-pipeline.md) D4) so that human triage of forward-blocked work can find every stuck slice without crawling the PRD's sub-issue list, and so post-run audits can correlate which parallel siblings were running at the moment of failure. On `RESULT: STOPPED` or `RESULT: INVALID_INPUT`, `ARTIFACTS` may be partial (e.g., just the PRD URL if `/to-issues` halted) or empty (e.g., no grilled context); `SLICE_COUNT` is `0`; `IMPLEMENTATION_PRS` is empty; `BLOCKED_SLICES` and `IN_FLIGHT_AT_FAILURE` are empty (no implementer ever ran).

## Hooks — what future slices fill in

The hook names below are stable contracts. A future slice can fill a hook by name without re-reading this orchestrator spec — it only needs to know the stage's input and output.

| Hook name              | Slice that fills it | Replaces no-op with                                              |
|------------------------|---------------------|------------------------------------------------------------------|
| `<prd-critic-hook>`    | **FILLED (slice #6)** | `prd-critic` subagent loop runs inside `to-prd` (≤3 rounds, APPROVE/BLOCK); `/ship` verifies APPROVE before stage 3 |
| `<slicer-hook>`        | **FILLED (slice #5)** | `slicer` subagent producing N=3 alternative decompositions       |
| `<slicer-critic-hook>` | **FILLED (slice #5)** | `slicer-critic` subagent picking best-of-N + single revision loop |

Slice 1 left all three as pass-through to validate the chain end-to-end before any critic logic was introduced (walking-skeleton discipline from CLAUDE.md rule #2). Slice #5 filled the two slicer hooks and slice #6 filled the prd-critic hook — all three hooks are now live.

## What this slice deliberately does NOT do

Listed here so future contributors don't sneak them in (CLAUDE.md rule #1, YAGNI):

- No `prd-critic`, `slicer`, or `slicer-critic` subagent files (separate slices).
- No edits to `to-prd` or `to-issues` skill bodies (separate slices).
- No edits to `reviewer.md` (separate slice — adds I4/I5 enforcement and `Closes #N`).
- No edits to `CLAUDE.md` (separate slice — 3-tier hierarchy, branch naming, PRD template).
- No resumability from a failed stage. If a stage fails (stages 2/2.5/3/3.5/3.6 — i.e., PRD authoring or slice decomposition), the user re-runs `/ship` from scratch or invokes the failing stage's skill manually. (Rabbit-hole per PRD #3 §6.) Stage 4 forward-block (per step 7d) is NOT a stage failure — it's per-slice failure handling within stage 4 and is fully autonomous.
- No CI-driven implementer invocation (PRD-CI future per backlog #63).
- No auto-rebase of merge conflicts between parallel sibling PRs in the same batch (deferred per [ADR-0010](../../../decisions/0010-implementer-subagent-auto-pipeline.md) Open Questions; slicer-critic INVEST Independence should make this rare).
- No concurrency cap as a configurable parameter (YAGNI — default is unbounded; orchestrator dispatches all ready slices).
- No cancellation of in-flight parallel siblings when one slice fails (per [ADR-0010](../../../decisions/0010-implementer-subagent-auto-pipeline.md) D4 — in-flight siblings finish normally).
- No daemon, no merge-queue integration. (PRD #3 §3 non-goals.)

## References

- PRD #3 — *Autonomous multi-stage pipeline with adversarial critics* (the spec this skill implements).
- This slice's issue: #4 — *slice 1: ship orchestrator skeleton (walking skeleton)*.
- [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) — D2 (five-stage pipeline), D4 (no human gates between stages — closed end-to-end by ADR-0010), D6 (skills vs subagents), D7 (`/ship` orchestrator skill, lightweight v1).
- [ADR-0010](../../../decisions/0010-implementer-subagent-auto-pipeline.md) — D2 (/ship auto-invokes implementer), D3 (parallel-where-independent DAG batching — slice 2 of PRD #80, step 7a/7b), D4 (forward-block failure handling — step 7d), D5 (sequential walking-skeleton; parallel slice 2 — now both filled).
- [ADR-0002](../../../decisions/0002-autonomous-merge-policy.md) — the autonomous loop pattern this pipeline generalizes; reviewer's auto-merge on APPROVE is the handoff target after implementer SUCCESS.
- Sibling skills the chain calls: [`.claude/skills/to-prd/SKILL.md`](../to-prd/SKILL.md), [`.claude/skills/to-issues/SKILL.md`](../to-issues/SKILL.md).
- Subagent invoked at stage 4: [`.claude/agents/implementer.md`](../../agents/implementer.md) (auto-invoked by step 7 above per ADR-0010 D2).
