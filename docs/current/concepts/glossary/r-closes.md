---
title: R-CLOSES — reviewer rule binding PR body to slice issue
summary: The reviewer rule that every slice PR's body must contain a Closes #<n> line pointing to a valid slice-labeled issue (with exemptions for trivial and prd PRs against issues of the matching tier).
tags: [glossary, reviewer-rule, project-jargon, pipeline]
type: concept
last_updated: 2026-05-26
sources:
  - .claude/agents/reviewer.md
  - CLAUDE.md
---

# R-CLOSES

**R-CLOSES** is rule 10 in the [`reviewer`](../../../.claude/agents/reviewer.md) rubric. It requires that every slice PR's body contain a `Closes #<n>` line pointing to a valid `slice`-labeled GitHub Issue. The rule is mechanical (grep-checkable from the PR body) and BLOCKs on absence; exemptions exist for `trivial`-labeled and `prd`-labeled PRs against issues of the matching tier.

**Edges**

- **related-to:** [[concepts/glossary/r-loc]]
- **related-to:** [[concepts/glossary/r-meta]]
- **part-of:** [[entities/subagents/reviewer]]

## What

The rule fires on every PR the reviewer judges. Mechanics:

- Reviewer reads the PR body (via `gh pr view --json body`).
- Greps for `Closes #<n>` (case-sensitive; bare `closes #N` and `Fixes #N` are accepted as equivalent per GitHub's keyword set, but reviewer prefers the canonical `Closes`).
- Looks up issue `<n>` via `gh issue view --json labels`.
- Confirms the label set includes `slice` for ordinary slice PRs, `trivial` for trivial-lane PRs, or `prd` for PRD-tier PRs.

BLOCK paths:

- Missing `Closes #N` line → BLOCK with "PR body missing `Closes #<n>` line".
- Referenced issue does not exist → BLOCK with "referenced issue #<n> does not exist".
- Referenced issue exists but lacks the required label → BLOCK with the labels listed.

A single PR MAY close multiple issues (e.g., `Closes #248, Closes #245` for a slice that closes both its slice AND its parent PRD because it satisfies the PRD's full acceptance criteria). The rule fires per `Closes #N` line; the FIRST line must resolve to a `slice`-labeled issue.

## Why

R-CLOSES exists because **the PR-to-slice binding is the load-bearing link of the audit trail**. Without it, merged PRs become unanchored from the planning artifact that authorized them. Downstream consumers — the workflow event log, the post-merge `git log` changelog, the future `/audit-meta` skill — rely on the binding to reconstruct "what was this PR FOR?" The check is mechanical because the failure mode is silent: a PR with no `Closes #N` line still merges cleanly; the audit gap only surfaces when someone (or some future agent) tries to walk backward from main to PRD.

Pairing R-CLOSES with I2 (the slice-grabbing protocol — first agent to assign themselves owns the slice) closes the loop: the slice issue is claimed by exactly one implementer, that implementer's PR closes it on merge, and `--delete-branch` cleans up the workspace. The reviewer's R-CLOSES check is what ensures the "closes on merge" half of that loop actually fires.

## Examples from this project

- **A slice PR that drifted into a hotfix** — R-CLOSES still fires; if the PR drifted to fix a typo, the implementer must either trim the PR back to the slice's "What ships" OR open a separate `hotfix/` PR labeled `trivial` against an audit-trail issue.
- **A PRD that closes via its terminal slice** — the terminal slice's PR may include both `Closes #<slice>` AND `Closes #<prd>`; R-CLOSES validates each independently against the appropriate label tier.
- **A trivial-lane PR** — labeled `trivial`, body says `Closes #<hotfix-audit-issue>`; R-CLOSES accepts because the issue is labeled `trivial`.

## Anti-patterns

- **`Closes #N` in the commit subject instead of the PR body** — CLAUDE.md rule #5 explicitly forbids this; the body is the canonical location.
- **`Refs #N` instead of `Closes #N`** — GitHub does not auto-close on merge with `Refs`; the audit-trail link survives but the issue stays open and rots.
- **Slice PR with `Closes #<prd>` only** — closes the PRD but orphans the slice issue, defeating the per-slice tracking I2 was designed to provide.

## Scope

(a) project jargon coined here

## Authority

[`.claude/agents/reviewer.md`](../../../.claude/agents/reviewer.md) rule 10

## References

- [`.claude/agents/reviewer.md`](../../../.claude/agents/reviewer.md) rule 10 — canonical R-CLOSES definition with all BLOCK paths and exemptions.
- [ADR-0002](../../../decisions/0002-autonomous-merge-policy.md) — autonomous merge depends on the PR-to-slice binding being verifiable.
- [CLAUDE.md](../../../CLAUDE.md) I2 — slice-grabbing protocol; the planning-side counterpart to R-CLOSES's audit-trail enforcement.
- [[concepts/glossary/r-loc]] — sibling reviewer rule capping runtime-artifact diff.
- [[concepts/glossary/r-meta]] — sibling reviewer rule enforcing ADR provenance.
- [[entities/subagents/reviewer]] — the subagent that owns this rule.
