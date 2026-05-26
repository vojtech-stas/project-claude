---
title: R-NO-MAIN — reviewer hard-block on direct commits or pushes to main
summary: The reviewer rule that BLOCKs any PR whose head branch is `main` or whose diff contains direct commits to `main`, enforcing the never-push-to-main discipline at PR review time.
tags: [rule, reviewer-rubric, hard-block]
type: concept
last_updated: 2026-05-26
sources:
  - .claude/agents/reviewer.md rule 5
  - CLAUDE.md
---

# R-NO-MAIN

**R-NO-MAIN** is rule 5 in the [`reviewer`](../../../.claude/agents/reviewer.md) rubric. It hard-blocks any PR whose head branch is `main` or whose diff contains direct commits to `main`. The rule mechanically enforces CLAUDE.md cross-cutting rule #4 ("Never push directly to `main`") at PR review time and complements the server-side branch-protection layer (when configured) plus the `.claude/hooks/pre-tool-bash-push.sh` PreToolUse hook (PR #203) that prevents `git push origin main` from main-agent context.

## What

The rule fires on every PR. Mechanics:

- Reviewer reads `gh pr view <PR> --json baseRefName,headRefName`.
- Asserts `baseRefName == "main"` AND `headRefName != "main"`.
- If `headRefName == "main"` → BLOCK with `R-NO-MAIN: PR head branch is main; every change must ship via a feature branch`.
- If the diff somehow contains direct commits to `main` (force-push residue, misconfigured branch) → BLOCK.

R-NO-MAIN is paired with branch protection (the configured-server-side layer) and the local-tool layer; together they form defense-in-depth around the `main` integrity invariant.

## Why

R-NO-MAIN exists because **`main` is the single source of truth for every downstream consumer**: deployed agents, the workflow event log, the `git log` changelog, future bisects. Direct commits bypass the reviewer gate (which is the project's sole PR-tier gate per [ADR-0002](../../../decisions/0002-autonomous-merge-policy.md) D9-revised) and bypass [R-CLOSES](r-closes.md)'s audit-trail enforcement. A direct commit to `main` is a slice with no PRD, no slice issue, no PR, no reviewer verdict — an audit black hole.

The rule is intentionally a mechanical reject rather than a judgment call. There are zero legitimate cases where a slice should land via direct push instead of a feature branch + PR; the trivial-lane (`hotfix/` branch) exists precisely so even one-line fixes go through the PR flow.

## How to check

```bash
gh pr view <PR> --json baseRefName,headRefName
```

Base should be `main`, head should NOT be `main`. Cross-check via:

```bash
git log origin/main --first-parent --oneline -5
```

Every commit on `main` should be a squash-merge of a feature PR (subject prefixed with `<type>(<scope>): ...` matching [R-CONV-COMMITS](r-conv-commits.md), trailer `(#<pr-number>)` from squash-merge).

## Exemptions

- **Initial bootstrap commits** (pre-pipeline; grandfathered): visible in early history of the repo before branch protection was configured. Not subject to retroactive enforcement (bootstrap-mode per [ADR-0004](../../../decisions/0004-bypass-prevention.md) D2).
- **None going forward**: every change post-pipeline-bootstrap MUST flow through a feature branch.

## Examples

- **PR opened from `main` → `main`**: BLOCK at the PR-view step.
- **Direct `git push origin main` from main-agent context**: prevented by `.claude/hooks/pre-tool-bash-push.sh` (PR #203) before R-NO-MAIN can even fire; defense-in-depth.

## Edges

- **part_of:** [[entities/subagents/reviewer]]
- **related_to:** [[concepts/rules/r-closes]]
- **part_of:** [[topics/reviewer-philosophy]]
