# ADR-0010: Implementer subagent + /ship auto-invoke closes ADR-0003 D4's autonomy gap

- **Status:** Accepted
- **Date:** 2026-05-19
- **Extends:** [ADR-0003](0003-autonomous-pipeline-with-critics.md) D2 (fills the implementer stage 4 hook); [ADR-0003](0003-autonomous-pipeline-with-critics.md) D4 (closes the residual human-gate violation); honors [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 (no new critics)
- **Supersedes:** none. [ADR-0003](0003-autonomous-pipeline-with-critics.md) D7 ("/ship orchestrator skill, lightweight v1") is extended-not-superseded by this ADR's D2 — D7's walking-skeleton acknowledgement ("Stage 4 ... is still human-triggered ... for now") was always temporary; this ADR makes good on the "for now".

## Context

[ADR-0003](0003-autonomous-pipeline-with-critics.md) D2 designed a 5-stage autonomous pipeline; D4 explicitly stated *"the human enters at `/grill-me` (input) and `/qa-plan` (acceptance), nothing in between"*. The walking-skeleton `/ship` implementation built per [ADR-0003](0003-autonomous-pipeline-with-critics.md) D7 acknowledged this with a temporary exception in its skill body: *"Stage 4 (implementer + reviewer per slice) and 5 (`qa-plan`) are out of `/ship`'s scope in this slice. The human runs them separately for now."* (see `.claude/skills/ship/SKILL.md`).

That "for now" has lasted across 7 shipped PRDs. The result, observed by the user at session start on 2026-05-19: **every `/ship` invocation stops at slice posting, requiring a separate manual prompt to trigger implementation**. The autonomous pipeline isn't actually autonomous in stage 4. Slices accumulate unimplemented — across 2026-05-15/16/19 sessions, three /ship runs each ended with a queue of unimplemented slices that the user later had to manually drive through implementation.

The user raised this as a workflow defect, not as a feature. The grill on 2026-05-2X (Q1-Q6) chose to ship the `implementer` subagent (backlog [#64](https://github.com/vojtech-stas/project-claude/issues/64)) SOLO (CI [#63](https://github.com/vojtech-stas/project-claude/issues/63) deferred), with `/ship` orchestrator-driven invocation (not CI-driven, until CI ships). This ADR captures the design.

## Decisions

### D1: One implementer subagent for all slice types

Ship a single `.claude/agents/implementer.md` that handles all slice types (feat/fix/docs/refactor/test) uniformly. The slice's branch-name prefix and commit-type follow CLAUDE.md conventions; the implementer adapts based on the slice issue body's "What ships" + "Acceptance criteria" sections.

Rationale (YAGNI): we have no data yet that different slice types need different prompts. The bootstrap-mode policy permits future specialization via a superseding ADR. Specialized variants (`feat-implementer` / `docs-implementer` / etc.) were explicitly rejected as premature.

### D2: `/ship` orchestrator auto-invokes implementer after slices posted

`/ship` body extends to automatically invoke the implementer subagent on each posted slice. Pipeline runs end-to-end from `/grill-me` to all-slices-merged with NO human gate between. The legitimate human checkpoint is `/qa-plan` (terminal) per ADR-0003 D4.

This **closes the residual human-trigger gap** that ADR-0003 D7's walking-skeleton acknowledged as "for now". Once ADR-0010 ships, ADR-0003 D4's "no human gates between stages" becomes properly enforceable end-to-end.

### D3: Parallel-where-independent (DAG-aware) execution

Orchestrator reads each posted slice's "Depends on" field (slicer-critic-verified per the DAG check), builds the dependency graph, and runs slices in parallel where dependencies are satisfied. Independent slices process concurrently; sync points are at dependency boundaries.

Rationale: honors slicer-critic-verified INVEST Independence; exploits the parallelism the slicer already designed for. A PRD with one walking-skeleton + N independent follow-ons can ship N+1 slices in approximately 2 reviewer-round-trip durations instead of N+1.

### D4: Forward-block failure handling

On a slice failure that auto-retry layers can't absorb (genuine round-3 BLOCK from reviewer; ambiguous acceptance criterion the implementer surfaces as `BLOCKED:<reason>`; INVALID_INPUT from a malformed slice issue):

1. Failed slice gets the `needs-human` label per existing I5 pattern.
2. **In-flight parallel slices finish normally** (they're already running; cancellation has no value).
3. **Slices whose dependencies INCLUDE the failed slice stay blocked indefinitely.** The orchestrator surfaces them in its terminal GENERATOR trailer as "blocked by #N".
4. **Slices with OTHER unmet deps proceed normally** through their natural batches.

Auto-retry layers (implementer-internal retry on transient errors; implementer+reviewer ≤3 round revision loop on rubric findings) handle ~80% of real-world failures before this escalation fires. Forward-block only triggers on genuinely irrecoverable failures.

Rationale: failure is locally contained, not contagious. Maximum useful work is preserved. Matches the existing I5 escalation surface (needs-human label + parent-PRD comment) without inventing a new escalation channel.

### D5: Sequential walking-skeleton; parallel ships in slice 2

Walking-skeleton slice 1 of PRD-implementer ships: implementer.md + /ship sequential auto-invocation + ADR-0010 commit + decisions/README row + dogfood. **Sequential only.** Slice 2 adds the parallel/DAG batching logic per D3 (and the forward-block failure handling per D4).

Rationale: walking-skeleton LoC budget is tight (~200 implementer + ~50 /ship sequential = ~250 runtime; under 300 cap). Adding parallel/DAG logic (~80-120 LoC) to slice 1 would breach R-LOC. Sequential is the safe baseline (no race conditions, no rebase complexity); parallel is optimization-not-correctness. Closes D3's locked behavior in TWO slices rather than one — an explicit trade-off, not a regression.

### D6: Tool boundaries per #64 captured body

Implementer gets: `Read`, `Edit`, `Write`, `Bash`, `Glob`, `Grep`.

**Explicitly NOT:** `Agent` (no recursive subagent invocation; the reviewer is invoked by /ship orchestrator AFTER the implementer's PR is opened, not by implementer itself). This prevents the implementer from spawning sub-implementers or other critics — keeps the contract clean and avoids confused authority.

The implementer does NOT directly create GitHub issues or PRs outside its own branch (no `gh issue create` for capture or backlog management; that's the orchestrator's or other skills' job).

### D7: Failure return modes per #64

The implementer returns one of three structured outcomes via the canonical GENERATOR trailer (per ADR-0005 D1c):

- **`RESULT: SUCCESS`** — PR opened with `Closes #<slice>`; ready for reviewer. Trailer includes per-agent extensions `PR_URL` and `BRANCH_NAME`.
- **`RESULT: BLOCKED`** with `REASON: <one sentence>` — genuine failure auto-retry can't absorb (merge conflict unresolvable, ambiguous acceptance criterion, scope explosion past the slice's SPIDR-Interface fallback hint). Implementer leaves a comment on the slice issue describing what's blocking; orchestrator applies the `needs-human` label per D4.
- **`RESULT: INVALID_INPUT`** with `REASON: <one sentence>` — the slice issue is malformed (missing acceptance criteria, missing parent-PRD reference, etc.). Implementer does NOT attempt; surfaces the issue for slicer/human correction.

Auto-retry layers within the implementer handle transient failures BEFORE returning one of these three:
- Tool errors (Edit fails, Bash fails, gh API hiccup) → retry with backoff (max 3 attempts)
- Test failures the implementer wrote → iterate locally before pushing
- Implementer's own self-checks (LoC count, PR body shape) → fix locally before push

### D8: Implementer is a generator; reviewer is its critic — no new critic needed

The implementer is a GENERATOR (it produces PRs). Per ADR-0005 D1, generators emit the GENERATOR trailer (per D7 above). The implementer's adversarial critic is the existing **reviewer** subagent — reviewer audits the PR and verdicts APPROVE/BLOCK per its rubric. The implementer+reviewer ≤3 round loop is the critic loop.

**No new critic is created.** Honors [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 6-critic-cap meta-rule: this ADR adds 0 critics. The implementer-critic role is absorbed by reviewer.

### D9: Bootstrap-mode acknowledgment (per [ADR-0004](0004-bypass-prevention.md) D2)

The implementer subagent and /ship auto-invocation logic bind FORWARD from each slice's merge:

- **Slice 1's mechanism** (implementer.md + /ship sequential invocation) applies to PRDs whose /ship runs from slice 1's merge onward. Existing pending slice issues (e.g., #77, #78, #79 from PRD #75 if not yet implemented at slice 1's merge time) CAN be processed by the new implementer on-demand once it's in main, but not retroactively swept.
- **Slice 2's parallel/DAG logic** binds from slice 2's merge. Sequential remains the default for the brief window between slice 1 and slice 2 merging.
- **Cascade docs (slice 3)** apply to documentation read after their merge; no retroactive doc update needed.

In-flight /ship invocations at any slice merge boundary use whichever /ship body they loaded at invocation time. There is no mid-pipeline reload.

This acknowledgment follows the same shape as [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D8 and [ADR-0009](0009-discipline-tightening.md) D5.

## Consequences

**Positive:**
- **Closes the autonomy gap.** ADR-0003 D4's "no human gates between stages" becomes properly enforceable end-to-end. The user's stated workflow defect (every /ship requires a follow-on manual implementation prompt) is fixed.
- **Pipeline ergonomics improve dramatically.** Future PRDs flow `/grill-me` → `/ship` → automatic implementation → `/qa-plan` with one human-action per gate. Sessions stop accumulating queues of unimplemented slices.
- **Parallel/DAG (slice 2) saves real wall-clock time** on multi-slice PRDs. A 4-slice PRD with 3 independent follow-ons drops from ~4 sequential reviewer round-trips to ~2.
- **Forward-block failure handling preserves maximum useful work.** A single failed slice doesn't take the rest of the PRD down with it.
- **One implementer simplifies maintenance** — one prompt file, one mental model. Specialization is reversible if data justifies later.

**Negative:**
- **`/ship` body grows substantially** — auto-invocation logic + (in slice 2) parallel/DAG batching + forward-block failure handling. The /ship skill stops being "walking skeleton" and becomes load-bearing pipeline code.
- **Failure modes get more nuanced under parallelism.** Mid-pipeline file conflicts between parallel slices, race conditions at the merge queue, partial-success final reports — all become real things qa-plan must interpret.
- **Sequential ships first; parallel is a second slice.** Slice 1 closes the gap but does NOT yet deliver the parallel speedup. Users wanting parallel must wait for slice 2's merge.
- **The implementer subagent file is the largest in the project.** ~200 LoC of prompt covering branch conventions, scope discipline, commit format, PR body shape, failure handling, auto-retry logic, and tool-use patterns. Prompt-engineering load.
- **R-LOC pressure on slice 1.** The walking-skeleton bumps against the 300 LoC runtime cap. SPIDR-Interface fallback (defer cascade docs to slice 3) is named in the PRD as the contingency.

**Neutral:**
- No new critic (D8 — honors 6-critic-cap meta-rule).
- No external dependencies (no CI infrastructure, no bot identity, no GitHub Actions).
- Implementer model is `opus` (default for quality-critical subagents).
- The slicer's `Depends on` field becomes load-bearing (the DAG is parsed by /ship for D3); slicer-critic rule 6 already verifies DAG correctness.

## Alternatives considered

- **Alt-A: Pair-grill #64 (implementer) with #63 (CI) for one combined PRD.** Rejected at grill Q1: multi-feature-PRD smell (same trap as PRD #58); CI half requires bot identity setup + GitHub Actions YAML design which significantly delays implementer; the user wanted the workflow gap closed sooner, not later.
- **Alt-B: Specialized implementer variants (feat / docs / refactor / ...).** Rejected at grill Q2: YAGNI; no data justifies specialization yet; can split prompt later via a new ADR if data justifies.
- **Alt-C: `/implement <N>` user-driven skill only; /ship stays at slice posting.** Rejected at grill Q3: directly regresses on the workflow gap the user raised; defeats the purpose of grilling implementer.
- **Alt-D: Direct Agent-tool invocation (low-level only).** Rejected at grill Q3: forces user to remember invocation shape; no auto-trigger; same regression as Alt-C.
- **Alt-E: Strict sequential implementation always (no parallel even where independent).** Rejected at grill Q4: wastes the parallelism the slicer designs for; the slicer-critic already verifies INVEST Independence which makes parallel safe in the DAG-respected case.
- **Alt-F: Best-effort failure handling (continue on every slice regardless of dep relationship).** Rejected at grill Q5: violates DAG semantics; produces incoherent state when a slice runs while its dep failed.
- **Alt-G: Halt-all-on-first-failure.** Rejected at grill Q5: wastes parallel speedup; the rare nature of escalations (after auto-retry layers) means the per-failure cost of halting all is bounded but consistently wasteful.
- **Alt-H: Ship parallel/DAG batching in slice 1 (all-in-one).** Rejected at grill Q6: LoC budget overflow almost certain; slicer-critic would BLOCK on R-LOC; sequential-first is the safe baseline that ships earlier.
- **Alt-I: Add a dedicated `implementer-critic` subagent.** Rejected per D8: would breach ADR-0008 D7 6-critic-cap; reviewer absorbs the role naturally (reviewer is the existing PR-gate critic).
- **Alt-J: Implementer can spawn sub-implementers via Agent tool (recursive).** Rejected per D6: confused authority; risk of runaway agent spawning; cleaner separation when implementer only DOES the work and orchestrator handles control flow.

## Open questions deferred

- Whether the implementer needs a `--dry-run` mode for testing the prompt against a slice without actually creating a branch + PR. Deferred until we observe whether the implementer's failure modes are rare enough that dry-run isn't needed.
- Whether the implementer should cache PRD + ADR reads across slices in the same /ship run (each implementer invocation re-reads the parent PRD; could optimize). Deferred until token cost analysis post-merge shows it matters.
- Whether the parallel-batch failure-recovery should auto-rebase merge conflicts when a parallel sibling merges first. Deferred until we observe how often this actually happens; slicer-critic INVEST Independence should make it rare.
- Whether the implementer's PR body should follow a stricter template (currently CLAUDE.md gives the shape; should the implementer enforce a more rigid schema?). Defer to reviewer-flagged patterns post-merge.

## Future direction

- **Specialized variants (per slice type)** if data shows the unified prompt is overflowing or accuracy is suffering on specific types. Bootstrap-mode permits via superseding ADR.
- **CI integration** (sister PRD-CI based on backlog #63) lets the implementer be triggered by `slice`-label events rather than only by /ship. The two invocation paths coexist.
- **Implementer-driven PRD restructuring** if a slice fundamentally can't be implemented as-described (today: BLOCKED+needs-human; future: implementer could propose a re-slice). Significant new authority surface; defer until rare-but-real signal.
- **Cost / latency instrumentation** on implementer invocations so the unified-vs-specialized decision (D1 vs Alt-B) can be revisited with data.

## References

- [ADR-0003](0003-autonomous-pipeline-with-critics.md) D2 (5-stage pipeline — this ADR fills stage 4); D4 (no human gates — this ADR closes the residual violation); D7 (`/ship` walking-skeleton with "for now" exception — this ADR makes good on that promise); D8 (ADR placement at grill→PRD boundary — why this ADR ships alongside PRD-implementer).
- [ADR-0002](0002-autonomous-merge-policy.md) — reviewer auto-merge on APPROVE; the implementer hands off to reviewer per D8.
- [ADR-0004](0004-bypass-prevention.md) D2 — bootstrap-mode policy (D9 follows the pattern).
- [ADR-0005](0005-output-shape-and-slicing-methodology.md) D1 (GENERATOR trailer schema the implementer emits per D7).
- [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 (6-critic-cap meta-rule — this ADR adds 0 critics per D8); D8 (bootstrap-mode acknowledgment pattern D9 mirrors).
- [ADR-0009](0009-discipline-tightening.md) D5 (also a bootstrap-mode acknowledgment in similar shape).
- Backlog [#64](https://github.com/vojtech-stas/project-claude/issues/64) — the captured candidate that motivated this PRD; its body is the substantive input to D1, D6, D7.
- Backlog [#63](https://github.com/vojtech-stas/project-claude/issues/63) — CI sibling deferred; pairing rejected at grill Q1.
- Grill session: PRD-implementer Q1–Q6 (2026-05-2X).
