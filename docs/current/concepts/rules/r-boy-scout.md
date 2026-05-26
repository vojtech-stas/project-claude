---
title: R-BOY-SCOUT — discretionary reviewer rule for per-PR drift detection on audit-relevant files
summary: The discretionary 13th reviewer rule that applies /audit-subagents and /audit-meta rubric checks INLINE to audit-relevant files touched in a PR; default-conservative-toward-REC severity.
tags: [rule, reviewer-rubric, discretionary]
type: concept
last_updated: 2026-05-26
sources:
  - .claude/agents/reviewer.md
  - decisions/0018-boy-scout-reviewer-rule.md
---

# R-BOY-SCOUT

**R-BOY-SCOUT** is the discretionary 13th rule in the [`reviewer`](../../../.claude/agents/reviewer.md) rubric, added per [ADR-0018](../../../decisions/0018-boy-scout-reviewer-rule.md). Additive to the 12 hard-block rules (no renumbering — R-BOY-SCOUT has its own severity discipline per ADR-0018 D4). It applies `/audit-subagents` and `/audit-meta` rubric checks INLINE when a PR touches audit-relevant files. Honors the 6-critic-cap (rule extension on the existing `reviewer` critic, NOT a new critic).

## What

The rule fires when the PR's diff touches files matching any of these trigger patterns. Each trigger maps to a specific subset of audit checks the reviewer applies inline:

| Trigger pattern | Audit checks to apply |
|---|---|
| `.claude/agents/*.md` | `/audit-subagents` rubric (all 10 checks per [ADR-0011](../../../decisions/0011-subagent-quality-framework.md) D4) on touched files only |
| `.claude/skills/*/SKILL.md` | `/audit-meta --structure` rubric STRUCT-1, STRUCT-2, STRUCT-7 + frontmatter shape |
| `decisions/*.md` | `/audit-meta --docs` rubric DOCS-1, DOCS-2, DOCS-7, DOCS-8 (cross-reference checks) |
| `CLAUDE.md` | `/audit-meta --docs` rubric DOCS-3, DOCS-4, DOCS-5, DOCS-9, DOCS-10 |
| `README.md` | `/audit-meta --docs` rubric DOCS-5, DOCS-6, DOCS-10 |

Multiple matching paths in one PR → run all applicable rubrics; consolidate findings in the verdict's Findings section.

**Inline-execution constraint** (per ADR-0018 D3): apply rubric criteria INLINE using own Bash + Grep tool access. Do NOT shell out to `/audit-subagents` or `/audit-meta` — they are session-interactive skills the reviewer cannot invoke. The rubrics are mechanical (grep-based per [ADR-0011](../../../decisions/0011-subagent-quality-framework.md) D2) and self-contained.

## Why

R-BOY-SCOUT exists because **audit-quality drift accumulates silently between scheduled audit runs**. Without it, a subagent body slowly degrades across many PRs (stale ADR references, missing rules from the 10-check rubric), and the drift only surfaces when someone runs `/audit-subagents` manually. R-BOY-SCOUT catches drift at the PR-tier mechanical layer — the same moment the reviewer is already inspecting the file. It's additive defense-in-depth, not a replacement for the scheduled audits.

The discretionary severity reflects the precision-vs-recall trade-off: applying audit rules at every PR catches more drift but also risks false-positive BLOCKs that frustrate implementers on borderline cases. The dual-severity mechanic (BLOCK only when ALL three criteria hold; Recommendation otherwise) calibrates: hard-block only on high-confidence + mechanical-fix + materially-impactful findings; surface everything else as non-blocking Recommendation.

## How to check

For each PR file matching a trigger pattern, apply the associated rubric inline:

```bash
gh pr view <PR> --json files --jq '.files[] | .path'
```

For each `.claude/agents/<name>.md` touched, run the 10 checks from `/audit-subagents` per ADR-0011 D4. For each `.claude/skills/<name>/SKILL.md` touched, run STRUCT-1/2/7. For each `decisions/<NNNN>-*.md` touched, run DOCS-1/2/7/8. Etc.

## Severity discretion

Emit each finding at one of two severities per ADR-0018 D4:

- **BLOCK** when ALL of:
  - The audit rule has zero documented false-positive cases against current `main` (currently *excludes* DOCS-5, DOCS-6, DOCS-7 from BLOCK eligibility per backlog [#142](https://github.com/vojtech-stas/project-claude/issues/142) calibration carve-out — those rules emit as Recommendation only until #142 ships).
  - The fix is mechanical and small (one-line, hotfix-shape).
  - The drift would materially impact future readers (stale ADR D-ID reference, known-bad pattern like `N=3` in narrative docs post-[ADR-0013](../../../decisions/0013-slicer-n3-contract-refined.md)).
- **Recommendation** otherwise — surface in verdict but do NOT block merge; user/implementer fixes via trivial-lane post-merge.

**Default-conservative-toward-REC** (per ADR-0018 D4, inverting [ADR-0009](../../../decisions/0009-discipline-tightening.md) D3's hard-block default): when uncertain whether a finding meets all three BLOCK criteria, emit as Recommendation. R-BOY-SCOUT is additive defense-in-depth; cost of a false-positive BLOCK exceeds cost of a false-negative REC.

## Verdict integration

R-BOY-SCOUT findings appear as a 13th rule line in the Rubric:

- `[PASS] 13. R-BOY-SCOUT: no audit-relevant files touched` (when no triggers fire).
- `[FAIL] 13. R-BOY-SCOUT: <N> BLOCK-grade findings (<M> Recommendations)` (when at least one BLOCK-grade finding).

BLOCK-grade findings appear in Findings numbered with rule prefix `R-BOY-SCOUT`; Recommendation-grade findings appear in the existing Recommendations section.

## Examples

- **PR touches `.claude/agents/implementer.md` adding a new section**: R-BOY-SCOUT runs all 10 `/audit-subagents` checks against the file. If a stale ADR reference is detected (e.g., `ADR-0099 D1` when ADR-0099 doesn't exist), emit BLOCK.
- **PR touches `CLAUDE.md` to add a new Map row**: R-BOY-SCOUT runs DOCS-3/4/5/9/10. If a Map row points to a non-existent file, emit BLOCK.
- **PR touches `decisions/0032-new-decision.md` (new ADR)**: R-BOY-SCOUT runs DOCS-1/2/7/8. Discretion applies for cross-reference completeness.

## Edges

- **part_of:** [[entities/subagents/reviewer]]
- **related_to:** [[concepts/rules/r-scope]]
- **part_of:** [[topics/reviewer-philosophy]]
