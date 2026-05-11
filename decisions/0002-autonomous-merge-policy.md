# ADR-0002: Autonomous merge policy with QA-level human checkpoint

- **Status:** Accepted
- **Date:** 2026-05-12
- **Supersedes:** D9 in ADR-0001 (in part — the rest of ADR-0001 stands)
- **Decided in:** Live revision during slice 3, after the first dogfood test of the reviewer subagent on PR #1

---

## Context

ADR-0001 D9 specified *"Human is always the final merge gate."* This was the conservative starting point — every PR required a human merge click.

After running the first walking-skeleton dogfood test (simulated reviewer audit on PR #1), the project owner revised the policy:

> *"I actually feel that the PR should be also autonomous. I need to be invited to the table only when you feel like you have done all the things on PRD to let me check if it all works by giving me test cases on QA."*

**Rationale:** Human-merge-per-PR is too tactical. The owner wants to play strategic senior engineer who validates STRATEGIC milestones (full PRDs complete) via acceptance tests — not every commit, not every PR. The reviewer subagent's verdict is trusted to gate per-PR merges.

This is a foundational policy shift. It changes WHERE the human's attention is spent in the pipeline.

---

## Decisions

### D9-revised: Auto-merge on reviewer APPROVE

- Reviewer subagent's **APPROVE** verdict triggers auto-merge (`gh pr merge --squash`).
- Reviewer subagent's **BLOCK** verdict sends the PR back to the implementer for fixes (the implementer-reviewer loop).
- After **N rounds** of BLOCK on the same PR, escalate to the human. Initial value: **N = 3**. Tuneable.
- Reviewer NEVER merges on its own arbitrary judgment — only on explicit APPROVE per its own rule set.

### Human checkpoint at PRD level, via `qa-plan`

The human is invited when:
1. All GitHub issues for a PRD have been merged.
2. The orchestrating agent invokes the `qa-plan` skill to generate a structured acceptance-test checklist.
3. The human runs the QA plan, marks pass/fail, posts results.
4. If ALL pass → PRD shipped (close it).
5. If ANY fail → failed acceptance criteria reopen as issues; implementer-reviewer cycle resumes for those.

### Pre-conditions for enabling autonomy

Autonomy is OFF until ALL of these are in place:

1. **Reviewer rule set tuned** based on PR #1 dogfood feedback (3 items: declarative-exemption tightening, edge-case-F clarification, output-format portability) — addressed in this slice.
2. **`qa-plan` skill exists** — the human handoff artifact — addressed in this slice.
3. **CLAUDE.md updated** to reflect the new policy — addressed in this slice.

Once slice 3.1 (this PR) merges, autonomy is ON starting from slice 4.

### Until slice 3.1 ships

PR #1 (slice 3) and this PR (slice 3.1) are still **human-merged** under the legacy policy. The new policy applies forward, not retroactively.

### What the reviewer subagent is now authorized to do

In addition to its previous tools (Read, Glob, Grep, Bash for read-only inspection + comment posting), the reviewer is now authorized to execute:

```bash
gh pr merge <PR> --squash --delete-branch
```

— **only when its own verdict is APPROVE** and only via `--squash` mode (per CLAUDE.md merge style). The reviewer's system prompt enforces this discipline.

The reviewer is NOT authorized to:
- Merge with any other strategy (`--merge` or `--rebase`)
- Merge a PR with a BLOCK verdict
- Force-merge bypassing checks
- Re-open or modify the merged PR

### Branch protection (deferred)

GitHub branch protection requiring PRs (and disallowing direct main pushes) is still deferred to **slice 7**. Until then, the policy is enforced by discipline (CLAUDE.md rule + reviewer's authority). The reviewer's `gh pr merge` calls use the human's `gh` auth token — from GitHub's perspective, it's "the human merging via API". Acceptable for early iteration; slice 7 will set up proper bot identity.

---

## Consequences

### Positive

- **Throughput.** AI does the full PR cycle without human bottleneck.
- **Strategic human role.** Owner's attention is reserved for QA-level validation, not per-PR review.
- **Forces reviewer quality.** The reviewer subagent's rule set must be reliable; that pressure surfaces bugs in the rules earlier.
- **Demonstrates the workflow value.** A fully autonomous PRD-to-shipped cycle is a real demo of the project's thesis.

### Negative / accepted trade-offs

- **Reviewer is load-bearing.** A wrong APPROVE = bad code in public main. Mitigation: tuned rules, max-N-rounds escalation, qa-plan catches end-to-end issues, the owner can `git revert` and reopen.
- **Public repo, public history.** Every auto-merged commit is permanently visible. Owner has accepted this.
- **Loss of per-PR human signal.** The owner won't catch subtle issues the reviewer misses until QA. Mitigation: qa-plan should be thorough; bad reviewer verdicts surface as failed QA tests, which feed back into tuning.
- **Loop-cap escalation needs handling.** When max-N rounds of BLOCK trigger, the human must be paged. Initial implementation: the orchestrating agent leaves a `@vojtech-stas` mention in a PR comment and stops. Full notification mechanism in slice 7.

---

## Alternatives considered

### Alt-A: Stay with human-merge per PR (status quo from ADR-0001 D9)
Rejected. Owner explicit: too tactical, wrong checkpoint.

### Alt-B: Auto-merge only "trivial" PRs (e.g., docs-only, dependency bumps)
Rejected. "Trivial" is subjective and hard to operationalize without becoming arbitrary. Either trust the reviewer or don't.

### Alt-C: Human approves at PR, reviewer auto-merges after approval
Rejected. Same as old "human merges" but with an extra step; no autonomy gain.

### Alt-D: Branch-protection-required GitHub Actions reviewer
Considered for the future. Slice 7 will set up CI/Actions for proper bot-identity merging. For now, the agent-on-user's-token model is sufficient.

### Alt-E: Allow reviewer to auto-merge but require human ack within 24h or auto-revert
Rejected as too complex for v0.1. If the reviewer's verdict is bad enough to need reverting, the qa-plan should catch it; if qa-plan doesn't catch it, the human can revert manually.

---

## Open questions deferred

| Question | Deferred to |
|---|---|
| Exact value of max-N rounds (initial: 3) | Tune after first 5 real PRs |
| What constitutes "the same PR" across BLOCK iterations (force-push? new commits only? rebase?) | Slice 4 dogfood |
| Whether the orchestrating agent pages the human on escalation via `@vojtech-stas` mention vs. another channel | Slice 7 |
| Whether `qa-plan` should be invoked auto on PRD-close or only manually | Decide after first PRD ships |
| Whether GitHub Actions runs reviewer in CI vs. only Claude Code session | Slice 7 |

---

## References

- ADR-0001 (foundational design) — D9 partially superseded by this ADR
- PR #1 (slice 3 walking-skeleton kit) — the dogfood that surfaced this revision
- `.claude/agents/reviewer.md` (updated in this slice with auto-merge authority)
- `.claude/skills/qa-plan/SKILL.md` (introduced in this slice as the human handoff artifact)
