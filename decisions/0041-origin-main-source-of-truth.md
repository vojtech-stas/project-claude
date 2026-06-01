# ADR-0041: origin/main is the only source of truth — worktree leak-guard + root ff-sync + consistent verify-base

- **Status:** Accepted
- **Date:** 2026-06-01
- **Extends:** [ADR-0036](0036-worktree-isolation-all-dispatches.md) D3 (the declared invariant "dispatched subagents never mutate the orchestrator's session worktree or the root repo" — this ADR adds the **guard** that enforces it + a scoped orchestrator carve-out). Reuses the `git --git-common-dir` root-resolution pattern from the canonical-log `.claude/hooks/log-event.sh` helper (an implementation pattern, not an ADR-backed decision). Honors [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 (no new critic) and [ADR-0015](0015-claude-code-hooks-adoption.md) (the guard is an orchestrator-invoked helper, not an auto-mutating Claude Code hook).
- **Supersedes:** none.

## Context

A ~10-issue cluster shares one root pathology: **agents trust worktree-local git state instead of the canonical remote (`origin/main`)**. Two faces:

1. **The post-dispatch leak.** `isolation: "worktree"` (ADR-0036) is supposed to keep a dispatched subagent's git work off the orchestrator's worktree and the root repo (D3 invariant). In practice, on this Windows multi-worktree setup, after an isolated `implementer`/`reviewer` dispatch the **orchestrator's own worktree** (and the **root repo**) is left checked out on the *dispatched feature branch*, not its prior branch / `main`. Observed and worked-around manually **3× in a single session** (2026-06-01). Consequences: the orchestrator dispatches the next slice from the wrong branch; the **root repo — which the dashboard serves — shows a stale feature-branch checkout** (#418); stale dirty worktree state carries across sessions (#213); `gh pr merge --delete-branch` conflicts (#214). D3 declared the invariant but nothing **guards** it.

2. **The verify-base drift.** Critics and AC-checks compute their diff base / scope / literal-count assertions from a **local** ref (a stale `main`, or worktree `HEAD`) instead of `origin/main`. This produces **false BLOCKs** — `reviewer` R-SCOPE/R-DOCS-CURRENT against a stale local `main` (#432); `slicer-critic` checking worktree state (#230); stale-worktree false-alarms in subagent dispatches (#173) — and **acceptance-criterion literal-count drift** session-to-session (#205). The `reviewer` body *already* states the principle in its run-context preamble ("`git fetch origin` and compute all diffs against `origin/main`"), but it is **not applied consistently per rule-mechanic** and is **absent from `slicer-critic`** and the AC-checking flow.

Grill (2026-06-01, Q1–Q6) resolved a single principle — **`origin/main` is the only source of truth for branch state, diff base, and AC verification** — fixed at three points: a leak-guard, a root ff-sync, and a consistent verify-base.

## Decisions

### D1: Post-dispatch worktree leak-guard enforces the ADR-0036 D3 invariant

The orchestrator (the main agent running `/ship` or `/build`) **captures its current branch before each isolated `Agent` dispatch** and, **after the dispatch returns, restores it** — asserting it is still on the expected branch and, if it drifted, ff-restoring from `origin/main` (`git checkout -B <expected> origin/main`, only when the tree is clean; soft-degrade otherwise). A small helper script (implementer's choice of `.claude/hooks/` or `tools/`; invoked by the orchestrator via `Bash`, NOT wired to a Claude Code event — so it does not strain [ADR-0015](0015-claude-code-hooks-adoption.md)) encapsulates the assert-and-restore. This is the guard that makes ADR-0036 D3 actually true on this setup; it is the exact `git checkout -B <branch> origin/main` restore that was performed manually 3× the day this ADR was written.

### D2: `origin/main` is the only verification base, applied consistently across all critics + AC-checks

Every critic and AC-checking agent MUST `git fetch origin main` and compute its **diff base, scope judgment, and acceptance-criterion checks against `origin/main`** — never local `main` (which may be stale) and never worktree `HEAD`. The `reviewer` already states this in its preamble; this ADR makes it **consistent in every rule-mechanic that computes a diff** (notably R-SCOPE and R-DOCS-CURRENT, the #432 false-BLOCK sites) and **extends it to `slicer-critic`** (#230) and any literal-count AC verification (#205). Soft-degrade if `git fetch` fails (note the degradation; do not silently compare against a possibly-stale base — prefer surfacing "could not fetch origin" over a false BLOCK).

### D3: The orchestrator MAY ff-sync the root repo (a scoped carve-out to ADR-0036 D3's spirit)

ADR-0036 D3 forbids **dispatched subagents** from mutating the root repo. This ADR adds a **deliberate, narrow exception for the ORCHESTRATOR** (never a subagent): after a slice merges to `origin/main`, the orchestrator MAY ff-sync the root worktree to `origin/main` — `git -C <root> checkout main && git -C <root> merge --ff-only origin/main` — **fast-forward-only**, **only when the root tree is clean**, **soft-degrading** on any error (never destructive, never a non-ff merge, never a reset). The root is resolved via the `git --git-common-dir` pattern (the same root-resolution the canonical-log `.claude/hooks/log-event.sh` helper uses). Purpose: the dashboard serves the root, so the root must reflect live `main` (#418). Subagents remain bound by D3 unchanged; only the orchestrator gets this safe ff-sync.

### D4: Bootstrap-mode (per [ADR-0004](0004-bypass-prevention.md) D2)

Binds forward from merge. No retroactive sweep; the guard + verify-base apply to dispatches and reviews from this ADR's slices onward.

## Consequences

**Positive:**
- The orchestrator and root never linger on a dispatched feature branch — the dashboard always shows live `main`; the next slice dispatches from the right base.
- False BLOCKs from stale-local-ref comparisons disappear; AC literal-counts are checked against current truth.
- One principle ("`origin/main` is truth") closes ~10 backlog issues coherently.

**Negative:**
- The orchestrator now runs a guard after every dispatch (a few extra git commands) — cheap, and only restores on drift.
- The D3 root carve-out means the orchestrator *does* mutate the root — mitigated by the strict ff-only/clean-only/soft-degrade contract (it can only ever advance the root to a commit already on `origin/main`).

**Neutral:**
- Net new artifact: one guard helper script. No new critic, no new dependency. Runtime touch: `/ship`, `/build`, `reviewer`, `slicer-critic` bodies.

## Alternatives considered

- **Alt-A (chosen):** orchestrator-run guard + root ff-sync + consistent verify-base.
- **Alt-B: a Stop hook re-syncs at end of turn.** Rejected (Q2): fires too late — the drift bites mid-turn (the orchestrator reads stale state / dispatches the next slice before Stop fires); and an auto-mutating git hook strains ADR-0015.
- **Alt-C: orchestrator only ever reads `origin/main`, never restores.** Rejected (Q2): leaves the root + dashboard on the wrong branch (#418 unfixed) — the visible half.
- **Alt-D: dashboard serves `origin/main` content directly.** Rejected (Q3): bigger awkward dashboard change; doesn't help a human inspecting the root; #418's root-never-synced concern persists outside the dashboard.
- **Alt-E: no ADR — treat the guard as pure ADR-0036 D3 implementation.** Rejected (Q5): the verify-base rule and the root-mutation carve-out are genuinely new decisions (the carve-out notably bends D3's "don't mutate root" spirit) and deserve a record.

## References

- Grill 2026-06-01 Q1–Q6 (one PRD / orchestrator guard / root ff-sync / verify-against-origin / new ADR extending 0036 / 2 slices).
- [ADR-0036](0036-worktree-isolation-all-dispatches.md) D2 (reviewer isolated), D3 (the invariant this guard enforces + the carve-out's scope). [ADR-0015](0015-claude-code-hooks-adoption.md) (the guard is orchestrator-invoked, not an auto-mutating Claude Code hook). [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 (no new critic). [ADR-0004](0004-bypass-prevention.md) D2 (bootstrap-mode). The `git --git-common-dir` root-resolution is an implementation pattern from the canonical-log `.claude/hooks/log-event.sh` helper (not an ADR decision).
- Cluster: #473 (leak, reproduced 3×), #418 (stale-root dashboard), #213 (stale dirty worktree), #214 (delete-branch worktree conflict) — D1+D3; #432 (reviewer stale-local-ref false-BLOCK), #230 (slicer-critic worktree state), #173 (stale-worktree false-alarm), #205 (AC literal-count drift) — D2.
- `.claude/skills/ship/SKILL.md`, `.claude/skills/build/SKILL.md`, the new guard helper, `.claude/agents/reviewer.md`, `.claude/agents/slicer-critic.md`.
