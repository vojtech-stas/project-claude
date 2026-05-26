---
title: BC-NOT-DUPLICATE — backlog-critic criterion 3, no semantic duplicate in open backlog or captured
summary: The backlog-critic rule that a captured item must not semantically duplicate any open `backlog`- or `captured`-labeled issue; literal-string match is not required (judge what the existing issue is about), and the duplicate-check queries used must be recorded in the verdict audit trail.
tags: [rule, backlog-critic-rubric]
type: concept
last_updated: 2026-05-26
sources:
  - .claude/agents/backlog-critic.md criterion 3 (not duplicate)
  - decisions/0008-workflow-autolog-bootstrap-and-naming.md D4
---

# BC-NOT-DUPLICATE

**BC-NOT-DUPLICATE** is the backlog-critic rubric criterion that enforces a `captured`-labeled item must not have a **semantic duplicate** already open in either the `backlog` or `captured` tier. Literal-string match is not required — the critic judges by what the existing issue is *about*, not by exact wording. The duplicate-check queries used must be recorded in the verdict's "Subject of review" so the audit trail captures the search performed.

## What

The rule fires on every fresh `captured`-labeled issue. Mechanics:

- Run both required queries (below) and read titles of all open items in both tiers.
- For any plausibly-adjacent title, read the body of the existing issue and compare it semantically to the new capture.
- A **duplicate** is two items that would, if both promoted, produce overlapping PRDs and overlapping slices — i.e., the same work.
- A **near-miss** is an item that is related-but-distinct in scope (e.g., one targets `backlog-critic`, the other targets `prd-critic`, with shared theme). Near-miss does NOT count as duplicate, but the critic explicitly notes the relationship in the rubric line.
- Default-conservative per [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D2: when uncertain whether two items are semantically the same, BLOCK and name the candidate duplicate so the user can decide.

## Why

This rule exists because **duplicate captures pollute the backlog's signal**: when `/grill-me` picks from a backlog containing the same idea twice, the user either grills one and culls the other (waste), or grills both and produces overlapping PRDs (wasted slices, eventual merge conflicts). The cost of letting one duplicate slip through the autopilot is paid by every future `/grill-me` invocation until manual cleanup.

The "literal-string match not required" carve-out matters because captures are often phrased in different vocabularies (one capture from a prd-critic context will say "rubric", another from a slicer-critic context will say "criteria"). A naive grep for substring matches misses true semantic duplicates while flagging false positives.

The audit-trail requirement (record queries in Subject of review) is the gating discipline: without it, an APPROVE on a duplicate cannot be retroactively diagnosed.

## How to check

For each captured-tier item:

1. Run BOTH required queries:
   ```bash
   gh issue list --label backlog --state open --limit 100 --json number,title,body
   gh issue list --label captured --state open --limit 100 --json number,title,body
   ```
2. State the exact queries used in the verdict's Subject of review.
3. Read all titles. For any plausibly-adjacent title, read the body and compare semantically.
4. If a semantic duplicate exists → FAIL with `"duplicate: issue #<N> ('<title>') already covers this in the <tier> tier; close this capture or comment on the existing issue instead"`.
5. If a near-miss exists (related but distinct scope) → note the relationship in the rubric line, do NOT FAIL.
6. If no duplicate → PASS.

## Examples

- **New capture "Add table of contents to CLAUDE.md"** + open backlog #142 "Add TOC to CLAUDE.md for navigation" → FAIL (clear semantic duplicate; same work).
- **New capture "Thin `backlog-critic.md` per ADR-0031 D12"** + open backlog #287 "slice 4/10: 4× bc-* rule notes for backlog-critic rubric" → FAIL (overlapping subagent; both want to refactor `backlog-critic.md`).
- **New capture "Add `/audit-prompts` skill"** + open backlog #128 "best-practice-workflow skill" → PASS as near-miss (both audit-shaped but distinct skill scopes); note the relationship.
- **New capture "Extract reviewer rule R-CLOSES to atomic note"** + no open issue mentioning R-CLOSES → PASS.

## Edges

- **part_of:** [[entities/subagents/backlog-critic]]
- **related_to:** [[concepts/rules/bc-actionable]]
- **related_to:** [[concepts/glossary/backlog]]
- **related_to:** [[concepts/glossary/captured]]
