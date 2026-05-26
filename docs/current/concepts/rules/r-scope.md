---
title: R-SCOPE — reviewer hard-block on scope drift outside PR body
summary: The reviewer rule that BLOCKs any PR whose diff modifies files or areas not justified by the PR body's stated scope.
tags: [rule, reviewer-rubric, hard-block]
type: concept
last_updated: 2026-05-26
sources:
  - .claude/agents/reviewer.md rule 1
  - decisions/0001-foundational-design.md D12
---

# R-SCOPE

**R-SCOPE** is rule 1 in the [`reviewer`](../../../.claude/agents/reviewer.md) rubric. It hard-blocks any PR whose diff modifies files or areas not justified by the PR body's stated **Scope** section. R-SCOPE is the project's primary anti-drift gate at PR review time, paired with the policy-level YAGNI rule ([R-YAGNI](r-yagni.md)) and the audit-trail link ([R-CLOSES](r-closes.md)).

## What

The rule fires on every PR the reviewer judges. Mechanics:

- Reviewer parses the PR body's **Scope** and **Out-of-scope** sections (required by [R-PR-BODY](r-pr-body.md)).
- For each file in `gh pr diff <PR> --name-only`, the reviewer asks: *is this file's modification justified by the PR body's scope?*
- If any modified file falls outside the stated scope, BLOCK with `Scope drift: <file> not justified by PR body's scope section`.

The check is judgment-shaped — the reviewer reads the scope statement and matches it against the diff's file paths and the nature of each change. A scope-aligned file with a scope-misaligned change (e.g., a stated reviewer.md thinning PR that also adds a new rule) is also a scope-drift BLOCK.

## Why

R-SCOPE exists because **uncontrolled drift compounds across PRs**. Without it, an implementer's "while I'm here" edit lands silently, future readers cannot tell what was the slice's intent vs an opportunistic side change, and `git revert` of the slice unwinds unrelated work. The PR body's Scope section is the spec contract; R-SCOPE is the mechanical enforcement that the diff matches the contract.

Pairing R-SCOPE with the PRD-tier scope lock (Non-goals section per [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D1) creates layered defense: the PRD bounds the feature, the slice bounds the work-session, and R-SCOPE enforces the PR matches what the slice promised. The cost of a false-positive BLOCK is one revision cycle; the cost of a false-negative APPROVE is permanent scope creep on `main`.

## How to check

For each changed file in the diff, ask: "is this file's modification justified by the PR body's scope?" If no, BLOCK with `Scope drift: <file> at <hunk> — not covered by PR scope`.

```bash
gh pr diff <PR> --name-only
gh pr view <PR> --json body --jq '.body' | sed -n '/## Scope/,/## /p'
```

Cross-reference each diff file against the parsed Scope section. Discretion applies for boilerplate (whitespace-only formatting, lint auto-fixes) — those typically pass.

## Exemptions

- **Trivial-lane PRs** (labeled `trivial` per [I3](../../../CLAUDE.md)): scope is implicit in the PR title; R-SCOPE applies but with looser interpretation since the change is by definition small.
- **Cascade-doc updates** named in the slice body (per [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D3): pre-approved scope expansion.

## Examples

- **Implementer adds a helper function in a docs-only slice**: BLOCK — even if the helper is small, it's a runtime artifact not named in the slice body.
- **PR titled "fix typo" also bumps a dependency version**: BLOCK — version bumps are out-of-scope for typo fixes.
- **Slice body says "ship the reviewer rule atomic notes"; PR also edits `.claude/agents/reviewer.md`**: BLOCK — the slice explicitly states "reviewer.md UNCHANGED in this slice"; the edit is out-of-scope drift.
- **Slice body lists exactly 3 files in "What ships"; PR diff touches 4**: BLOCK on the 4th file unless covered by a cascade-doc note in the slice body.

## Edges

- **part_of:** [[entities/subagents/reviewer]]
- **related_to:** [[concepts/rules/r-yagni]]
- **related_to:** [[concepts/rules/r-pr-body]]
- **part_of:** [[topics/reviewer-philosophy]]
