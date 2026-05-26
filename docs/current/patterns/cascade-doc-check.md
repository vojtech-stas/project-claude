---
title: Cascade-doc check — slicer's identification of ripple-effect doc updates
summary: The slicer's slicing-time pattern of enumerating docs (README, CLAUDE.md Map rows, ADR index rows, downstream skill/subagent bodies) that should update to reflect a new feature even when not strictly required by acceptance criteria, and covering each via a slice.
tags: [pattern, slicing, slicer, cascade-doc]
type: pattern
last_updated: 2026-05-26
sources:
  - decisions/0005-output-shape-and-slicing-methodology.md D3
  - CLAUDE.md "Slicing logic — what makes a good slice"
  - .claude/agents/slicer.md
  - .claude/agents/slicer-critic.md criterion 9
---

# Cascade-doc check

The dogfood slicing-time pattern for discoverability. When a PRD introduces a new subagent, skill, ADR, hook, or convention, several files that aren't directly named in the feature's acceptance criteria still need to update so future readers find the new thing. The cascade-doc check is the slicer's responsibility to enumerate those docs at slicing time and cover them via a slice (new or merged into an existing slice).

Per [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D3, this is a **first-class slicing obligation**, not a post-hoc cleanup activity. [`slicer-critic`](../../../.claude/agents/slicer-critic.md) criterion 9 ([SC-CASCADE-DOCS-COVERED](../concepts/rules/sc-cascade-docs-covered.md)) gates it; criterion 10 ([SC-CROSS-PR-COLLISION](../concepts/rules/sc-cross-pr-collision.md)) adds the cross-PR awareness layer.

## What

A cascade-doc is a file that should update when a feature ships, even when the slice's acceptance criteria do not literally require it. The project's canonical cascade-doc surfaces:

- **`README.md`** — top-level orientation.
- **`CLAUDE.md` Map rows** — the "Looking for… / Find it at" table that lets agents discover capabilities by intent.
- **`decisions/README.md`** — the chronological ADR index.
- **CLAUDE.md Pipeline-stage rows** — "How to X — ✓ available / ⏳ future" lines.
- **Sibling skill/subagent bodies referencing the changed area** — cross-references that go stale if the new thing arrives but its callers don't learn about it.
- **The Glossary** — when the new feature coins jargon meeting the inclusion threshold per [ADR-0012](../../../decisions/0012-glossary-consolidation-single-tier.md) D2.

The slicer enumerates these per candidate decomposition; the slicer-critic verifies each enumeration is reasonable and complete.

## Why

The cascade-doc check exists because **a feature that ships without its discoverability paths effectively does not exist** for the next reader. Future Claude Code sessions and human contributors find capabilities via CLAUDE.md's Map and Pipeline-stage sections; an unwired feature is invisible there. The cost compounds: each later PRD that needs the feature has to rediscover it from git log or grep, and each forgotten Map row makes the codebase harder for the agents that operate it autonomously.

Putting the responsibility on the **slicer** rather than the implementer is deliberate. Slicer sees the whole PRD shape and knows which existing files reference adjacent surfaces; implementer sees only one slice and is biased to YAGNI cascade-doc edits out. Catching cascade-docs at slicing time gates them into scope before YAGNI can reject them; catching them later means an extra hotfix PR per missed doc.

## How to check

When decomposing a PRD into slices:

1. Identify what the PRD introduces (new subagent? new skill? new ADR? new convention?).
2. For each, walk the discoverability surfaces above and ask: *does this file need an update to point at the new thing?*
3. Add a row to the decomposition table's "Cascade-docs identified" column listing each file.
4. Assign the update to a slice (new dedicated slice OR fold into an in-scope slice).
5. If no cascade-docs apply, **explicitly state** "no cascade-docs identified" with a one-line justification (e.g., "feature is internal-only — no user-facing surface changes").

The explicit-no-cascade exemption matters: requiring acknowledgment forces consideration rather than silent skipping.

## Anti-patterns

- **"Cascade docs are out of scope; that's a follow-up PR"** — fragments discoverability and creates a follow-up backlog that decays.
- **Implementer-time cascade discovery** — implementer notices a missing Map row mid-slice and either silently adds it (scope drift; YAGNI violation) or skips it (creates the fragmentation above). Slicer should have surfaced it.
- **Cascade-doc check applied only to `docs/`, ignoring CLAUDE.md** — CLAUDE.md is the primary discovery surface for agents; the check is incomplete without it.

## Examples from this project

- **PRD #3 (autonomous pipeline)** — every new subagent slice also updated CLAUDE.md's Map + Pipeline-stage sections; the slicer enumerated these as cascade-docs and slicer-critic enforced.
- **PRD #128 (best-practices KB)** — each new `best-practice-<topic>` skill slice cascaded into a CLAUDE.md Pipeline-stage row + a `docs/best-practices/` README mention.
- **PRD #210** — criterion 10 (cross-PR collision) was added to slicer-critic as the root-cause workflow improvement after the PR #183 + PR #186 cascade-doc rebase incident.

## Edges

- **defines:** [[concepts/glossary/cascade-doc-check]]
- **related_to:** [[concepts/rules/sc-cascade-docs-covered]]
- **related_to:** [[concepts/rules/sc-cross-pr-collision]]
- **related_to:** [[patterns/walking-skeleton]]
- **part_of:** [[entities/subagents/slicer]]
