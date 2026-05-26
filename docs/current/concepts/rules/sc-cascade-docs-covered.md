---
title: SC-CASCADE-DOCS-COVERED — slicer-critic criterion 9, every cascade-doc identified and covered
summary: The slicer-critic rule that each decomposition explicitly identifies cascade-docs (README, CLAUDE.md Map rows, ADR index rows, downstream skill/subagent bodies) that should update for the new feature and covers each via a slice; missing a load-bearing cascade-doc is FAIL, a minor one WARN.
tags: [rule, slicer-critic-rubric]
type: concept
last_updated: 2026-05-26
sources:
  - .claude/agents/slicer-critic.md criterion 9
  - decisions/0005-output-shape-and-slicing-methodology.md D3
---

# SC-CASCADE-DOCS-COVERED

**SC-CASCADE-DOCS-COVERED** is criterion 9 in the [`slicer-critic`](../../../.claude/agents/slicer-critic.md) rubric. It enforces the cascade-doc check at slicing time: each decomposition must explicitly identify cascade-docs (docs that should update to reflect the new feature even when not strictly required by acceptance criteria) and cover each via a slice (new or merged into an existing slice). Missing a load-bearing cascade-doc is **FAIL**; missing a minor cascade-doc is **WARN**; identifying-and-covering all cascade-docs (or explicitly stating none apply) is **PASS**.

## What

Mechanics:

- Read each slice's row in the slicer's decomposition table — there should be a "Cascade-docs identified" column listing the docs the slice updates.
- Cross-reference against the project's discoverability surfaces:
  - **`README.md`** — top-level orientation.
  - **`CLAUDE.md` Map rows** — the "Looking for… / Find it at" table.
  - **`decisions/README.md`** — ADR index rows.
  - **CLAUDE.md Pipeline-stage rows** — "How to X — ✓ available / ⏳ future" lines.
  - **Sibling skill/subagent bodies referencing the changed area** — stale cross-refs.
  - **The Glossary** (CLAUDE.md `## Glossary` section, when new jargon meets the inclusion threshold).
- FAIL severity if a load-bearing cascade-doc (README, CLAUDE.md, `decisions/README.md`) is missed.
- WARN severity if a minor cascade-doc is missed (downstream skill body, peripheral reference).
- PASS if cascade-docs are identified-and-covered, OR if the decomposition explicitly states "no cascade-docs identified" with a one-line justification.

Per [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D3, this is a formal slicer responsibility — not a post-hoc cleanup activity.

## Why

This rule exists because **a feature that ships without its discoverability paths effectively does not exist** for the next reader. Future Claude Code sessions and human contributors find capabilities via CLAUDE.md's Map and Pipeline-stage sections; an unwired feature is invisible there. Putting the responsibility on the *slicer* (and verified by slicer-critic) rather than the implementer is deliberate: slicer sees the whole PRD shape and knows adjacent surfaces; implementer sees only one slice and is biased to YAGNI cascade-doc edits out.

The two-tier FAIL/WARN severity is calibrated: missing CLAUDE.md is silent breakage of agent discoverability; missing a peripheral cross-ref is recoverable. The dichotomy lets the critic block the truly damaging misses while flagging the recoverable ones for explicit acknowledgment.

The "PASS if explicitly no cascade-docs" exemption matters because some PRDs genuinely have no cascade impact (purely internal refactors). Requiring explicit acknowledgment forces the slicer to actually consider the question rather than silently skip it.

## How to check

For each candidate decomposition:

1. Look for a "Cascade-docs identified" column or row in the slicer's table.
2. If absent → FAIL (criterion not addressed at all).
3. If present, cross-check against the discoverability surfaces above.
4. For each missed surface: classify as load-bearing (FAIL) or minor (WARN).
5. If decomposition states "no cascade-docs" with justification → PASS.

## Examples

- **Slice ships a new subagent; decomposition lists `CLAUDE.md` Map row + Pipeline-stage row + `decisions/README.md` ADR index row as cascade-docs each covered by slice 2** → PASS.
- **Slice ships a new ADR but no decomposition row mentions `decisions/README.md`** → FAIL (load-bearing cascade-doc missed).
- **Decomposition states "purely internal doc migration; no user-facing surface changes; no cascade-docs"** → PASS (explicit acknowledgment).

## Edges

- **part_of:** [[entities/subagents/slicer-critic]]
- **defines:** [[concepts/glossary/cascade-doc-check]]
- **related_to:** [[patterns/cascade-doc-check]]
- **related_to:** [[concepts/rules/sc-cross-pr-collision]]
