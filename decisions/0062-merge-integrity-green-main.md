# 0062 — Merge integrity: the not-rocket-science invariant + a green-main pointer

- **Status:** Accepted
- **Date:** 2026-06-12
- **Extends:** ADR-0042 D3 (reviewer merges with `--auto` merge-when-checks-pass — inoperative on this repo because the auto-merge repository setting is disabled; this ADR codifies the working replacement loop observed live, and D3 resumes if the setting is ever enabled); ADR-0041 D3 (root ff-sync after merge — gains a post-merge verification step and a recorded event)

## Context

Parallel slice waves race to merge: squash-merging sibling PRs leaves the rest BEHIND main, and GitHub auto-merge is disabled on this repo, so reviewers hit "BEHIND / auto-merge not allowed" — observed on four separate PRs across this run, each resolved ad-hoc with an undocumented update-branch dance. The deeper gap: nothing ever attests that merged main AS A WHOLE works — every gate runs pre-merge on branches; the stale-server incidents proved merged-main state can silently diverge from what anyone verified. The fleet principle (Bors' "not rocket science" rule): every commit lands only after testing against the exact main it lands on; its TAP complement: the merged whole is continuously attested.

## Decisions

### D1 — BEHIND is recoverable: the update-branch retry loop is contract

The merge step for every reviewer (and any orchestrator merge collection) treats a BEHIND/blocked merge as recoverable: `gh pr update-branch <n>` → await the re-triggered `ci` check → retry `gh pr merge --squash --delete-branch`, bounded at 3 attempts, then report honestly. Reviewer `MERGE_STATUS:` gains `behind-retried: <n>` when the loop ran. This codifies the loop already proven live; per ADR-0004 D2 (bootstrap-mode) it binds forward from the reviewer-prompt merge.

### D2 — Merges serialize; implementation stays parallel

When multiple sibling PRs are simultaneously APPROVE-ready, merges execute one at a time in completion order (each through D1's loop). Implementer dispatches remain fully parallel — only the terminal ~minutes-long merge step serializes, guaranteeing every squash lands on the main it was CI-tested against (the not-rocket-science invariant) without hosted merge-queue infrastructure. Binds forward per ADR-0004 D2.

### D3 — Green-main pointer: post-merge verification with a recorded event

After each merge + root-sync, the orchestrator runs a post-merge verify on actual merged main — `bash tools/ci-checks.sh` plus a dashboard smoke (the `/api/meta` SHA handshake from wave 1; pytest joins when a later wave ships the test suite) — and appends a `main_green` event (`{"v":2,"ts":...,"event":"main_green","sha":...}` — matching the ADR-0016 v2 schema's mandatory fields) to the workflow event log via the canonical logger pattern. On failure: the 1–3 squash commits since the last green pointer are the suspect set (≤300 LoC slices make bisect degenerate); revert flows through the trivial lane. Green-pointer lag (`rev-list <last-green>..origin/main --count`) is the standing metric; wrap-ups require lag 0. Binds forward per ADR-0004 D2.

### D4 — Scope boundary

This is one orchestrator step and one event type — NOT a CI platform: no hosted merge queue (unavailable on personal repos; D1+D2 deliver the invariant without it), no stacked-PR tooling (≤300 LoC slices + DAG parallelism already give the benefit), no canary/traffic staging (no traffic exists; noted for template consumers building apps).

## Consequences

- Logically-incompatible green PRs can no longer land unattested; "merged main works" becomes a recorded, lag-measurable claim instead of an assumption; the BEHIND dance stops being tribal knowledge.
- Each merge costs one extra ci-checks + smoke run (~seconds); serialization adds minutes to multi-PR waves — the price of the invariant.

### Enforcement (rule #23)

Deterministic: a dashboard green-pointer row (last `main_green` sha + lag vs origin/main + age; red on lag > 0 at wrap-up or stale > 24h) and merge-race counters (BEHIND encounters / recovered / unrecovered per session, parsed from the event log + MERGE_STATUS fields). Parsimony: extends the existing reviewer merge step and root-sync hook of ADR-0041/0042 — no new agent, no new infrastructure. Shadow: unattested merged main + ad-hoc merge races.

## Alternatives considered

- **GitHub merge queue:** rejected — unavailable on personal repos; D1+D2 deliver the same invariant with zero platform dependency.
- **Enable repo-level auto-merge instead:** rejected for now — repo-settings changes are permission-gated to the human; the loop works without it and remains correct if the setting later flips.
- **Full post-merge test pyramid (TAP-style):** deferred — ci-checks + smoke is the honest maximum until the test-suite wave lands; the event schema already accommodates richer verification.

## References

- ADR-0042 D3 (auto-merge intent being adapted), ADR-0041 D3 (root-sync being extended), ADR-0016 (event log the `main_green` event joins), ADR-0004 D2 (bootstrap-mode), live BEHIND incidents (PRs #748 #759 #761 #770-773 range), stale-server incidents (#623/#685 class), workflow-v2 synthesis §B11/§C2 (2026-06-12).
