---
title: git workflow — operational logic for starting, working, finishing, reviewing, and merging a slice
summary: The canonical operational HOW of the per-slice git lifecycle in this project — branch creation from latest main, slice claiming (I2), Conventional Commits discipline within the slice, PR template, reviewer gate and auto-merge (ADR-0002), and the anti-pattern list (force-push, direct-main commits, long-running branches, bundled commits, vague messages).
tags: [git, workflow, conventional-commits, branch-naming, reviewer, auto-merge, topic]
type: topic
last_updated: 2026-05-27
sources:
  - CLAUDE.md
  - decisions/0002-autonomous-merge-policy.md
  - decisions/0003-autonomous-pipeline-with-critics.md
---

# git workflow — per-slice operational lifecycle

The canonical per-slice git-lifecycle operational reference. Follow this EVERY time. This is the operational logic — not just the principle. Synthesized from `CLAUDE.md` "Operational git workflow" section (slimmed into a pointer in T6 of [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D10 step 6).

**EnforcedBy:** [[../../entities/subagents/reviewer.md]]
**ImplementsRule:** [[../../concepts/glossary/conventional-commits.md]]
**RelatedTopic:** [[pipeline-stages.md]]
**RelatedDecision:** [[../../../decisions/0002-autonomous-merge-policy.md]]

---

## Starting a slice

```bash
git checkout main
git pull --ff-only origin main          # always start from latest main
git checkout -b <type>/<issue-number>-<kebab-summary>
gh issue edit <issue-number> --add-assignee @me   # claim the slice (I2)
```

**Branch naming:** `<type>/<issue-number>-<kebab-summary>` — where `<type>` is from the Conventional Commits set (`feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `perf`, `style`, `build`, `ci`) plus `hotfix/` for the trivial lane (I3). Examples:
- `feat/4-ship-orchestrator-skeleton`
- `feat/7-reviewer-enforcement-additions`
- `docs/8-claude-md-conventions-rollup`
- `hotfix/<issue-number>-fix-typo-in-readme` (the pre-commit regex enforces an issue number for all types, even trivial-lane hotfixes — use the closing audit-trail issue number)

The `slice-N-<name>` pattern from earlier slices is retired; GitHub issue numbers replace the slice number.

## Working within a slice

- Commit at meaningful checkpoints, not just at the end. Each commit = one coherent step.
- Apply CLAUDE.md rule #5 (Conventional Commits, tightened): lowercase subject, ≤72 char cap, `Co-authored-by:` trailer for agent commits.
- Message body (after blank line) explains WHY. Bullet points OK.
- If the slice grows beyond its planned scope → **STOP** and discuss with the user. Don't sneak extras in.

## Finishing a slice

```bash
git push -u origin <branch>
gh pr create --title "<conv-commits-style title>" --body "<see template below>"
```

**PR body MUST include:**
- **`Closes #<slice-issue>`** — links the PR to its slice (reviewer enforces).
- **Scope** — what's in.
- **Out-of-scope** — what's deliberately NOT in this slice.
- **Verification** — concrete steps to confirm it works.
- **ADR reference** — link to any new ADR if this slice made a design decision.

## Reviewing

Per [ADR-0002](../../../decisions/0002-autonomous-merge-policy.md) (autonomous merge at PR level) and [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D4 (no human gates between pipeline stages), the `reviewer` subagent is the **sole gate per PR**. There are no per-stage human checkpoints in the standard flow — the human enters at `/grill-me` (input) and `/qa-plan` (acceptance), nothing in between.

The reviewer:
- Reads PR body + diff + CLAUDE.md + ADRs + linked slice issue.
- Posts a structured verdict comment via `gh pr comment`.
- **APPROVE** → auto-merges with `gh pr merge --squash --delete-branch`. No human action.
- **BLOCK** → returns the PR to the implementer for fixes. On round-3 BLOCK, applies the `needs-human` label and posts to the parent PRD (I5).

**Bootstrap exception (PRD #3 only):** the slices of PRD #3 ran with per-stage human checkpoints to validate the pipeline before fully enabling it. That exception ended with PRD #3's merge. From PRD #4 onward, reviewer is the sole gate per PR; no human checkpoints between stages.

## Merging

- `reviewer` subagent merges with `gh pr merge --squash --delete-branch` on APPROVE only (per ADR-0002). Never on BLOCK.
- Merge style: **squash-and-merge** always — one commit per slice on `main`, clean history.
- After merge (`--delete-branch` auto-deletes the remote branch):
  ```bash
  git checkout main
  git pull --ff-only origin main
  ```

## What NOT to do

- `git push --force` to a shared branch (use `--force-with-lease` if rewriting a feature branch is truly necessary)
- Commits on `main` directly
- Long-running branches (>1 week without merge) — split into smaller slices instead; reviewer marks stale per I4
- Bundle multiple unrelated changes in one commit
- Vague messages: `fix stuff`, `update`, `wip`, `final`
