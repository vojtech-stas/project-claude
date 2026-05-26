---
title: reviewer edge cases — 7 special-case handling paths A-G
summary: The 7 edge-case handling paths in the reviewer body (huge diff / previous rounds / merge conflicts / fork PRs / ADR disagreement / no-CLAUDE.md / auto-merge failure).
tags: [reviewer, edge-cases, topic]
type: topic
last_updated: 2026-05-26
sources:
  - .claude/agents/reviewer.md
  - decisions/0002-autonomous-merge-policy.md
---

# reviewer edge cases

Seven enumerated edge cases the [`reviewer`](../../entities/subagents/reviewer.md) subagent handles outside its standard 12-rule rubric pass. Each is a specific operational situation where the standard verdict flow needs an explicit alternative path or a clarified disposition. All seven are pulled verbatim from `.claude/agents/reviewer.md` and are preserved here as the canonical KB-layer reference; the reviewer's own body links to this topic page.

## A. The diff is huge (>1000 lines)

Pulled verbatim from `.claude/agents/reviewer.md`:

> Split your review by file group. Still apply hard rules to each group. Note in your comment that the PR is unusually large — recommend splitting into smaller slices for future work, but only BLOCK if a hard rule is violated.

The crossover with [R-LOC](../concepts/rules/r-loc.md): R-LOC's 300-LoC cap applies only to runtime-artifact code. A docs-heavy 1000+ LoC PR can pass R-LOC and still be unwieldy to review; this edge case handles that gap. The disposition is *recommend smaller slices in the comment*, not BLOCK — diff size alone is not a hard-block rule.

## B. The implementer has already addressed previous review rounds

Pulled verbatim from `.claude/agents/reviewer.md`:

> Look for previous reviewer comments via `gh pr view <PR> --comments`. Check whether the previous BLOCK reasons are now resolved. If so, focus your review on the new changes only. Increment the round counter.

The round counter feeds the [I5 escalation surface](../../../CLAUDE.md): on round-3 BLOCK, the reviewer applies the `needs-human` label and comments on the parent PRD. Counting rounds correctly is therefore load-bearing — if the reviewer fails to detect a previous BLOCK comment, the round counter under-counts and the escalation fires late. Use `gh pr view <PR> --comments --jq '.comments[].body' | grep -c "reviewer verdict: BLOCK"` as the mechanical check.

## C. The PR has merge conflicts

Pulled verbatim from `.claude/agents/reviewer.md`:

> BLOCK with reason "merge conflicts with base branch must be resolved before review can complete". The implementer must rebase.

This is the one situation where the reviewer BLOCKs without applying the 12-rule rubric — the diff cannot be meaningfully judged until conflicts resolve. The implementer's reaction is mechanical: `git fetch origin main && git rebase origin/main`, fix conflicts, force-push the feature branch (`--force-with-lease`).

## D. The PR is from a fork

Pulled verbatim from `.claude/agents/reviewer.md`:

> Apply the same rules. No special handling for the verdict. For auto-merge: `gh pr merge` works on fork PRs the same way.

External contributors are subject to the same rubric. The reviewer does NOT relax R-CLOSES, R-LOC, R-META, or any other rule for forks. The `gh pr merge --squash --delete-branch` command works identically; branch deletion happens on the contributor's fork via the GitHub API.

## E. You disagree with an ADR

Pulled verbatim from `.claude/agents/reviewer.md`:

> If the PR's approach seems wrong but it follows an existing ADR, APPROVE (with a recommendation that the ADR be revisited in a future slice). The ADR is the rule; your opinion is not.

This is the explicit ADR-supremacy rule. ADRs are the project's immutable decision substrate per [decisions/README.md](../../../decisions/README.md); the reviewer's opinion does not override an accepted ADR. The correct path for disagreement is a [Recommendation](reviewer-philosophy.md) noting the disagreement, optionally paired with a `captured`-labeled GitHub issue per [CLAUDE.md rule #11](../../../CLAUDE.md) to propose a superseding ADR in a future PRD.

This rule pairs with [R-ADR-CONFLICT](../concepts/rules/r-adr-conflict.md): the reviewer BLOCKs only when the PR *contradicts* an ADR without superseding it. A PR that follows the ADR is APPROVED regardless of the reviewer's preference.

## F. The repo has no CLAUDE.md or ADRs

Pulled verbatim from `.claude/agents/reviewer.md`:

> Note this in your comment as a recommendation to add them. Apply universal hard rules (Conventional Commits, no commits to main, no secrets, PR body completeness, scope drift via PR-body comparison). For YAGNI: skip ONLY if neither CLAUDE.md nor any ADR encodes YAGNI as a project rule. If even one of them encodes it, apply YAGNI normally. Skip ADR-conflict check entirely (no ADRs to conflict with).

This is the reviewer's degradation path for bare-repo invocation. The universal rules (R-CONV-COMMITS, R-NO-MAIN, R-SECRETS, R-PR-BODY, R-SCOPE) are always applicable; the project-specific rules (R-YAGNI, R-ADR-CONFLICT) are conditionally applicable based on whether the encoding documents exist. The reviewer is portable across repos this way — it degrades gracefully rather than failing.

R-LOC, R-CLOSES, R-META, R-TRUTH-DOC, and R-BOY-SCOUT are project-specific to this repo's `.claude/` + `decisions/` + `docs/current/` layout. In a bare-repo invocation, they don't fire by trigger absence.

## G. Auto-merge fails after APPROVE

Pulled verbatim from `.claude/agents/reviewer.md`:

> If `gh pr merge` returns an error (status checks pending, merge conflict appeared, branch protection, permissions), do NOT retry. Return `MERGE_STATUS: failed: <error>` and post a follow-up comment on the PR explaining the auto-merge failure. The orchestrating agent or human takes it from there.

The no-retry rule is intentional: the reviewer's authority is gated on its own APPROVE verdict ([ADR-0002](../../../decisions/0002-autonomous-merge-policy.md)). If auto-merge fails, the failure mode is investigated by the orchestrator or human, not papered over by retry loops. `MERGE_STATUS: failed: <error>` is a permitted reviewer-specific CRITIC-trailer extension per [[topics/output-shapes]] and is the load-bearing signal for the orchestrator's downstream branching.

Common failure causes: branch-protection settings (required status checks pending), merge conflict appearing between the reviewer's read of the diff and the merge attempt (a race with another merge to main), permissions issue (the gh CLI's auth token doesn't have merge rights on the target repo).

## Edges

- **defines:** none
- **part_of:** [[entities/subagents/reviewer]]
- **related_to:** [[topics/reviewer-philosophy]]
- **related_to:** [[topics/output-shapes]]
- **related_to:** [[concepts/rules/r-loc]]
- **related_to:** [[concepts/rules/r-adr-conflict]]
