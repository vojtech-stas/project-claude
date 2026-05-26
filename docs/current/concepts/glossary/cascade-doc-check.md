---
title: cascade-doc check — slicer obligation to identify ripple-effect doc updates
summary: The slicer's responsibility to identify docs (README, CLAUDE.md Map rows, ADR index rows) that should update to reflect a new feature even when not strictly required by acceptance criteria, and add or fold a slice to cover them.
tags: [glossary, slicing, project-jargon, slicer]
type: concept
last_updated: 2026-05-26
sources:
  - decisions/0005-output-shape-and-slicing-methodology.md
  - CLAUDE.md
---

# cascade-doc check

The **cascade-doc check** is the slicer's responsibility to identify docs that *should* update to reflect a new feature — even when those updates are not strictly required by the slice's acceptance criteria — and to add a dedicated slice (or fold the work into an existing slice) to cover them. Per [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D3, this is a first-class slicing obligation, not a post-hoc cleanup activity.

**Edges**

- **related-to:** [[concepts/glossary/slice]]
- **related-to:** [[concepts/glossary/hamburger-method]]
- **part-of:** [[topics/slicing]]

## What

When a PRD introduces a new subagent, skill, ADR, hook, or convention, several files that aren't directly named in the feature's acceptance criteria still need to update so future readers find the new thing:

- **`README.md`** — top-level orientation.
- **`CLAUDE.md` Map rows** — the "Looking for… / Find it at" table that lets agents discover capabilities by intent.
- **`decisions/README.md` ADR index** — the chronological list of decisions.
- **Pipeline-stage rows in CLAUDE.md** — "How to X — ✓ available / ⏳ future" lines.
- **Sibling skill/subagent bodies that reference the new thing** — cross-references that go stale if the new thing arrives but its callers don't learn about it.
- **The Glossary** — when the new feature coins jargon that meets the inclusion threshold per [ADR-0012](../../../decisions/0012-glossary-consolidation-single-tier.md) D2.

The [`slicer`](../../../.claude/agents/slicer.md) is required to enumerate cascade-docs per candidate decomposition; the [`slicer-critic`](../../../.claude/agents/slicer-critic.md) rubric has a matching "Cascade-docs identified and covered" criterion that BLOCKs decompositions that ship the new feature without wiring its discoverability paths.

## Why

The cascade-doc check exists because **a feature that ships without its discoverability paths effectively does not exist** for the next reader. Future Claude Code sessions and human contributors find capabilities via CLAUDE.md's Map and Pipeline-stage sections; an unwired feature is invisible there. The cost of forgetting cascade-docs compounds: each later PRD that needs the feature has to rediscover it from git log or grep, and each forgotten Map row makes the codebase harder to navigate for the agents that are supposed to operate it autonomously.

Putting the responsibility on the *slicer* rather than the implementer is deliberate. Slicer sees the whole PRD shape and knows which existing files reference adjacent surfaces; implementer sees only one slice and is biased to YAGNI those edits out. Catching cascade-docs at slicing time gates them into scope before YAGNI can reject them; catching them later means an extra hotfix PR per missed doc.

## Examples from this project

- **PRD #3 (autonomous pipeline)** — every new subagent slice also updated CLAUDE.md's Map + Pipeline-stage sections; the slicer enumerated these as cascade-docs and slicer-critic enforced.
- **PRD #128 (best-practices KB)** — each new `best-practice-<topic>` skill slice cascaded into a CLAUDE.md Pipeline-stage row + a `docs/best-practices/` README mention.
- **PRD #245 / this very migration** — slice 1 cascaded the new `## Glossary` INDEX header paragraph into CLAUDE.md, slice 2 cascaded 9 more INDEX rows, slice 3 cascades the final 8 rows + the cleanup that brings the INDEX shape to its end state.

## Anti-patterns

- **"Cascade docs are out of scope; that's a follow-up PR"** — fragments discoverability and creates a follow-up backlog that decays.
- **Implementer-time cascade discovery** — implementer notices a missing Map row mid-slice and either silently adds it (scope drift; YAGNI violation) or skips it (creates the fragmentation above). Slicer should have surfaced it.
- **Cascade-doc check applied only to docs/, ignoring CLAUDE.md** — CLAUDE.md is the primary discovery surface for agents; the check is incomplete without it.

## Scope

(a) project jargon coined here

## Authority

[ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D3

## References

- [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D3 — cascade-doc check as a first-class slicer obligation.
- [CLAUDE.md](../../../CLAUDE.md) "Slicing logic — what makes a good slice" — methodology overview citing the cascade-doc check.
- [`.claude/agents/slicer.md`](../../../.claude/agents/slicer.md) — operational application; enumeration step in candidate decomposition.
- [`.claude/agents/slicer-critic.md`](../../../.claude/agents/slicer-critic.md) — rubric criterion that BLOCKs decompositions missing cascade-docs.
- [[concepts/glossary/slice]] — the unit whose discoverability the check protects.
