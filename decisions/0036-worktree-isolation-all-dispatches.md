# ADR-0036: Worktree isolation for ALL git-mutating subagent dispatches

- **Status:** Accepted
- **Date:** 2026-05-31
- **Supersedes:** [ADR-0035](0035-worktree-isolation-parallel-dispatch.md) D1 (the batch-size-≥2 condition and the explicit batch-size-1 carve-out) and resolves the manual-dispatch follow-on deferred in [ADR-0035](0035-worktree-isolation-parallel-dispatch.md) D3.
- **Extends:** [ADR-0010](0010-implementer-subagent-auto-pipeline.md) D6 (implementer tool boundaries; isolation stays in the orchestrator), honors [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 (no new critic).

## Context

[ADR-0035](0035-worktree-isolation-parallel-dispatch.md) D1 mandated harness-native `isolation: "worktree"` for parallel implementer dispatch — but only for ready batches of size **≥ 2**, explicitly carving out batch-size-1: *"there is no concurrency and therefore no race."* ADR-0035 D3 further deferred the **manual dispatch path** (main agent dispatching implementers/reviewers directly, not via `/ship`) to a captured follow-on.

That race-only framing missed a second failure mode, observed repeatedly in a 2026-05-31 session that dispatched implementers/reviewers **serially** (batch-1) without isolation: **shared-tree state pollution.** A single subagent doing `git checkout -b <branch>`, `git checkout main`, `git fetch/pull`, or `gh pr merge --delete-branch` mutates the HEAD/branch state of the *shared* tree it runs in (the orchestrator's session worktree, and — when cwd resolved there — the root repo). With no sibling concurrency there is no *race*, but the orchestrator (and the next dispatched subagent) then finds the shared tree on an unexpected branch or mid-conflicted-merge. Concrete symptoms that session: the session worktree left orphaned on a merged feature branch; the root repo tangled into conflicted-merge / wrong-branch states ~4 times, each needing manual `git merge --abort` / `reset` / `checkout -B main` recovery; and reviewers' `gh pr merge --delete-branch` repeatedly failing with *"branch deletion failed — worktree conflict"* because the shared tree had the to-be-deleted branch checked out. Reviewers also hit a stale-local-`main` false-positive ([#432](https://github.com/vojtech-stas/project-claude/issues/432)) from operating on a polluted/un-fetched shared tree.

**Root cause (generalized):** *any* subagent that performs git branch/merge operations inside a tree the orchestrator also uses can corrupt that tree's state — independent of concurrency. ADR-0035's race-only fix is necessary but not sufficient.

## Decisions

### D1: Every implementer dispatch uses worktree isolation, regardless of batch size

Supersedes [ADR-0035](0035-worktree-isolation-parallel-dispatch.md) D1's batch-size condition. EVERY `implementer` `Agent` invocation — whether part of a parallel ready batch (≥2) OR a serial single dispatch (batch-1, including single-slice PRDs) — MUST pass `isolation: "worktree"`. The batch-size-1 carve-out ("MAY run without isolation") is removed: even a lone implementer's `git checkout -b` pollutes the shared tree's HEAD. The orchestrator no longer branches on batch size — it isolates unconditionally.

### D2: Reviewer dispatch is isolated too

EVERY `reviewer` `Agent` invocation MUST pass `isolation: "worktree"`. The reviewer's `git fetch` + `git diff origin/main...<branch>` + `gh pr merge --squash --delete-branch` then run in a fresh harness-created worktree that (a) is never the shared session tree, and (b) does not have the merged branch checked out — eliminating the "branch deletion failed — worktree conflict" failure and the stale-local-`main` false-positive class ([#432](https://github.com/vojtech-stas/project-claude/issues/432), since the isolated tree is freshly created off HEAD and the reviewer fetches `origin/main` explicitly).

### D3: The invariant — dispatched subagents never mutate the orchestrator's session worktree or the root repo

A subagent that performs git branch/merge operations MUST run in an isolated worktree; the orchestrator's session worktree and the project root repo are never mutated by a dispatched subagent. This binds BOTH dispatch paths: `/ship`'s stage-4 loop AND the main agent dispatching `implementer`/`reviewer` manually. (Resolves the manual-path follow-on deferred by ADR-0035 D3.)

### D4: Read-only / non-git-mutating subagents are exempt (YAGNI)

Isolation is required only for the git-MUTATING subagents (`implementer`, `reviewer`). Subagents that never run `git checkout`/`commit`/`merge` — `slicer`, `slicer-critic`, `prd-critic`, `adr-critic`, `qa-tester`, `glossary-critic`, `backlog-critic` — are NOT required to isolate (they read the tree at most; `gh`/read-only `git` is safe). Mandating isolation for them is harmless but adds worktree-creation cost for no benefit. Default-narrow.

### D5: Bootstrap-mode acknowledgment (per [ADR-0004](0004-bypass-prevention.md) D2)

Binds FORWARD from this ADR's merge, mirroring [ADR-0035](0035-worktree-isolation-parallel-dispatch.md) D4: a `/ship` body (or main-agent dispatch) loaded after this slice merges applies the rule; in-flight runs use their loaded body. No retroactive sweep; no auto-cleanup of pre-existing orphaned worktrees (a one-off ops task).

## Consequences

**Positive:**
- Eliminates shared-tree state pollution (the serial/manual failure mode), not just the parallel race — the orchestrator's session tree + root repo stay clean across any dispatch pattern.
- Removes the recurring "branch deletion failed — worktree conflict" and reduces the reviewer stale-base false-positive class ([#432](https://github.com/vojtech-stas/project-claude/issues/432)).
- One uniform rule (always isolate the git-mutating two) — simpler than a batch-size conditional.

**Negative:**
- Every implementer/reviewer dispatch pays a worktree-creation cost (cheap — worktrees share one `.git`).
- The isolated reviewer runs `gh pr merge --delete-branch` against the remote; because the merged branch is not checked out in the isolated tree, the delete no longer conflicts — that is the point of D2.

**Neutral:**
- No new critic (honors [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7), no new dependency (harness-native), no implementer/reviewer INTERNAL-logic change — only WHERE they run.

## Alternatives considered

- **Alt-A (chosen): isolate all git-mutating dispatches unconditionally.** Uniform, eliminates both race and pollution.
- **Alt-B: keep ADR-0035's batch-size-1 carve-out; add an orchestrator post-dispatch "restore shared tree to main" step.** Rejected: fragile (which ref? what if dirty?), and still races the orchestrator's own operations against the subagent's.
- **Alt-C: forbid subagents from running git branch ops entirely (push branch creation to the orchestrator).** Rejected: breaks the implementer's self-contained branch→commit→PR contract (ADR-0010) for no gain over isolation.
- **Alt-D: status quo (ADR-0035 race-only).** Rejected: the 2026-05-31 session proved serial/manual dispatch pollutes shared trees ~4×.

## References

- [ADR-0035](0035-worktree-isolation-parallel-dispatch.md) — D1 (superseded carve-out), D3 (deferred manual-path follow-on this ADR resolves), D2/D4 (isolation-in-orchestrator + bootstrap shapes this mirrors).
- [ADR-0010](0010-implementer-subagent-auto-pipeline.md) D6 (implementer tool boundaries), [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 (no new critic).
- [#322](https://github.com/vojtech-stas/project-claude/issues/322) (worktree-race root cause; this ADR closes the serial/manual gap), [#432](https://github.com/vojtech-stas/project-claude/issues/432) (reviewer stale-base, same shared-tree class), sibling worktree reports #298/#300/#173/#195/#213/#214.
- 2026-05-31 session evidence: shared worktree orphaned on `hotfix/disable-graph-zoom-pan`; root tangled ~4×; repeated reviewer "branch deletion failed — worktree conflict".
