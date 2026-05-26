---
title: AS-CRIT-4 — audit-subagents critic check, 5-section verdict template present
summary: The audit-subagents critic-only mechanical check that every critic body documents the canonical 5-section verdict template (Header verdict line + Subject of review + Rubric + Findings + Summary) per ADR-0005 D1a; any missing section FAILS the check.
tags: [rule, audit-subagents-rubric]
type: concept
last_updated: 2026-05-27
sources:
  - .claude/skills/audit-subagents/SKILL.md CRIT-4
  - decisions/0011-subagent-quality-framework.md D4
  - decisions/0005-output-shape-and-slicing-methodology.md D1a
---

# AS-CRIT-4

**AS-CRIT-4** is the [`/audit-subagents`](../../entities/skills/audit-subagents.md) rubric check (scope: `critic`) that enforces every critic body documents the canonical **5-section verdict template** per [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D1a:

1. **Header** — `## <critic-name> verdict: [APPROVE | BLOCK] (round N/3)`
2. **Subject of review** — restated spec contract
3. **Rubric** — per-criterion PASS/FAIL
4. **Findings** — itemized list on BLOCK; `None.` on APPROVE
5. **Summary** — one-paragraph synthesis

A critic body missing documentation of any of the five sections FAILS the check.

## What

The check fires on every critic file. Mechanics:

- Run five greps and require ALL five to match:
  - `grep -cF "Subject of review" <file>` ≥ 1 AND
  - `grep -cE "^#+\s*Rubric" <file>` ≥ 1 AND
  - `grep -cE "^#+\s*Findings" <file>` ≥ 1 AND
  - `grep -cE "^#+\s*Summary" <file>` ≥ 1 AND
  - `grep -cE "verdict:" <file>` ≥ 1.
- If all five counts are ≥ 1 → **PASS**.
- If any one count is 0 → **FAIL** (template documentation incomplete).

The pattern uses anchored heading matches (`^#+`) for sections 3-5 (since those are naturally headings in the template) and fixed-string matches for sections 1 and 2 (since those are unique enough phrases). The mix is deliberate: the rubric author preferred the cheapest unambiguous match per section.

## Why

The 5-section verdict template is the **converged shape** across the 4 ≤3-round critics (`reviewer`, `prd-critic`, `adr-critic`, `slicer-critic`) per [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D1a. A critic that omits a section produces a verdict the user (and downstream consumers) cannot parse consistently — the Summary in particular is what humans read first, and Findings are what implementers need to act on.

Checking all five fields together (rather than spot-checking) catches partial migrations: critics that updated to include the trailer (AS-CRIT-3) but never updated their body template, OR critics copy-pasted from an older 3-section shape that pre-dates [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md).

## How to check

For each critic file:

1. Run all five greps listed above.
2. If all five counts are ≥ 1 → PASS.
3. If any count = 0 → FAIL; the report should flag the file and the missing section(s).
4. For generators → render `—`.

## Examples

- **`prd-critic.md` documenting all five sections in an "Output format" block** → PASS.
- **`reviewer.md` with all five section headings shown in an example verdict** → PASS.
- **A critic file documenting Header + Rubric + Findings + Summary but missing "Subject of review"** → FAIL.
- **A critic file with "verdict:" prose but no heading-shaped Rubric / Findings / Summary sections** → FAIL (anchored heading patterns don't match).

## Edges

- **part_of:** [[entities/skills/audit-subagents]]
- **related_to:** [[concepts/rules/as-crit-3]]
- **related_to:** [[concepts/glossary/critic-trailer]]
