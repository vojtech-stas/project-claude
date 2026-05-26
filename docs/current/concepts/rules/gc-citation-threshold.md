---
title: GC-CITATION-THRESHOLD — glossary-critic rule 5, term cited ≥3 times across ≥2 of {decisions/, .claude/agents/, .claude/skills/}
summary: The glossary-critic rule that a draft term must appear at least 3 total times across at least 2 of the three load-bearing source directories (`decisions/`, `.claude/agents/`, `.claude/skills/`); terms below the threshold FAIL the rule (per ADR-0012 D2, grandfathering existing entries per D7).
tags: [rule, glossary-critic-rubric]
type: concept
last_updated: 2026-05-26
sources:
  - .claude/agents/glossary-critic.md rule 5 (citation threshold)
  - decisions/0012-glossary-consolidation-single-tier.md D2
  - decisions/0012-glossary-consolidation-single-tier.md D7
  - decisions/0011-subagent-quality-framework.md D2
---

# GC-CITATION-THRESHOLD

**GC-CITATION-THRESHOLD** is rule 5 in the [`glossary-critic`](../../../.claude/agents/glossary-critic.md) rubric. It enforces that a draft term must appear at least **3 total times across at least 2** of the three load-bearing source directories: `decisions/`, `.claude/agents/`, `.claude/skills/`. Terms below the threshold FAIL the rule per [ADR-0012](../../../decisions/0012-glossary-consolidation-single-tier.md) D2.

Existing CLAUDE.md glossary entries are **grandfathered** against this tightened threshold per [ADR-0012](../../../decisions/0012-glossary-consolidation-single-tier.md) D7; the rule applies only to NEW entries added from ADR-0012's merge forward.

## What

The rule fires on every NEW draft entry's term. Mechanics:

- Run `grep -rc "<term>" decisions/ .claude/agents/ .claude/skills/`. The `-c` flag yields per-file counts.
- Case-insensitivity (`-i`) is permitted; whole-word matching (`-w`) is preferred where the term is short or could substring-collide (e.g., "PR" without `-w` would catch every "PRD").
- Sum per-file counts to get total citations.
- Count how many of the three top-level directories have ≥1 hit.
- If total citations <3 → FAIL with `"inclusion-threshold: '<X>' cited <N> times across <D> directories; ADR-0012 D2 requires ≥3 citations across ≥2 directories"`.
- If total ≥3 but only 1 directory has hits → FAIL with the same message format (e.g., a term mentioned 5 times in `decisions/` but never in `.claude/` is still pre-load-bearing).

## Why

This rule is the **frequency floor** that prevents the glossary from degrading into a wishlist of terms the author thinks SHOULD be load-bearing but aren't yet. It aligns with [ADR-0011](../../../decisions/0011-subagent-quality-framework.md) D2's mechanical-rubric philosophy — quality gates that LLMs cannot bluff past.

The 3-citations-across-2-directories shape captures the operational reality that load-bearing terms here cross between **decisions** (the ADR layer) and **agent/skill execution** (the runtime layer). A term used only in ADRs but never invoked in a subagent or skill is theoretical; a term used only in one subagent's prompt is local jargon, not project jargon.

The grandfathering of pre-ADR-0012 entries per D7 exists because the threshold was tightened mid-flight — retroactively culling existing entries would force a sweep that doesn't carry its weight. New entries from D7's merge forward carry the cost.

The asymmetric cost (cheap to enforce — one `grep` invocation; expensive to repair — a low-frequency entry confuses every future session-loader) puts the rule at the critic gate.

## How to check

For each NEW draft entry's term:

1. Run `grep -rc -i "<term>" decisions/ .claude/agents/ .claude/skills/` from the repo root.
2. Tally total citations across all files.
3. Tally distinct directories with ≥1 hit (out of 3).
4. Verify total ≥3 AND distinct-directories ≥2.
5. If either threshold misses → FAIL with the standard message.
6. For grandfathering: if the entry already exists in CLAUDE.md `## Glossary` as of ADR-0012's merge commit, skip the rule.

## Examples

- **Term "kb-maintainer" — citations: 2 in `decisions/`, 0 elsewhere = 2 total, 1 directory** → FAIL (under both thresholds).
- **Term "supersession" — citations: 4 in `decisions/`, 0 in `.claude/agents/`, 0 in `.claude/skills/` = 4 total, 1 directory** → FAIL (total OK but only 1 directory).
- **Term "joint-APPROVE gate" — citations: 1 in `decisions/`, 1 in `.claude/agents/`, 1 in `.claude/skills/` = 3 total, 3 directories** → PASS.
- **Term "slice" — citations: dozens across all three** → PASS (and grandfathered anyway).
- **Term "GENERATOR trailer" (NEW post-ADR-0012) — citations: 5 in `decisions/`, 2 in `.claude/agents/`, 1 in `.claude/skills/` = 8 total, 3 directories** → PASS.

## Edges

- **part_of:** [[entities/subagents/glossary-critic]]
- **related_to:** [[concepts/rules/gc-no-duplicate]]
- **related_to:** [[concepts/rules/gc-scope-tagged]]
