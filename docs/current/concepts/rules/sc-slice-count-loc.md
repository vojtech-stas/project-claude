---
title: SC-SLICE-COUNT-LOC — slicer-critic criterion 7, slice count and per-slice LoC fit the PRD §4 appetite
summary: The slicer-critic rule that the decomposition's slice count fits the PRD §4 appetite budget and every per-slice LoC estimate is ≤ the project cap; any violation FAILs the decomposition.
tags: [rule, slicer-critic-rubric]
type: concept
last_updated: 2026-05-26
sources:
  - .claude/agents/slicer-critic.md criterion 7
  - CLAUDE.md workflow improvement I4
---

# SC-SLICE-COUNT-LOC

**SC-SLICE-COUNT-LOC** is criterion 7 in the [`slicer-critic`](../../../.claude/agents/slicer-critic.md) rubric. It enforces a two-part budget check: (a) the total slice count fits within the PRD §4 appetite, and (b) every per-slice LoC estimate is ≤ the project cap (300 runtime-artifact LoC per [R-LOC](r-loc.md) and CLAUDE.md workflow improvement I4). Any violation is a hard **FAIL**.

## What

Mechanics:

- Read PRD §4 (Appetite) for the slice-count budget (e.g., "4-6 slices") and any LoC ceiling specifics.
- Count slices in the candidate decomposition; FAIL if outside the §4 range.
- For each slice, read the LoC estimate row; FAIL if any estimate exceeds 300 runtime-artifact LoC.
- Optional WARN if estimate ≥ 250 with no SPIDR fallback (overlaps with SC-SPIDR-SPLITABILITY criterion 3).

The "dual-cap math trap" pattern (captured as #268 from PRD #253 T2 retrospective): a slice can have a `wc -l` target (e.g., "thin slicer.md to ≤120 lines") AND a runtime-LoC cap (≤300 absolute under R-LOC). Slicer-critic must check BOTH are *jointly satisfiable* — the wc-LoC target's required deletions must fit inside the R-LOC absolute-LoC budget for the same slice. A slice that needs 270 deletions to hit the wc-target AND ships 200 new lines of replacement content totals 470 LoC and breaches R-LOC. Slicer-critic catches this at decomposition time, not at PR time.

## Why

This rule exists because **per-slice budgets are the autonomous pipeline's parallelism guarantee**. Per [ADR-0010](../../../decisions/0010-implementer-subagent-auto-pipeline.md), the `/ship` orchestrator dispatches slices in parallel; if a single slice exceeds the cap, the implementer subagent for that slice has to mid-PR pivot (and the parallel dispatch of other slices may continue assuming the over-cap slice was viable). The cost of a mid-PR pivot under the autonomous pipeline is much higher than under manual workflows — the parallel dispatch can amplify the bad slice's effects.

The slice-count constraint exists because **PRD appetite is a real budget**. A PRD that says "4-6 slices" expects roughly that much work; a 12-slice decomposition silently expands appetite without re-grilling. Same energy as the SC-NO-NON-GOALS criterion (4): catching scope expansion at the slicing layer.

The dual-cap check exists specifically because it has bitten this project (PRD #253 #268 retrospective). Pre-merge math discipline prevents the post-merge respin.

## How to check

For each candidate decomposition:

1. Count slices; verify in PRD §4 range.
2. For each slice, read LoC estimate; verify ≤ 300 runtime-artifact LoC.
3. For thinning slices, compute: (lines deleted from target file) + (lines added as replacement) — must be ≤ 300.
4. Cross-check estimate against the slice's actual workload (is it credible?).

## Examples

- **PRD §4 says "4-6 slices"; decomposition has 7 slices** → FAIL (over appetite).
- **Slice estimates: 80, 120, 290, 50** → PASS each individually (all ≤300).
- **Slice thins file from 420 → 150 lines (270 deletions) AND adds 200 lines of synthesis** → FAIL (270+200 = 470 absolute LoC; over R-LOC cap; needs split).

## Edges

- **part_of:** [[entities/subagents/slicer-critic]]
- **related_to:** [[concepts/rules/r-loc]]
- **related_to:** [[concepts/rules/sc-spidr-splitability]]
- **related_to:** [[concepts/rules/sc-invest]]
