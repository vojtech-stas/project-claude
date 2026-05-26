---
title: pipeline stages — the autonomous PRD-to-merge chain
summary: The HOW of every stage in the autonomous pipeline — from /grill-me intake to /qa-plan acceptance — synthesizing CLAUDE.md "Pipeline operational logic" and the /ship orchestrator's stage map; each generation stage is paired with an adversarial critic per ADR-0003 D2.
tags: [pipeline, orchestration, ship, topic]
type: topic
last_updated: 2026-05-26
sources:
  - CLAUDE.md
  - .claude/skills/ship/SKILL.md
  - decisions/0003-autonomous-pipeline-with-critics.md
  - decisions/0010-implementer-subagent-auto-pipeline.md
---

# pipeline stages

The canonical synthesis of the autonomous pipeline's operational logic — the HOW for each stage from idea-grilling to PRD acceptance. Authority: [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D2 (every generation stage is paired with an adversarial critic), [ADR-0010](../../../decisions/0010-implementer-subagent-auto-pipeline.md) (auto-implementer at stage 4 + DAG-aware parallel batching). This topic page is the **canonical KB-layer home of pipeline operational logic** — content is the synthesis of two source locations on origin/main as of 2026-05-26:

1. `CLAUDE.md` "Pipeline operational logic" section (the project-rules shell — slated for removal in T6 per [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D10 step 6; see the T6-cleanup captured issue raised alongside this slice).
2. `.claude/skills/ship/SKILL.md` "The chain" + step-by-step procedure (the orchestrator's executable map).

Until T6 ships, edits to ANY of the three locations (this page + CLAUDE.md "Pipeline operational logic" + ship.md stages) must update all three to prevent drift.

**Out of scope (deferred to sibling topic).** The canonical output-shape standard (verdict template, CRITIC trailer, GENERATOR trailer) lives in [[topics/output-shapes]] — this topic links there rather than restating it. Per PRD #273 §6 rabbit-holes ("defer disambiguation to topic-cleanup PRD if needed"), pipeline-stages.md focuses on stage operational logic; output-shapes.md focuses on the schema each agent emits.

## The chain (high-level)

The autonomous pipeline runs in five sequential stages with one human checkpoint at intake (`/grill-me`) and one at acceptance (`/qa-plan`). There are no human gates between stages per [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D4 (closed end-to-end by [ADR-0010](../../../decisions/0010-implementer-subagent-auto-pipeline.md) — implementer at stage 4 was the residual gap).

```
grill-me  (human intake — design conversation; not part of /ship)
   |
   v
to-prd ----------------- stage 2: PRD authoring
   |
   v
<prd-critic-hook>        stage 2.5: PRD adversarial critic
   |                       (prd-critic + adr-critic in parallel when ADR drafted;
   |                        ≤3-round APPROVE/BLOCK loop inside to-prd;
   |                        /ship verifies APPROVE before proceeding)
   v
gh issue create (PRD)    side-effect: PRD posted with label `prd`
   |
   v
to-issues --------------- stage 3: slice decomposition (thin wrapper)
   |
   v
<slicer-hook>            stage 3.5: alternative-decomposition generator
   |                       (slicer subagent produces N=3 per ADR-0003 D3;
   |                        N=1 degenerate carveout per ADR-0013)
   v
<slicer-critic-hook>     stage 3.6: slice-quality critic
   |                       (slicer-critic picks best-of-N + single revision)
   v
gh issue create (slices) side-effect: one sub-issue per slice with label `slice`
   |
   v
implementer (per batch) - stage 4a: slice → PR
   |                       (DAG-aware parallel batches for ≥2 independent slices,
   |                        sequential fallback for single-slice PRDs)
   v
reviewer (per slice) ---- stage 4b: PR audit + auto-merge on APPROVE
   |                       (gh pr merge --squash --delete-branch per ADR-0002;
   |                        round-3 BLOCK applies needs-human + forward-blocks)
   v
all slices merged
   |
   v
qa-plan                  stage 5: PRD acceptance (terminal human checkpoint)
                           (writer extracts AC + dispatches qa-tester; PRD auto-closes
                            on all-PASS + all-judgment-ACCEPT per ADR-0020 D5/D10)
```

Stage 4 (implementer + reviewer per slice) is **filled** per [ADR-0010](../../../decisions/0010-implementer-subagent-auto-pipeline.md) D2 (sequential, slice 1 of PRD #80) and D3/D4 (parallel/DAG batching + forward-block, slice 2 of PRD #80). Stage 5 (`qa-plan`) remains the terminal human checkpoint per [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D4 and is out of `/ship`'s scope.

## Session-level enforcement hooks

Per [ADR-0023](../../../decisions/0023-validation-and-notification-hooks-extension.md), extending [ADR-0015](../../../decisions/0015-claude-code-hooks-adoption.md) D6. Four hook surfaces frame the pipeline at session-start and at tool-invocation time:

- **`SessionStart`** — injects `additionalContext` with branch + divergence vs `origin/main` + recent commits + open slice/PR/captured counts; mitigates the recurring stale-worktree false-alarm (#173).
- **`PreToolUse(Edit|MultiEdit|Write)`** — emits `permissionDecision: "ask"` when main agent (not subagent) writes a tracked file, mechanically escalating CLAUDE.md rule #10 (main-agent meta-output discipline).
- **`PreToolUse(Bash)`** — emits `permissionDecision: "deny"` on `git push ... origin main` (any flavor), enforcing CLAUDE.md rule #4 (never push to main).
- **`UserPromptSubmit`** — nudges feature-request-shaped prompts toward `/grill-me` before `/ship`.

Hooks are logging/validation/notification only (per CLAUDE.md rule #12 + [ADR-0015](../../../decisions/0015-claude-code-hooks-adoption.md)) — they may NOT auto-invoke skills or subagents (technically impossible).

## Stage-by-stage operational logic

### Stage 1 — `/grill-me` (idea capture) — human intake

See [`.claude/skills/grill-me/SKILL.md`](../../../.claude/skills/grill-me/SKILL.md). Invoked via `/grill-me` or natural-language match. Interviews user one question at a time, recommends an answer for each, walks the decision tree. Not part of `/ship` — the user runs `/grill-me` first to settle the design, then runs `/ship` to hand off.

**Output:** a settled design conversation in transcript form, sufficient for `/to-prd` to synthesize a 6-section PRD without additional interview.

### Stage 2 — `/to-prd` (PRD authoring) + stage 2.5 prd-critic + adr-critic

See [`.claude/skills/to-prd/SKILL.md`](../../../.claude/skills/to-prd/SKILL.md) — **canonical home of the 6-section PRD template** (Problem / Goal / Non-goals / Appetite / Solution sketch / Rabbit-holes & Open questions). The skill invokes [`prd-critic`](../../../.claude/agents/prd-critic.md) in a ≤3-round APPROVE/BLOCK loop before posting, and drafts any warranted macro-ADRs alongside the PRD per [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D8.

**Step 2 invocation pattern by /ship** (verbatim from [`ship.md`](../../../.claude/skills/ship/SKILL.md) step 2):

- Invoke the existing `to-prd` skill at `.claude/skills/to-prd/SKILL.md` unchanged.
- Let `to-prd` synthesize the PRD from conversation context and publish it as a GitHub Issue. Capture the issue number.

**Stage 2.5 — adr-critic in parallel** ([`adr-critic`](../../../.claude/agents/adr-critic.md)). Invoked by `/to-prd` in parallel with `prd-critic` whenever a macro-ADR is drafted alongside a PRD (per [ADR-0004](../../../decisions/0004-bypass-prevention.md) D1). Mirrors `prd-critic`'s ≤3-round APPROVE/BLOCK loop and I5 escalation surface; rubric is ADR-specific (convention compliance, cross-ADR consistency, supersession explicit by D-ID, bootstrap-mode policy acknowledged, immutability respected). **Both critics must APPROVE** before `/to-prd` posts — this is the [[concepts/glossary/joint-approve-gate]] per [ADR-0004](../../../decisions/0004-bypass-prevention.md) D1.

**Step 2.5 verification by /ship** (verbatim from [`ship.md`](../../../.claude/skills/ship/SKILL.md) step 3). The `to-prd` skill now runs the `prd-critic` loop **internally** (≤3 rounds, APPROVE/BLOCK) before posting the PRD. `/ship` verifies that `to-prd` reported an APPROVE verdict — the posted PRD body should end with `> **Pipeline metadata** — Approved by prd-critic round <N>/3.`. If `to-prd` returned a round-3 BLOCK or `ESCALATE: needs-human`, STOP the pipeline — do NOT proceed to stage 3. Surface the critic's findings back to the user and recommend re-grilling. Macro-ADRs drafted by `to-prd` ship as files alongside the PRD; they are NOT separately posted as issues — they will be committed in slice 1's PR by the implementer.

Normally invoked indirectly via `/ship`.

### Stage 3 — `/to-issues` (slice decomposition wrapper) + stages 3.5 + 3.6 slicer pair

See [`.claude/skills/to-issues/SKILL.md`](../../../.claude/skills/to-issues/SKILL.md). Thin wrapper that delegates to the slicer pair below. Invocation shape `/to-issues` preserved; new internals. Output: GitHub Issues (one per vertical slice) with the `slice` label and sub-issue link to the parent PRD.

**Step 3 invocation pattern by /ship** (verbatim from [`ship.md`](../../../.claude/skills/ship/SKILL.md) step 4):

- Invoke the existing `to-issues` skill at `.claude/skills/to-issues/SKILL.md` unchanged, passing the PRD issue number from step 2 as input.
- Let `to-issues` produce the vertical-slice decomposition and publish one GitHub Issue per slice. Capture the slice issue numbers.

**Stage 3.5 — slicer** ([[entities/subagents/slicer]]) (verbatim from [`ship.md`](../../../.claude/skills/ship/SKILL.md) step 5). Invoke the `slicer` subagent (file: `.claude/agents/slicer.md`) with the PRD issue number from step 2. The subagent returns the "Slicer output for PRD #N" block — N=3 alternative decompositions per [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D3, or N=1 with explicit rationale per [ADR-0013](../../../decisions/0013-slicer-n3-contract-refined.md) for degenerate cases where all candidates would have bit-identical post-merge end-state. Pass this block forward to stage 3.6 without posting issues yet. This stage is invoked by `/to-issues` internally; when `/ship` calls `/to-issues` at stage 3, this hook fires as part of that call. The hook name remains stable so future re-wiring can swap the implementation without re-shaping the orchestrator.

The slicer applies hamburger-vertical check on slice 1 of every decomposition, SPIDR split-fallback hints on near-cap slices, and cascade-doc identification per [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D3 — see [[entities/subagents/slicer]] for the full check list.

**Stage 3.6 — slicer-critic** ([[entities/subagents/slicer-critic]]) (verbatim from [`ship.md`](../../../.claude/skills/ship/SKILL.md) step 6). Invoke the `slicer-critic` subagent (file: `.claude/agents/slicer-critic.md`) with the PRD and the slicer's N=3 block from stage 3.5. The critic scores all three decompositions against the 10-criterion rubric, picks one with explicit tiebreak rationale, and runs **at most one** revision loop on the chosen decomposition (per [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D3 — no re-sampling N=3 mid-loop). On APPROVE: hand the `Final approved decomposition` to `/to-issues` for posting (one `gh issue create` per slice, labelled `slice`, in dependency order). On BLOCK: surface the critic's blocking reasons to the user. Do NOT post slices. The autonomous pipeline halts here for this run; re-running `/ship` re-grills the slicer pair.

### Stage 4 — implementer + reviewer (auto-dispatched per slice)

**Stage 4a — implementer** ([`.claude/agents/implementer.md`](../../../.claude/agents/implementer.md)). Auto-invoked by the `/ship` orchestrator at stage 4 once `slicer-critic` has posted the slice sub-issues (per [ADR-0010](../../../decisions/0010-implementer-subagent-auto-pipeline.md) D2). For each slice, `implementer` reads the slice body + parent PRD + relevant ADRs, claims the slice (I2 — `gh issue edit <slice> --add-assignee @me`), creates a branch per CLAUDE.md naming, implements within scope, commits per [[concepts/glossary/conventional-commits]], and opens a PR with `Closes #<slice>`. Tool boundaries per [ADR-0010](../../../decisions/0010-implementer-subagent-auto-pipeline.md) D6 (Read/Edit/Write/Bash/Glob/Grep; NOT Agent). TDD (Matt's `tdd` skill) is a future enhancement layered atop this subagent.

**DAG-aware parallel batching per ADR-0010 D3** (verbatim from [`ship.md`](../../../.claude/skills/ship/SKILL.md) step 7b). `/ship` builds the dependency graph by parsing each slice's `## Depends on` section (slicer-critic-verified per [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D3's DAG check). Extract referenced slice issue numbers; build a directed graph (slice → its deps). Topologically sort the graph; ties between same-rank slices are broken by issue number ascending. If the parse fails or the graph has a cycle (slicer-critic should have prevented this), STOP and surface to user as `RESULT: INVALID_INPUT` in the terminal trailer — do NOT invoke any implementers.

Maintain four sets: `pending` (all posted slices), `in_flight` (implementer running or PR open under reviewer), `merged` (PR merged via reviewer APPROVE), `blocked` (slice itself failed via BLOCKED/INVALID_INPUT, OR an upstream dep is in `blocked`). Loop:

1. Compute the **ready batch**: every slice in `pending` whose `Depends on` set is a subset of `merged` (all deps merged) AND has no dep in `blocked`. Slices with a dep in `blocked` move from `pending` directly to `blocked` (forward-block — see below). Slices with deps still in `in_flight` stay in `pending`.
2. **Dispatch the ready batch in parallel.** For each slice in the ready batch, invoke the `implementer` subagent via the `Agent` tool with `subagent_type: "implementer"`, passing the slice issue number. (If the subagent isn't auto-discovered, fallback to `general-purpose` with the implementer prompt loaded inline from `.claude/agents/implementer.md`.) Move each to `in_flight`. **Single-slice PRDs trivially have batch size 1** — the parallel path reduces to the sequential path naturally; no separate code path needed.
3. **Await batch completion.** Collect each implementer's GENERATOR trailer per [ADR-0010](../../../decisions/0010-implementer-subagent-auto-pipeline.md) D7 plus the reviewer's downstream verdict for each `RESULT: SUCCESS` PR.
4. Loop until `pending` and `in_flight` are both empty.

**Per-slice outcome handling** (verbatim from ship.md step 7c). For each slice that completes within a batch:

- **`RESULT: SUCCESS`** → PR is open with `Closes #<slice>`. Reviewer takes over per the existing ADR-0002 flow (reviewer is the gate; on APPROVE it auto-merges via `gh pr merge --squash --delete-branch`; on round-3 BLOCK it applies `needs-human` and surfaces). On reviewer APPROVE+merge → move slice from `in_flight` to `merged`. On reviewer round-3 BLOCK → treat as forward-block (the slice is now `needs-human`-labeled and its downstream must not proceed).
- **`RESULT: BLOCKED`** → forward-block.
- **`RESULT: INVALID_INPUT`** → forward-block. The slice is malformed and will not be retried.

**Stage 4b — reviewer** ([[entities/subagents/reviewer]]). Per [ADR-0002](../../../decisions/0002-autonomous-merge-policy.md) (autonomous merge at PR level) and [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D4 (no human gates between pipeline stages), `reviewer` is the **sole gate per PR**. Reads PR body + diff + CLAUDE.md + ADRs + linked slice issue. Posts a structured verdict comment via `gh pr comment`. On APPROVE → auto-merges with `gh pr merge --squash --delete-branch`. On BLOCK → returns PR to implementer for revision; on round-3 BLOCK → applies `needs-human` label and comments on the parent PRD (I5 escalation surface).

**Forward-block failure handling per ADR-0010 D4.** When a slice fails (BLOCKED, INVALID_INPUT, or reviewer round-3 BLOCK):

1. Apply `needs-human` label to the failed slice.
2. Compute the transitive downstream set: every slice in `pending` whose dep chain includes the failed slice. Move them all from `pending` to `blocked` (they stay open indefinitely — orchestrator does not retry, does not close).
3. Post a summary comment on the parent PRD issue (one comment per failure event, not per blocked slice).
4. **In-flight parallel siblings finish normally** — do NOT cancel them. The dispatch loop's next iteration awaits their completion; their PRs proceed to reviewer per the normal path. This honors [ADR-0010](../../../decisions/0010-implementer-subagent-auto-pipeline.md) D4's "in-flight parallel slices finish normally" semantics.
5. **Slices with OTHER unmet deps proceed normally** through their natural batches once those deps merge. Failure is locally contained to the failed slice's downstream cone.

**Terminal state collection** (verbatim from [`ship.md`](../../../.claude/skills/ship/SKILL.md) step 7e). For the terminal report, `/ship` captures: each `PR_URL` from SUCCESS slices (whether merged or under-review), the `blocked` set (for `BLOCKED_SLICES`), and the snapshot of `in_flight` at the moment the FIRST failure was observed (for `IN_FLIGHT_AT_FAILURE` — empty if no failures occurred). These fields are emitted as per-agent extensions on the `/ship` GENERATOR trailer; the trailer schema lives in [[topics/output-shapes]].

### Stage 5 — `/qa-plan` (PRD acceptance, terminal human checkpoint)

See [`.claude/skills/qa-plan/SKILL.md`](../../../.claude/skills/qa-plan/SKILL.md). Invoked via `/qa-plan <PRD#>` when all `Closes #<slice>` PRs for a PRD have merged. Per [ADR-0020](../../../decisions/0020-qa-automation-writer-executor.md), QA automation Tier 1 splits into a writer (`/qa-plan` skill running in main-agent context) and an executor ([`qa-tester`](../../../.claude/agents/qa-tester.md) subagent running in isolated context).

The writer LLM-extracts each PRD §2 acceptance criterion into a bash check or `JUDGMENT` flag per [ADR-0020](../../../decisions/0020-qa-automation-writer-executor.md) D2, persists the structured plan as a PRD comment per D4, dispatches `qa-tester` via the `Agent` tool to walk the plan one-by-one, then renders any `JUDGMENT` / `EXTRACT_FAILED` rows via `AskUserQuestion` and auto-closes the PRD on all-PASS + all-judgment-ACCEPT per D5. On any mechanical FAIL the writer halts with an `AskUserQuestion` offering accept-FAIL / reopen-for-fix / cull-as-won't-fix.

The executor (`qa-tester`) is a GENERATOR per [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D1c + [ADR-0020](../../../decisions/0020-qa-automation-writer-executor.md) D9 — tool boundaries Read/Bash/Grep only (NO Agent / Write / Edit / AskUserQuestion per [ADR-0020](../../../decisions/0020-qa-automation-writer-executor.md) D3). It returns a per-criterion verdict table + canonical GENERATOR trailer with `PASS_COUNT` / `FAIL_COUNT` / `JUDGMENT_COUNT` / `EXTRACT_FAILED_COUNT` per-agent extensions (see [[topics/output-shapes]]). The writer's own trailer adds a `PRD_DISPOSITION` extension naming the resulting state (`closed-completed` / `reopened-for-fix` / `culled` / `left-open-pending-fix`).

**This is the terminal human checkpoint** in the autonomous pipeline per [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D4, refined per [ADR-0020](../../../decisions/0020-qa-automation-writer-executor.md) D10 — humans judge subjective outcomes via `AskUserQuestion`, agents handle mechanical verification. Honors the 6-critic-cap per [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7 (qa-tester is a generator, not a 7th critic).

## Hook contract (extensibility points)

The `<prd-critic-hook>` / `<slicer-hook>` / `<slicer-critic-hook>` names from the chain map are **stable contracts**. A future slice can fill or replace a hook by name without re-reading the orchestrator spec — it only needs to know the stage's input and output.

| Hook name              | Current state | Replaces no-op with                                              |
|------------------------|---------------|------------------------------------------------------------------|
| `<prd-critic-hook>`    | **FILLED**    | `prd-critic` subagent loop runs inside `to-prd` (≤3 rounds, APPROVE/BLOCK); `/ship` verifies APPROVE before stage 3 |
| `<slicer-hook>`        | **FILLED**    | `slicer` subagent producing N=3 alternative decompositions       |
| `<slicer-critic-hook>` | **FILLED**    | `slicer-critic` subagent picking best-of-N + single revision loop |

Slice 1 of PRD #3 left all three as pass-through to validate the chain end-to-end before any critic logic was introduced (walking-skeleton discipline per CLAUDE.md rule #2 + [[patterns/walking-skeleton]]). The hooks were filled in subsequent slices; all three are now live.

## What the pipeline deliberately does NOT do

Listed here so future contributors don't sneak them in (CLAUDE.md rule #1, YAGNI):

- **No resumability from a failed stage.** If a stage fails (stages 2/2.5/3/3.5/3.6 — i.e., PRD authoring or slice decomposition), the user re-runs `/ship` from scratch or invokes the failing stage's skill manually. Stage 4 forward-block (per ADR-0010 D4) is NOT a stage failure — it's per-slice failure handling within stage 4 and is fully autonomous.
- **No CI-driven implementer invocation** (PRD-CI future per backlog #63).
- **No auto-rebase of merge conflicts between parallel sibling PRs in the same batch** (deferred per [ADR-0010](../../../decisions/0010-implementer-subagent-auto-pipeline.md) Open Questions; slicer-critic INVEST Independence should make this rare).
- **No concurrency cap as a configurable parameter** (YAGNI — default is unbounded; orchestrator dispatches all ready slices).
- **No cancellation of in-flight parallel siblings when one slice fails** (per [ADR-0010](../../../decisions/0010-implementer-subagent-auto-pipeline.md) D4 — in-flight siblings finish normally).
- **No daemon, no merge-queue integration** (PRD #3 §3 non-goals).
- **No human gates between stages 2-4** (per [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D4 closed end-to-end by [ADR-0010](../../../decisions/0010-implementer-subagent-auto-pipeline.md)).

## Session continuity — how new sessions resume mid-pipeline

No formal handoff document. New Claude Code sessions reconstruct state from **live state** per [ADR-0006](../../../decisions/0006-backlog-and-session-continuity.md) D2:

- `git log --oneline -10` — recent commits / branch state
- `gh issue list --state open --label slice` — in-flight slices
- `gh pr list --state open` — in-flight PRs (work under review)
- `gh issue list --label backlog` — forward queue (queued for future PRDs)
- Project board #2 column states — visual progress of in-flight work
- `tail .claude/logs/workflow-events.jsonl` — recent agent/bash/session-stop events from the workflow event log (per [ADR-0016](../../../decisions/0016-workflow-event-log-jsonl.md))

The natural pipeline milestones (end of `/grill-me`, `/ship`, `/qa-plan`) always leave a new session in a state where live reconstruction is sufficient. Mid-task interruption (mid-grill or mid-slice) loses conversational context regardless of mechanism; this is an accepted trade-off per [ADR-0006](../../../decisions/0006-backlog-and-session-continuity.md) D2.

## Promotion: backlog → PRD

When a `backlog`-labeled issue is ready for full grilling:

1. `gh issue edit <N> --remove-label backlog --add-label prd`
2. `/grill-me #<N>` to refine the body into a 6-section PRD (per [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D1)
3. After grill, `/ship` continues the autonomous pipeline as usual

## Why this matters

Per [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md), the pipeline exists because **human bandwidth is the limiter** on senior-engineer-overseen agent work. By pairing every generation stage with an adversarial critic and removing all human gates between intake and acceptance, a single `/grill-me` + `/ship` invocation produces a posted PRD, sliced sub-issues, opened PRs, reviewed PRs, and squash-merged PRs without further human turn-taking. The human checkpoints (`/grill-me` at idea-input, `/qa-plan` at PRD-acceptance) bookend the autonomous middle.

Per [ADR-0010](../../../decisions/0010-implementer-subagent-auto-pipeline.md), the residual gap was at stage 4 — until that ADR, the implementer was the only stage requiring manual invocation. Closing it made the pipeline end-to-end autonomous in practice, not just in principle.

## Edges

- **defines:** none (synthesis topic; canonical authorities are CLAUDE.md and ship.md, slated for thinning in T6)
- **part_of:** [[entities/subagents/slicer]]
- **part_of:** [[entities/subagents/slicer-critic]]
- **part_of:** [[entities/subagents/reviewer]]
- **related_to:** [[topics/output-shapes]]
- **related_to:** [[topics/reviewer-philosophy]]
- **related_to:** [[concepts/glossary/prd]]
- **related_to:** [[concepts/glossary/slice]]
- **related_to:** [[concepts/glossary/critic]]
- **related_to:** [[concepts/glossary/joint-approve-gate]]
- **related_to:** [[concepts/glossary/walking-skeleton-glossary]]
- **related_to:** [[concepts/glossary/conventional-commits]]
- **related_to:** [[patterns/walking-skeleton]]
- **related_to:** [[patterns/cascade-doc-check]]
- **related_to:** [[patterns/n1-degenerate-carveout]]
