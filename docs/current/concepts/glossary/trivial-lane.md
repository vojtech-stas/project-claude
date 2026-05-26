---
title: trivial lane — fast-path workflow for tiny no-behavior-change PRs
summary: The fast-path workflow (I3) for PRs at most 10 LoC of runtime-artifact diff with no behavior change — branch `hotfix/<short-summary>`, label `trivial`, no PRD/slice ceremony.
tags: [glossary, pipeline, project-jargon, workflow]
type: concept
last_updated: 2026-05-26
sources:
  - decisions/0003-autonomous-pipeline-with-critics.md
  - CLAUDE.md
---

# trivial lane

The **trivial lane** (also called the "I3 lane" after its CLAUDE.md ID) is this project's fast-path PR workflow for tiny no-behavior-change changes. PRs that satisfy all three trivial-lane criteria skip PRD/slice ceremony, branch under `hotfix/<issue-number>-<summary>`, carry the `trivial` label, and get fast-pathed by the reviewer.

**Edges**

- **related-to:** [[concepts/glossary/slice]]
- **related-to:** [[concepts/glossary/conventional-commits]]
- **part-of:** [[topics/pipeline-stages]]

## What

The three criteria for trivial-lane eligibility (per CLAUDE.md I3):

1. **≤10 LoC of runtime-artifact diff** — the canonical "runtime artifact" definition lives in [`reviewer.md`](../../../.claude/agents/reviewer.md) R-LOC; same scope, much tighter cap.
2. **No behavior change** — pure typo fixes, documentation polishing, formatting touch-ups. If the change alters how an agent behaves, what a critic blocks on, or what an orchestrator dispatches, it's NOT trivial-lane eligible.
3. **`trivial` label applied to the PR** — load-bearing for reviewer dispatch.

Trivial-lane mechanics:

- **Branch**: `hotfix/<issue-number>-<kebab-summary>`. The pre-commit regex enforces the issue number — use the closing audit-trail issue number even for "obvious" typo fixes, so the trail isn't broken.
- **No PRD or slice required** — but DO create a "captured" or audit-trail issue if one doesn't already exist, so the PR has a `Closes #<n>` target. R-CLOSES still applies; the exemption is from the slice-label requirement, not from R-CLOSES entirely.
- **Reviewer**: fast-paths trivial-lane PRs — quicker turnaround, fewer rubric checks against scope (because there isn't a slice body to litigate against), still enforces Conventional Commits + Co-Authored-By + tests-touched-if-behavior-touched.

## Why

The trivial lane exists because **PRD-slice ceremony has fixed cost regardless of change size**. A 1-character typo fix that goes through grill → ship → slicer → critic → implementer → reviewer wastes orders of magnitude more compute and human attention than the change merits. The trivial lane scales the ceremony down to match the change size.

The strict no-behavior-change criterion is the load-bearing safeguard. Behavior changes — even small ones — can have non-local effects that the PRD/slice ceremony exists to surface. Permitting "small behavior changes" through the trivial lane would erode the autonomous pipeline's value over time as agents (and humans) rationalize larger and larger behavior changes through the fast path.

The `trivial` label gives the reviewer a mechanical dispatch signal — no inference required.

## Examples from this project

- A typo fix in [`CLAUDE.md`](../../../CLAUDE.md): branch `hotfix/123-fix-typo-in-claude-md`, label `trivial`, ~3 LoC diff, no behavior change.
- A broken link fix in an existing [`.claude/agents/<critic>.md`](../../../.claude/agents/): if the link target moved, fixing the URL is trivial-lane eligible.
- **NOT trivial-lane**: a 5-LoC change that adjusts a critic's rubric threshold — behavior change, requires slice ceremony so reviewer can litigate scope.
- **NOT trivial-lane**: a 20-LoC formatting cleanup — over the 10-LoC cap; needs a slice even though no behavior change.

## Anti-patterns

- **Trivial-lane abuse for "obviously fine" behavior changes** — erodes the boundary; reviewer should BLOCK and require slice promotion.
- **Skipping the issue-number requirement** — breaks the pre-commit regex AND the audit trail; even hotfixes need a closing issue number.
- **Multiple unrelated typo fixes bundled into one trivial-lane PR** — exceeds the 10-LoC cap easily and bundles drift; one trivial PR per coherent change.
- **Missing the `trivial` label** — reviewer treats it as a normal slice PR; R-CLOSES looks for a `slice` issue and BLOCKs.

## Scope

(a) project jargon coined here

## Authority

[ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D1

## References

- [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D1 — trivial-lane introduction.
- [CLAUDE.md](../../../CLAUDE.md) I3 — operational definition and mechanics.
- [`.claude/agents/reviewer.md`](../../../.claude/agents/reviewer.md) R-LOC — runtime-artifact LoC scope (used for both the 300-LoC slice cap AND the 10-LoC trivial cap).
- [`.claude/agents/reviewer.md`](../../../.claude/agents/reviewer.md) rule 10 — R-CLOSES with `trivial`-label exemption from the slice-label requirement.
- [[concepts/glossary/slice]] — the non-trivial counterpart.
