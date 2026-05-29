# ADR-0035: Per-agent worktree isolation for parallel implementer dispatch

- **Status:** Accepted
- **Date:** 2026-05-30
- **Extends:** [ADR-0010](0010-implementer-subagent-auto-pipeline.md) D3 (supplies the working-tree isolation mechanism D3's parallel-dispatch decision left unspecified); honors [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 (no new critic)
- **Supersedes:** none
- **Numbering note:** 0032 and 0034 are reserved by in-flight gate-cleared ADR drafts (PRD #341 and PRD #348 respectively); this ADR takes 0035 to avoid forcing a renumber on those drafts. The 0032/0034 gap on disk is intentional and fills when those PRDs merge.

## Context

[ADR-0010](0010-implementer-subagent-auto-pipeline.md) D3 decided **DAG-aware parallel dispatch**: `/ship`'s stage-4 loop computes a ready batch of independent slices (deps all merged) and dispatches them concurrently by invoking the `implementer` subagent via the `Agent` tool. D3 specified *which* slices run in parallel — but said nothing about *where* each implementer's working tree lives.

The defect surfaced in production (root-cause capture [#322](https://github.com/vojtech-stas/project-claude/issues/322), with sibling reports [#298](https://github.com/vojtech-stas/project-claude/issues/298) and [#300](https://github.com/vojtech-stas/project-claude/issues/300)): concurrently dispatched implementers all executed inside the **same shared worktree** and raced on `git checkout -b`. The implementer for slice #312 found its working-tree HEAD switched mid-task to a sibling's branch (`feat/314-...`) with the sibling's unrelated edits staged. The slice became unsafe to commit (would mix in sibling work) and unsafe to clean (would destroy it); the implementer correctly halted with `RESULT: BLOCKED` per [ADR-0009](0009-discipline-tightening.md) D3/D4 default-conservative.

**Root cause:** there is no per-branch working-tree isolation between concurrently dispatched implementers — the shell working directory is shared, so two `git checkout -b` calls fight over one HEAD. This is a correctness gap in D3's design: parallel dispatch is unsafe without isolation. The project has been working around it by serializing all slices, which abandons the wall-clock speedup D3 was built to deliver.

## Decisions

### D1: Parallel implementer dispatch MUST use per-agent worktree isolation

When `/ship`'s stage-4 dispatch loop (the [ADR-0010](0010-implementer-subagent-auto-pipeline.md) D3 ready-batch dispatch) dispatches a ready batch of size **≥ 2**, EACH `implementer` `Agent` invocation MUST run in its own isolated git worktree, using the harness-native `isolation: "worktree"` parameter on the `Agent` tool call.

The harness creates a fresh per-agent worktree off the current HEAD; the implementer creates and commits its branch there in isolation, pushes to `origin`, and opens its PR; the harness auto-cleans the worktree when the agent returns. Because each agent owns a distinct working directory, concurrent `git checkout -b` calls can no longer collide.

A ready batch of size **1** (single-slice PRDs, or a batch that happens to contain one slice) MAY run without isolation — there is no concurrency and therefore no race — but isolation is harmless and permitted. The dispatch loop need not branch on batch size for correctness; it MUST apply isolation whenever it dispatches more than one implementer in the same iteration.

**Rationale:** eliminates the race at its source (the shared working directory) using the harness's built-in mechanism rather than bespoke `git worktree add`/`remove` plumbing. This is the "wheel already invented" — the Agent tool was designed for exactly this isolation case.

### D2: The isolation mechanism lives in the orchestrator, not the implementer

The decision to isolate is made by `/ship` (the dispatcher), not by the implementer. The implementer body is **unchanged**: it continues to `git checkout -b` and operate in "the current worktree", which — when dispatched under D1 — is now its own isolated one. No `implementer.md` edit is required.

**Rationale:** honors [ADR-0010](0010-implementer-subagent-auto-pipeline.md) D6 (the implementer has no `Agent` tool and does not self-spawn or self-manage worktrees) and keeps the implementer worktree-agnostic. Control flow belongs to the orchestrator; the implementer only does the work.

### D3: Detection/guard layer deferred (YAGNI)

[#322](https://github.com/vojtech-stas/project-claude/issues/322) proposed two additional layers: Option B (an implementer pre-check that BLOCKs on detecting another agent's branch in its worktree) and Option C (a CLAUDE.md rule mandating distinct worktrees). D1's source-elimination makes both **defense-in-depth, not load-bearing**, so neither ships here. A `captured` follow-on tracks the optional implementer guard for the *manual* dispatch path (where `/ship` is not the dispatcher and isolation is not guaranteed).

**Rationale:** YAGNI (CLAUDE.md rule #1) — ship the minimal correct fix; add defensive layers only if the source fix proves insufficient in practice.

### D4: Bootstrap-mode acknowledgment (per [ADR-0004](0004-bypass-prevention.md) D2)

The isolation requirement binds FORWARD from this ADR's merge. A `/ship` invocation that loads its body after this slice merges applies isolation; an in-flight `/ship` run uses whatever body it loaded at invocation time (no mid-pipeline reload). No retroactive sweep of already-merged work. Mirrors the shape of [ADR-0010](0010-implementer-subagent-auto-pipeline.md) D9 and [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D8.

## Consequences

**Positive:**
- ADR-0010 D3 parallel batching becomes **safe to actually use** — unblocking the wall-clock speedup on multi-slice PRDs that motivated [#322](https://github.com/vojtech-stas/project-claude/issues/322).
- Zero custom worktree plumbing; the implementer is untouched.
- The fix is the harness-native mechanism, so it tracks harness behavior rather than diverging from it.

**Negative:**
- Each parallel implementer pays a worktree-creation cost (cheap — worktrees share one `.git`).
- Isolated worktrees are ephemeral: if an implementer fails before pushing, its local work is auto-cleaned. Acceptable — nothing reached `origin`, and the slice is simply re-dispatched.

**Neutral:**
- No new critic (honors [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7); no new reviewer rule; no new dependency (harness-native).
- The change is confined to the `/ship` skill body (runtime) plus this ADR and its truth-doc cascade (non-runtime).

## Alternatives considered

- **Alt-A (chosen): harness-native `isolation: "worktree"` per parallel `Agent` call.** Minimal, correct, no custom lifecycle code.
- **Alt-B: implementer self-manages `git worktree add <path>` / work / `git worktree remove`.** Rejected: the implementer's Bash shell state does not persist across tool calls, making manual worktree lifecycle + cleanup error-prone; it also duplicates what the harness already provides.
- **Alt-C: detection-only (#322 Option B) without isolation.** Rejected as the *primary* fix: it converts corruption into a BLOCK but still cannot run slices in parallel safely. Retained only as deferred defense-in-depth (D3).
- **Alt-D: serialize all slices permanently (status quo).** Rejected: abandons ADR-0010 D3's designed speedup; directly contradicts the user's request for parallel waves.
- **Alt-E: `/ship` pre-creates a dedicated locked `agent-<hash>/` worktree per slice (the literal #322 Option A wording).** Rejected in favor of harness `isolation`: same isolation effect, but the harness manages creation AND cleanup automatically, whereas pre-creating named locked worktrees reintroduces manual lifecycle management and worktree-leak risk.

## References

- [ADR-0010](0010-implementer-subagent-auto-pipeline.md) — D3 (parallel dispatch; this ADR supplies its missing isolation mechanism), D6 (implementer tool boundaries; why isolation lives in the orchestrator — D2), D9 (bootstrap-mode shape D4 mirrors).
- [ADR-0003](0003-autonomous-pipeline-with-critics.md) D1 — defines a slice as an INVEST-shaped vertical; the **Independence** property (the "I" in INVEST) is what makes the independent slices of a ready batch semantically safe to run concurrently once their worktrees are isolated.
- [ADR-0009](0009-discipline-tightening.md) D3/D4 — default-conservative; why the racing implementer in #322 correctly BLOCKED rather than committing contaminated work.
- [#322](https://github.com/vojtech-stas/project-claude/issues/322) — root-cause capture (symptom + root cause + Option A/B/C proposal); [#298](https://github.com/vojtech-stas/project-claude/issues/298), [#300](https://github.com/vojtech-stas/project-claude/issues/300) — sibling worktree-race reports.
