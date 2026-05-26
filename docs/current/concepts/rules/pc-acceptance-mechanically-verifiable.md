---
title: PC-ACCEPTANCE-MECHANICALLY-VERIFIABLE — prd-critic criterion 6, every Goal bullet is bash-checkable at merge
summary: The prd-critic rule that every Goal / success criterion bullet in §2 is mechanically verifiable — observable at merge or after a single bash command — without requiring subjective human judgment; "users are happy" or "code is clean" FAIL.
tags: [rule, prd-critic-rubric]
type: concept
last_updated: 2026-05-26
sources:
  - .claude/agents/prd-critic.md criterion 2 (goal verifiability)
  - .claude/skills/qa-plan/SKILL.md acceptance-criterion extraction
  - decisions/0020-qa-automation-writer-executor.md D2
---

# PC-ACCEPTANCE-MECHANICALLY-VERIFIABLE

**PC-ACCEPTANCE-MECHANICALLY-VERIFIABLE** is the prd-critic rubric criterion that enforces every Goal / success criterion bullet in §2 is mechanically verifiable — observable at merge or extractable into a bash check or `JUDGMENT` flag by [`qa-plan`](../../../.claude/skills/qa-plan/SKILL.md). Bullets that require subjective human judgment ("users are happy", "code is clean", "experience is delightful") FAIL the rule.

This rule is the upstream contract for `/qa-plan`: every §2 bullet must be extractable per [ADR-0020](../../../decisions/0020-qa-automation-writer-executor.md) D2 into either a `bash` check OR a `JUDGMENT` flag (where the human is asked via `AskUserQuestion`). A bullet that satisfies neither shape is `EXTRACT_FAILED` at QA time — too late to fix cheaply.

## What

The rule fires on every Goal bullet in §2. Mechanics:

- Read each bullet; classify it:
  - **Mechanical bash check** — shape: "X file exists" / "wc -l Y ≤ N" / "grep Z returns ≥1 match" / "command returns exit code 0". PASS.
  - **JUDGMENT-extractable** — shape: "feature behaves as described in §5 sketch step 3" / "subagent body reads cleanly to a human auditor" / any subjective-but-judgable claim that a human can answer ACCEPT / REJECT to via `AskUserQuestion`. PASS.
  - **Neither** — shape: "users are happy" / "code is clean" / "experience is delightful" / vague qualitative. FAIL.
- The bar is **extractability**, not pre-extraction: the bullet doesn't need to ship as bash, but it must be extractable into bash OR a JUDGMENT prompt by the qa-plan writer.

## Why

This rule exists because **`/qa-plan` is the terminal human checkpoint** in the autonomous pipeline (per [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D4 + [ADR-0020](../../../decisions/0020-qa-automation-writer-executor.md) D10). If §2 bullets aren't extractable, qa-plan emits `EXTRACT_FAILED` rows that block the PRD's close — the entire pipeline up to that point shipped fine, only to fail at the final gate.

The asymmetric cost is brutal: PRD revision is cheap, slice respin is expensive, PR revert is very expensive, and `EXTRACT_FAILED` is the worst because the PRD's slices have already merged and `/qa-plan` cannot recover them without human triage. Catching at PRD time eliminates the whole class of failure.

The "extractable into JUDGMENT" carve-out matters because some subjective acceptance is honest — e.g., "the entity note reads as a coherent role synthesis" is genuinely human-judgable but useful. The rule asks for extractability, not exclusion of all subjective bullets.

## How to check

For each draft PRD's §2 Goal bullets:

1. Read each bullet; classify per the three shapes above.
2. If shape is mechanical: try to mentally compile to bash. If you can write the check in one line, PASS.
3. If shape is JUDGMENT-extractable: try to mentally compile to an `AskUserQuestion` prompt. If you can write a clear ACCEPT/REJECT question, PASS.
4. If neither shape applies → FAIL with the offending bullet quoted.

## Examples

- **"wc -l .claude/agents/prd-critic.md ≤ 120"** → PASS (direct bash check).
- **"All 6 docs/current/concepts/rules/pc-*.md files exist with frontmatter"** → PASS (mechanical: `ls` + `head` grep).
- **"No behavioral change: rubric criteria preserved verbatim in semantics"** → PASS as JUDGMENT (human reads the thin file + entity note + rule notes and judges semantic preservation).
- **"PRD #283 ships well"** → FAIL (neither mechanical nor JUDGMENT-extractable).
- **"Users find the new docs intuitive"** → FAIL (no users to ask; not mechanical).

## Edges

- **part_of:** [[entities/subagents/prd-critic]]
- **related_to:** [[concepts/rules/pc-prd-completeness]]
- **related_to:** [[concepts/rules/sc-invest]]
