---
title: R-CLOSES — reviewer hard-block on PR body missing valid slice-issue Closes link
summary: The reviewer rule that requires every slice PR's body to contain a `Closes #<n>` line pointing to a valid slice-labeled GitHub Issue; the load-bearing PR-to-slice audit-trail link.
tags: [rule, reviewer-rubric, hard-block]
type: concept
last_updated: 2026-05-26
sources:
  - .claude/agents/reviewer.md rule 10
  - CLAUDE.md
---

# R-CLOSES

**R-CLOSES** is rule 10 in the [`reviewer`](../../../.claude/agents/reviewer.md) rubric. It requires that every slice PR's body contain a `Closes #<n>` line pointing to a valid `slice`-labeled GitHub Issue. The rule is mechanical (grep-checkable from the PR body) and BLOCKs on absence. The glossary stub at [[concepts/glossary/r-closes]] is the short vocabulary entry; this note is the full rule definition.

## What

The rule fires on every PR the reviewer judges. Mechanics:

- Reviewer reads the PR body via `gh pr view <PR> --json body`.
- Greps for `Closes #<n>` (case-insensitive; also accepts `Fixes #<n>` / `Resolves #<n>` per GitHub's keyword set, though canonical is `Closes`).
- Looks up issue `<n>` via `gh issue view <n> --json labels`.
- Confirms the label set includes `slice` for ordinary slice PRs, `trivial` for trivial-lane PRs, or `prd` for PRD-tier PRs.

BLOCK paths:

- Missing `Closes #N` line → BLOCK with `R-CLOSES: PR body missing Closes #<n> line; every slice PR must close exactly one slice-labeled issue`.
- Referenced issue does not exist → BLOCK with `R-CLOSES: referenced issue #<n> does not exist`.
- Referenced issue exists but lacks the required label → BLOCK with `R-CLOSES: referenced issue #<n> is not labeled slice (labels: <list>)`.

A single PR MAY close multiple issues (e.g., `Closes #248, Closes #245` for a terminal slice that closes both its slice AND its parent PRD). The rule fires per `Closes #N` line; the FIRST line must resolve to a `slice`-labeled (or label-appropriate) issue.

## Why

R-CLOSES exists because **the PR-to-slice binding is the load-bearing link of the audit trail**. Without it, merged PRs become unanchored from the planning artifact that authorized them. Downstream consumers — the workflow event log, the post-merge `git log` changelog, the future `/audit-meta` skill, the impact-analyst per [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D8 — all rely on the binding to reconstruct "what was this PR FOR?".

The check is mechanical because the failure mode is silent: a PR with no `Closes #N` line still merges cleanly; the audit gap only surfaces when someone tries to walk backward from `main` to PRD. Pairing R-CLOSES with [I2](../../../CLAUDE.md) (the slice-grabbing protocol — first agent to assign themselves owns the slice) closes the loop: the slice issue is claimed by exactly one implementer, that implementer's PR closes it on merge, `--delete-branch` cleans up the workspace, and the slice issue's auto-close on merge proves the link fired.

## How to check

```bash
gh pr view <PR> --json body --jq '.body' | grep -iE '(closes|fixes|resolves) #[0-9]+'
```

For each `#N` extracted, verify the label:

```bash
gh issue view <N> --json labels --jq '.labels[].name' | grep -E '^(slice|trivial|prd)$'
```

Match the label to the PR's tier:
- Ordinary slice PR (no special label) → must close `slice`.
- `trivial`-labeled PR → must close `trivial` (or `slice` if a slice-tier issue exists).
- `prd`-labeled PR → must close `prd`.

## Exemptions

- **Trivial-lane PRs** labeled `trivial`: may close a `trivial`-labeled audit-trail issue.
- **PRD-tier PRs** labeled `prd`: may close a `prd`-labeled issue (the PRD itself).
- **Unlabeled PRs that clearly fit the slice tier** (modify `.claude/agents/` or `.claude/skills/`): apply R-CLOSES against `slice`-labeled issues.

## Examples

- **Slice PR with `Closes #254` (slice-labeled)**: PASS.
- **Slice PR with `Refs #254` instead of `Closes #254`**: BLOCK — GitHub doesn't auto-close on `Refs`; the issue rots.
- **Slice PR with `Closes #N` in the commit subject but not the PR body**: BLOCK — CLAUDE.md rule #5 explicitly forbids; canonical location is the PR body.
- **Terminal slice PR closing both slice and PRD**: `Closes #248, Closes #245` — PASS, each line verified independently.

## Edges

- **part_of:** [[entities/subagents/reviewer]]
- **defines:** [[concepts/glossary/r-closes]]
- **related_to:** [[concepts/rules/r-loc]]
- **related_to:** [[concepts/rules/r-meta]]
- **part_of:** [[topics/reviewer-philosophy]]
