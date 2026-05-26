---
title: PC-APPETITE-BOUNDED — prd-critic criterion 3, appetite is concrete and coheres with solution-sketch scope
summary: The prd-critic rule that the Appetite section names a concrete slice budget, time, LoC cap, or no-new-deps stance AND that the figure is coherent with the Solution sketch's scope; mismatched appetite (5 slices appetite vs 10-slice sketch) FAILs the rule.
tags: [rule, prd-critic-rubric]
type: concept
last_updated: 2026-05-26
sources:
  - .claude/agents/prd-critic.md criterion 4 (appetite-vs-scope coherence)
  - decisions/0003-autonomous-pipeline-with-critics.md D1
---

# PC-APPETITE-BOUNDED

**PC-APPETITE-BOUNDED** is the prd-critic rubric criterion that enforces the Appetite section names a concrete budget (slice count, time, LoC cap, or no-new-deps stance) AND that the budget coheres with the Solution sketch's implied scope. Vague appetite ("a few slices") or mismatched appetite (sketch implies 10 slices, appetite says 5–7) FAILs the rule.

## What

The rule fires on every draft PRD's Appetite + Solution sketch sections together. Mechanics:

- **Concreteness:** Appetite must name at least one of:
  - Slice budget (e.g., "8–12 slices").
  - Time budget (e.g., "2 work sessions").
  - LoC cap reaffirmation (e.g., "honors R-LOC 300; qa-tester needs cluster split").
  - Dependency stance (e.g., "no new external dependencies").
- **Coherence:** The named budget matches the Solution sketch's enumerated work:
  - If sketch enumerates ~10 work-units (subagents, slices) and appetite says "5 slices" → FAIL (cannot fit).
  - If sketch says "no new deps" and any sketch bullet adds a `yt-dlp`-like external → FAIL.
  - If sketch implies a single trivial-lane change and appetite says "8-12 slices" → FAIL (too coarse).

## Why

This rule exists because **appetite-vs-scope mismatch is the second-largest source of slice-cap explosions** (after missing non-goals). A PRD with "5 slices" appetite that implies 12 work-units forces the slicer to either (a) cluster brutally (each slice maxes R-LOC and risks SC-INVEST-S violations) or (b) ignore the appetite and emit 12 slices, leaving the PRD's budget claim broken from day 1.

The coherence check is the upstream cousin of [SC-SLICE-COUNT-LOC](sc-slice-count-loc.md). Slicer-critic checks that the decomposition fits the appetite — but only if the appetite is honest about what the sketch entails. PC-APPETITE-BOUNDED catches the honesty failure at PRD time.

The "no new deps" sub-check is the most adversarial: most PRDs that violate it do so silently, with the new dep buried in the sketch's prose. The grep for `yt-dlp` / `jq` / `npx` / `pip install` / `brew install` flags the case.

## How to check

For each draft PRD:

1. Read Appetite section — verify it names at least one concrete budget shape (above).
2. Read Solution sketch — count work-units (subagents enumerated, slice-bullets, deliverables).
3. Compare appetite to work-unit count: is the appetite within ±20% of the implied count?
4. Grep sketch for dependency-adding shapes (`yt-dlp` / `jq` / `pip install` / `npm install` / `brew install` / `apt-get`). If any match AND appetite says "no new deps" → FAIL.
5. If appetite is vague ("a few slices") → FAIL.

## Examples

- **Appetite "8-12 slices" + sketch enumerates 7 subagent thinnings + 1 cluster split** → PASS (math works: 7-9 slices fit the appetite).
- **Appetite "no new deps" + sketch bullet says "shells out to `yt-dlp` to fetch transcripts"** → FAIL.
- **Appetite "a few slices"** → FAIL (vague; not budget-bounded).
- **Appetite "5 slices" + sketch enumerates 13 deliverables** → FAIL (cannot fit; will force SC-INVEST-S violations).

## Edges

- **part_of:** [[entities/subagents/prd-critic]]
- **related_to:** [[concepts/rules/pc-solution-sketch-actionable]]
- **related_to:** [[concepts/rules/sc-slice-count-loc]]
- **related_to:** [[concepts/rules/r-loc]]
