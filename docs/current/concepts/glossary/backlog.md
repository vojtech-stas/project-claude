---
title: backlog — forward-looking work queue
summary: The forward-looking work queue of `backlog`-labeled GitHub Issues plus the Backlog column on project board #2, holding queued ideas not yet ready for full PRD grilling.
tags: [glossary, pipeline, common-word-narrowed, workflow]
type: concept
last_updated: 2026-05-26
sources:
  - decisions/0006-backlog-and-session-continuity.md
  - CLAUDE.md
---

# backlog

The **backlog** is this project's forward-looking work queue: GitHub Issues carrying the `backlog` label, surfaced visually as the "Backlog" column on project board #2. Items in the backlog are queued ideas that have passed the `backlog-critic`'s 4-criterion filter but are not yet promoted to a full `prd`-labeled issue and have not yet been grilled.

**Edges**

- **related-to:** [[concepts/glossary/prd]]
- **related-to:** [[concepts/glossary/session]]
- **part-of:** [[topics/captured-and-backlog-tiers]]

## What

The backlog is the **second** of two tiers in this project's captured→backlog→PRD promotion pipeline (per [ADR-0006](../../../decisions/0006-backlog-and-session-continuity.md) D1 + [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D3):

1. **Captured tier** — `captured`-labeled issues. The noisy raw layer; every agent fires `gh issue create --label captured` on deferred or follow-up items per CLAUDE.md rule #11.
2. **Backlog tier** — `backlog`-labeled issues. The curated forward queue. Promotion from captured to backlog runs through the [`/promote-to-backlog`](../../../.claude/skills/promote-to-backlog/SKILL.md) skill, which dispatches the [`backlog-critic`](../../../.claude/agents/backlog-critic.md) subagent (per [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D4's 4-criterion rubric: actionable / scoped / not duplicate / clear).
3. **PRD tier** — `prd`-labeled issues. Promoted from backlog when ready for full grilling via `/grill-me`.

Promotion `backlog` → `prd` swaps labels and rewrites the title into the canonical `PRD: <one-line feature summary>` form per [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D5. Backlog issue titles themselves are descriptive noun phrases — no codename prefixes, no topical classifiers — so the backlog functions as a neutral pool from which `/grill-me` picks based on current priorities.

## Why

The backlog exists because **work captured during one session is rarely ready to ship in the next**. The two-tier design separates noise filtering (captured → backlog, gated by `backlog-critic`) from prioritization (backlog → PRD, gated by human selection at `/grill-me` time). Without the backlog tier, every deferred idea would either (a) land directly as a full PRD draft — too heavyweight for the typical "this should probably happen someday" capture — or (b) live in a personal notes file invisible to other sessions and to other agents.

The default-conservative posture on the captured layer (per CLAUDE.md rule #11 — "when in doubt about whether an item is worth capturing, capture it") is paired with the backlog-critic's filter so the human-facing backlog stays curated even when the captured layer is noisy. The captured graveyard remains visible for rescue if mis-classified.

## Examples from this project

- `gh issue list --label backlog` — lists the current forward queue.
- `gh issue list --label captured` — lists the raw layer waiting for promotion or culling.
- **Backlog [#128](https://github.com/vojtech-stas/project-claude/issues/128)** — the docs-first KB pattern backlog item that became PRD #179 (`best-practice-workflow` skill) after promotion.

## Anti-patterns

- **Direct main-agent edit of a backlog-tier title** — violates CLAUDE.md rule #10 (main-agent meta-output discipline); promote through the captured→backlog→PRD pipeline.
- **Codename-prefixed backlog titles** (`PRD-A — foo`) — pre-bias candidate selection at `/grill-me` time and violate the neutral-pool design per [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D5.
- **Skipping the backlog tier for non-trivial work** — captures should normally graduate through the critic; the trivial-lane (I3) is for ≤10 LoC hotfixes only, not "this is small enough to skip ceremony" PRDs.

## Scope

(c) common word with narrowed meaning here

## Authority

[ADR-0006](../../../decisions/0006-backlog-and-session-continuity.md) D1

## References

- [ADR-0006](../../../decisions/0006-backlog-and-session-continuity.md) D1 — backlog tier definition and queue role.
- [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D3 — inline `/promote-to-backlog` firing convention.
- [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D4 — `backlog-critic`'s 4-criterion rubric.
- [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D5 — title-naming conventions across captured/backlog/PRD tiers.
- [`.claude/skills/promote-to-backlog/SKILL.md`](../../../.claude/skills/promote-to-backlog/SKILL.md) — the promotion skill.
- [`.claude/agents/backlog-critic.md`](../../../.claude/agents/backlog-critic.md) — the filter critic.
