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
   |                       (slice 1: pass-through no-op)
   |                       (filled by a future slice — see "Hooks" below)
   v
gh issue create (PRD)    side-effect: PRD posted with label `prd`
   |
   v
to-issues --------------- stage 3: slice decomposition
   |
   v
<slicer-hook>            stage 3.5: alternative-decomposition generator
   |                       (slice 1: pass-through no-op — to-issues already
   |                        produces one decomposition; future slice swaps in
   |                        N=3 alternatives via the slicer subagent)
   v
<slicer-critic-hook>     stage 3.6: slice-quality critic
   |                       (slice 1: pass-through no-op)
   |                       (filled by a future slice — see "Hooks" below)
   v
gh issue create (slices) side-effect: one sub-issue per slice with label `slice`
```

Stages 4 (implementer + reviewer per slice) and 5 (`qa-plan`) are out of `/ship`'s scope in this slice. The human runs them separately for now.

## Step-by-step procedure for the invoking agent

When the user invokes `/ship`:

1. **Confirm there is a grilled context to ship.**
   - Scan the conversation history for a settled design discussion (typically a recent `/grill-me` session).
   - If the context is thin or the design is still open, STOP and ask the user to grill the idea further first. Do NOT invent a PRD from nothing.

2. **Stage 2 — run `/to-prd`.**
   - Invoke the existing `to-prd` skill at `.claude/skills/to-prd/SKILL.md` unchanged.
   - Let `to-prd` synthesize the PRD from conversation context and publish it as a GitHub Issue. Capture the issue number.

3. **Stage 2.5 — `<prd-critic-hook>`.**
   - **Slice 1 behaviour: pass-through no-op.** Do nothing; proceed to stage 3.
   - Future slice will: invoke a `prd-critic` subagent against the PRD; on BLOCK loop back to `to-prd` for revision (max 3 rounds); on APPROVE proceed. Do not implement that logic in this slice.

4. **Stage 3 — run `/to-issues` against the PRD issue.**
   - Invoke the existing `to-issues` skill at `.claude/skills/to-issues/SKILL.md` unchanged, passing the PRD issue number from step 2 as input.
   - Let `to-issues` produce the vertical-slice decomposition and publish one GitHub Issue per slice. Capture the slice issue numbers.

5. **Stage 3.5 — `<slicer-hook>`.**
   - **Slice 1 behaviour: pass-through no-op.** `to-issues` is the slicer for this slice; do nothing extra.
   - Future slice will: replace this hook with a `slicer` subagent that produces N=3 alternative decompositions before posting (per ADR-0003 D3). Do not implement that logic in this slice.

6. **Stage 3.6 — `<slicer-critic-hook>`.**
   - **Slice 1 behaviour: pass-through no-op.** Do nothing; the chain ends here.
   - Future slice will: invoke a `slicer-critic` subagent against the N decompositions, pick the best with rationale, run a single revision loop, then post the chosen slices. Do not implement that logic in this slice.

7. **Report back to the user.**
   - Print the PRD issue URL and the list of slice issue URLs.
   - Tell the user the slices are now ready for the implementer-reviewer loop (one slice per PR), and that `qa-plan` is the next human-facing step once all slices merge.

## Hooks — what future slices fill in

The hook names below are stable contracts. A future slice can fill a hook by name without re-reading this orchestrator spec — it only needs to know the stage's input and output.

| Hook name              | Slice that fills it | Replaces no-op with                                              |
|------------------------|---------------------|------------------------------------------------------------------|
| `<prd-critic-hook>`    | future PRD-critic slice | `prd-critic` subagent loop (≤3 rounds, APPROVE/BLOCK) on the draft PRD before posting |
| `<slicer-hook>`        | future slicer slice | `slicer` subagent producing N=3 alternative decompositions       |
| `<slicer-critic-hook>` | future slicer-critic slice | `slicer-critic` subagent picking best-of-N + single revision loop |

Slice 1 deliberately leaves all three as pass-through so the chain is observable end-to-end before any critic logic is introduced. This is the walking-skeleton discipline from CLAUDE.md rule #2.

## What this slice deliberately does NOT do

Listed here so future contributors don't sneak them in (CLAUDE.md rule #1, YAGNI):

- No `prd-critic`, `slicer`, or `slicer-critic` subagent files (separate slices).
- No edits to `to-prd` or `to-issues` skill bodies (separate slices).
- No edits to `reviewer.md` (separate slice — adds I4/I5 enforcement and `Closes #N`).
- No edits to `CLAUDE.md` (separate slice — 3-tier hierarchy, branch naming, PRD template).
- No resumability from a failed stage. If a stage fails, the user re-runs `/ship` from scratch or invokes the failing stage's skill manually. (Rabbit-hole per PRD #3 §6.)
- No parallelism, no daemon, no merge-queue integration. (PRD #3 §3 non-goals.)
- No `implementer` invocation. Stage 4 of the pipeline (per ADR-0003 D2) is still human-triggered.

## References

- PRD #3 — *Autonomous multi-stage pipeline with adversarial critics* (the spec this skill implements).
- This slice's issue: #4 — *slice 1: ship orchestrator skeleton (walking skeleton)*.
- [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) — D2 (five-stage pipeline), D6 (skills vs subagents), D7 (`/ship` orchestrator skill, lightweight v1).
- [ADR-0002](../../../decisions/0002-autonomous-merge-policy.md) — the autonomous loop pattern this pipeline generalizes.
- Sibling skills the chain calls: [`.claude/skills/to-prd/SKILL.md`](../to-prd/SKILL.md), [`.claude/skills/to-issues/SKILL.md`](../to-issues/SKILL.md).
