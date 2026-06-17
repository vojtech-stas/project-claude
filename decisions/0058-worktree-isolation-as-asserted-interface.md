---
id: "ADR-0058"
status: "accepted"
supersedes:
  - "ADR-0041"
superseded_by: []
scope: "isolation"
rule_ids:
  - "ISO-004"
  - "ISO-005"
  - "ISO-006"
---
# 0058 — Worktree isolation as an asserted interface

- **Status:** Accepted
- **Date:** 2026-06-12
- **Supersedes:** ADR-0036 D3 (the never-mutate invariant moves from convention to asserted interface — the invariant itself is preserved and strengthened, its by-convention enforcement is replaced by D1/D2 assertions); ADR-0041 D1 (the post-dispatch guard's `branch-restore` semantics — the silent force-reset behavior is retired in favor of D3's ff-only + loud-failure contract; the guard's existence and invocation points are unchanged)

## Context

ADR-0036 made worktree isolation mandatory for every implementer/reviewer dispatch and ADR-0041 added the post-dispatch guard — but both treat isolation as a CONVENTION the orchestrator requests, not an INTERFACE anyone asserts. Measured failures (2026-06-11, issue #746): of three isolated dispatches in one /ship wave, one returned no worktreePath at all (isolation silently never engaged; the agent ran in the root repo and left it checked out on its feature branch) and another leaked staged modifications into the root tree; the guard's `branch-restore` printed the drifted branch name without restoring. Related class: #673 (untracked-file leakage invisible to the guard), #732 (branch-restore is an undocumented force-reset; prune cannot reclaim worktrees whose branch never had a PR — the accumulation it exists to prevent), #685 (dispatched agents leave sandbox servers double-bound on production ports).

## Decisions

### D1 — Missing worktreePath is a dispatch failure

The orchestrator MUST check every isolated dispatch result for the harness-reported `worktreePath`. Absence means isolation did not engage: the result is treated as a failed dispatch regardless of the agent's own trailer — re-dispatch, and capture the occurrence (rule #13). The agent's work product from a non-isolated dispatch is suspect by definition.

### D2 — Dispatched agents self-assert isolation (step 0)

Implementer and reviewer dispatch templates pass the orchestrator's repo root; the agent's step 0 asserts `git rev-parse --show-toplevel` differs from it and is a worktree. On match the agent returns `RESULT: BLOCKED — isolation assertion failed` WITHOUT executing any write. Belt-and-braces with D1: the orchestrator checks after, the agent checks before.

### D3 — Guard semantics fixed and made loud

`tools/worktree-guard.sh`: (a) `branch-restore` performs fast-forward-only restore; non-ff drift (local commits on the wrong branch) is a loud non-zero failure naming the divergence — the silent `reset --hard` behavior is retired (it could abandon committed-but-unpushed work, #732); (b) `prune` gains a no-PR reclamation path: a dispatch worktree with no associated PR is reclaimed when its tree is clean AND its branch is 0-ahead of main AND it exceeds an age threshold; (c) `root-clean` verification after dispatches includes UNTRACKED files under tracked directories (the #746/#673 leak shape), not just modifications; (d) every guard subcommand exits non-zero on any unrepaired violation — guards never fail silently. `tools/README.md`'s "advisory, modifies nothing" claim is corrected (it deletes worktrees and branches).

### D4 — Sandbox teardown obligation

Any dispatched agent that starts a server/process for verification MUST kill it and verify port closure before returning; dispatch templates carry this line. (The stale-server class — #685, plus the 2026-06-11 incident where a worktree-spawned server on the canonical port served pre-merge code during a production gate — is downstream of orphaned sandboxes.)

### D5 — Isolation Health group on the dashboard

`dashboard/health.py` gains an isolation group: orphaned/empty worktree directories under `.claude/worktrees/`; prune drift (reclaimable-but-present count); escaped dispatches where computable from telemetry (bash events inside a dispatch window carrying the root `wt` field). Red on any non-zero entry. This is the standing detector for the whole class — the dashboard requirement that the designed workflow is *actually* isolated, not declared isolated.

## Consequences

- Isolation failures become a hard stop or a red badge within the same run, instead of a forensic surprise; the root repo's cleanliness is continuously attested.
- Re-dispatch on missing worktreePath costs one extra agent run when the harness glitches — cheap against the alternative (suspect work merged from an unisolated tree).
- `branch-restore` callers that relied on the silent force-reset must handle the loud failure; that is the point.

### D6 — Bootstrap-mode binding

Per ADR-0004 D2 (bootstrap-mode): D1–D4 bind forward from the merge of their implementing slice — D1/D2 apply to dispatches made after the /ship + agent-prompt edits merge; D3's guard-semantics change applies from its merge (callers encounter the loud non-ff failure only on post-merge invocations; the Consequences note about `branch-restore` callers is covered by this forward binding); D4 applies to dispatches made after the dispatch templates carry the teardown line. In-flight dispatches running pre-merge templates are grandfathered. No retroactive sweep of historical worktrees beyond what D3's prune reclamation organically collects.

### Enforcement (rule #23 — established by the co-submitted no-rule-without-a-check ADR shipping in the same slice-1 PR)

Deterministic: D5's Health group + guard non-zero exits + D1's orchestrator contract (checkable in /ship SKILL.md text by CI grep; observable per-dispatch in session logs). Shadow: silent isolation escape / guard theater. Existing-mechanism check: ADR-0036/0041 prose covers intent but nothing asserts engagement; the audit proved the gap live.

## Alternatives considered

- **Trust the harness (status quo):** rejected — #746 is a measured counterexample.
- **Abandon worktrees for clone-per-dispatch:** rejected — heavier on disk/time; worktrees work when asserted; the failure was the absence of assertion, not the mechanism.
- **Correlation-ID plumbing through every event:** rejected for now — D5's `wt`-field detection plus the capture-liveness session SLO (decided by the co-submitted hook fail-loud ADR shipping in the same slice-1 PR) cover the observable need without a new ID scheme; revisit if trail reconstruction still gaps.

## References

- ADR-0036 (isolation mandate; D3 superseded here), ADR-0041 (guard origin; semantics superseded here), issues #746/#673/#732/#685, CLAUDE.md I4a, workflow-v2 synthesis §B6 (2026-06-12).
