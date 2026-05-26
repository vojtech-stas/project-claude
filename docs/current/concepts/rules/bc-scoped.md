---
title: BC-SCOPED — backlog-critic criterion 2, item is PRD-sized or coherent sub-feature
summary: The backlog-critic rule that a captured item must be PRD-size or a coherent sub-feature — large enough to deserve a future grill, small enough to plausibly fit one PRD; trivial-lane-sized items and multi-PRD-sized items both FAIL.
tags: [rule, backlog-critic-rubric]
type: concept
last_updated: 2026-05-26
sources:
  - .claude/agents/backlog-critic.md criterion 2 (scoped)
  - decisions/0008-workflow-autolog-bootstrap-and-naming.md D4
  - CLAUDE.md I3 (trivial lane)
---

# BC-SCOPED

**BC-SCOPED** is the backlog-critic rubric criterion that enforces a `captured`-labeled item is **PRD-sized or a coherent sub-feature** — large enough that promoting it to the curated backlog deserves a future `/grill-me` session, small enough that one PRD's appetite can plausibly cover it. The rule has two failure modes: items too small belong in the I3 trivial lane, and items too large cannot be sketched without multiple PRDs.

## What

The rule fires on every fresh `captured`-labeled issue. Mechanics:

- **Too small:** a one-line edit (typo fix, single-word doc rename, single-character label tweak) belongs in the I3 trivial-lane workflow (`hotfix/<short>` branch, `trivial` label, no PRD/slice ceremony per CLAUDE.md I3). Promoting it to the backlog adds friction without value → FAIL.
- **Too large:** an item that would require multiple PRDs to even sketch ("redesign the entire pipeline"; "rebuild the agent system"; "rewrite all critics") cannot be acted on as one PRD → FAIL.
- **Borderline (PASS):** items that add or refactor a single subagent, single skill, single ADR, or single CLAUDE.md section. These are valid PRD-shaped slices.

## Why

This rule exists because **the backlog is the input queue for `/grill-me`**, and `/grill-me` is calibrated for one PRD-sized feature per session. Trivial-lane-sized items pollute the queue with work that should bypass ceremony entirely; multi-PRD items poison the queue by being un-grillable — every selection wastes the user's time confirming "this is too big, we need to split it first".

The asymmetric-default of CLAUDE.md rule #11 ("when in doubt, capture") means the captured layer collects many size mismatches; this rule is the second filter (after BC-ACTIONABLE) that prevents them from reaching the curated forward queue.

## How to check

For each captured-tier item:

1. Read the body. Estimate the implied work size:
   - One-line edit, single-typo fix, single-word rename, ≤10 LoC of net change → **trivial-lane size**, FAIL.
   - Single subagent / single skill / single ADR / single CLAUDE.md section change → **PRD size**, PASS.
   - Multi-subagent rewrite, pipeline redesign, "the agent system" reorganization → **multi-PRD size**, FAIL.
2. If trivial-lane → FAIL with `"scoped: item is trivial-lane-sized; close this issue and submit a hotfix PR instead"`.
3. If multi-PRD → FAIL with `"scoped: item requires multiple PRDs to sketch; split into separately-capturable concerns before promoting"`.
4. Otherwise → PASS.

## Examples

- **"Fix typo `recieve` → `receive` in CLAUDE.md"** → FAIL (trivial-lane; one-character hotfix).
- **"Add a new skill `/promote-to-backlog` that wraps the backlog-critic invocation"** → PASS (single skill, PRD-sized).
- **"Redesign the entire pipeline to use a state machine instead of skills/subagents"** → FAIL (multi-PRD; would need decomposition before any single PRD).
- **"Thin `.claude/agents/backlog-critic.md` per ADR-0031 D12 pattern"** → PASS (single subagent + named pattern, PRD-sized).
- **"Improve docs"** → BC-ACTIONABLE FAIL first; if rewritten as "Add table of contents to CLAUDE.md", PASS scoped (single section).

## Edges

- **part_of:** [[entities/subagents/backlog-critic]]
- **related_to:** [[concepts/rules/bc-actionable]]
- **related_to:** [[concepts/glossary/trivial-lane]]
- **related_to:** [[concepts/glossary/prd]]
