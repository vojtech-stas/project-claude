---
title: R-PR-BODY — reviewer hard-block on PR body missing required sections
summary: The reviewer rule that BLOCKs any PR whose body lacks the required Scope / Out-of-scope / Verification sections per CLAUDE.md "Finishing a slice" template.
tags: [rule, reviewer-rubric, hard-block]
type: concept
last_updated: 2026-05-26
sources:
  - .claude/agents/reviewer.md rule 7
  - CLAUDE.md
---

# R-PR-BODY

**R-PR-BODY** is rule 7 in the [`reviewer`](../../../.claude/agents/reviewer.md) rubric. It hard-blocks any PR whose body lacks the required template sections: **Scope**, **Out-of-scope**, **Verification**. The rule mechanically enforces CLAUDE.md "Operational git workflow → Finishing a slice" at PR review time, ensuring every merged PR carries the structured metadata needed for downstream consumers (reviewer rubric application, [R-CLOSES](r-closes.md) audit-trail link, post-merge `git log` summary).

## What

The rule fires immediately on PR open. Mechanics:

- Reviewer reads `gh pr view <PR> --json body`.
- Greps for headings matching `## Scope`, `## Out-of-scope` (or `## Out of scope`), `## Verification`.
- If any heading is missing → BLOCK with `PR body missing required sections (scope / out-of-scope / verification)`.

The check is mechanical (grep-based on heading text); the reviewer does NOT judge the content quality of each section — that's [R-SCOPE](r-scope.md)'s and [R-YAGNI](r-yagni.md)'s job. R-PR-BODY ensures the sections exist; the other rules judge what's inside them.

Optional sections that DON'T trigger R-PR-BODY:

- `## ADR reference` (only required if the slice ships a new ADR).
- `## Dogfood`, `## Notes`, `## References` — common but not mandatory.

## Why

R-PR-BODY exists because **structured PR bodies are load-bearing input to every downstream rule and process**. Without it:

- [R-SCOPE](r-scope.md) cannot judge drift (no scope section to compare against).
- [R-CLOSES](r-closes.md) cannot find the slice link (no canonical body location to grep).
- Future readers cannot reconstruct the slice intent.
- The post-merge changelog (`git log` per CLAUDE.md cross-cutting rule #6) loses the per-slice context.

Making it a hard-block at PR open time (rather than a soft recommendation) ensures the implementer fills the template before the reviewer wastes a full rubric pass on a body-less PR.

## How to check

```bash
gh pr view <PR> --json body --jq '.body' > /tmp/pr-body.md
grep -E '^## Scope' /tmp/pr-body.md
grep -E '^## Out[- ]of[- ]scope' /tmp/pr-body.md
grep -E '^## Verification' /tmp/pr-body.md
```

All three greps must hit. Missing any → BLOCK with the exact missing-section name.

## Exemptions

- **PRD-tier PRs** (labeled `prd`): the body IS the PRD content (6-section template per [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D1), not the standard slice template. R-PR-BODY does not fire.
- **Trivial-lane PRs** (labeled `trivial`): a single-line scope statement in the body is acceptable; the template requirement is relaxed since the change is by definition small.

## Examples

- **PR body says only "fixes bug"**: BLOCK — missing all three required sections.
- **PR body has Scope + Verification but no Out-of-scope**: BLOCK — Out-of-scope is the drift-defense lever; its absence is load-bearing.
- **PR body has all three sections + ADR reference + Dogfood**: PASS.

## Edges

- **part_of:** [[entities/subagents/reviewer]]
- **related_to:** [[concepts/rules/r-scope]]
- **related_to:** [[concepts/rules/r-closes]]
- **part_of:** [[topics/reviewer-philosophy]]
