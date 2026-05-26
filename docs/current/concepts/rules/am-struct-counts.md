---
title: AM-STRUCT-COUNTS — audit-meta structure check, directory cardinality caps (agents ≤12, skills ≤16, ADRs ≤20)
summary: The audit-meta structure-subcommand mechanical check covering STRUCT-1/2/5 — directory cardinality caps for .claude/agents/, .claude/skills/, and decisions/, surfacing consolidation candidates when counts approach the cap.
tags: [rule, audit-meta-rubric, structure]
type: concept
last_updated: 2026-05-27
sources:
  - .claude/skills/audit-meta/SKILL.md STRUCT-1
  - .claude/skills/audit-meta/SKILL.md STRUCT-2
  - .claude/skills/audit-meta/SKILL.md STRUCT-5
  - decisions/0017-audit-meta-consolidation.md D2
  - decisions/0008-workflow-autolog-bootstrap-and-naming.md D7
---

# AM-STRUCT-COUNTS

**AM-STRUCT-COUNTS** is the [`/audit-meta`](../../entities/skills/audit-meta.md) `--structure` subcommand check family covering three directory-cardinality caps per [ADR-0017](../../../decisions/0017-audit-meta-consolidation.md) D2:

- **STRUCT-1** — `.claude/agents/` file count ≤ 12 (the [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7 6-critic-cap headroom).
- **STRUCT-2** — `.claude/skills/` direct-child directory count ≤ 16 (cap bumped from 12 to accommodate [ADR-0022](../../../decisions/0022-docs-first-kb-pattern.md) D3+D8 best-practice sibling skills B/C/E/F; see backlog #184).
- **STRUCT-5** — `decisions/` ADR count ≤ 20 (informational; flags consolidation candidate when high).

Each emits PASS / WARN / FAIL based on three-band thresholds.

## What

The checks fire under the `structure` subcommand (`/audit-meta --structure` or `/audit-meta` with no args). Mechanics:

- **STRUCT-1:** `ls .claude/agents/*.md | wc -l` → ≤ 12 PASS; 13..15 WARN; >15 FAIL.
- **STRUCT-2:** `ls -d .claude/skills/*/ | wc -l` → ≤ 16 PASS; 17..19 WARN; >19 FAIL.
- **STRUCT-5:** `ls decisions/[0-9]*.md | wc -l` → ≤ 20 PASS; 21..25 WARN; >25 FAIL.

The three-band shape (PASS / WARN / FAIL) reflects that hitting the cap is rarely a hard error — it's a signal to consider consolidation before the next addition pushes the cap.

## Why

Directory cardinality caps exist because the project's mental model has finite-headroom assumptions baked in:

- The 6-critic-cap from [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7 implies ~12 subagents at full saturation (6 critics + ~6 generators); past that, the cognitive cost of maintaining a unified mental model of the agent fleet rises sharply.
- The 16-skill cap accommodates the planned sibling-skill expansion ([ADR-0022](../../../decisions/0022-docs-first-kb-pattern.md)) but no further; new skills past 16 should justify why an existing skill cannot absorb the concern.
- The 20-ADR cap is informational — past 20, the README index becomes painful to scan, and consolidation candidates (deprecated + superseded chains) should be reviewed.

The WARN band gives one round of soft warning before FAIL; users can absorb a temporary excess during a multi-PRD wave without the audit screaming.

## How to check

When `--structure` is active:

1. Run `ls .claude/agents/*.md | wc -l`; apply STRUCT-1 thresholds.
2. Run `ls -d .claude/skills/*/ | wc -l`; apply STRUCT-2 thresholds.
3. Run `ls decisions/[0-9]*.md | wc -l`; apply STRUCT-5 thresholds.
4. Each emits its own row in the Structure findings table.

## Examples

- **`.claude/agents/` contains 8 files** → STRUCT-1 PASS (8 ≤ 12).
- **`.claude/agents/` contains 13 files** → STRUCT-1 WARN (in 13..15 band).
- **`.claude/skills/` contains 14 subdirectories** → STRUCT-2 PASS.
- **`decisions/` contains 22 NNNN-*.md files** → STRUCT-5 WARN.
- **`decisions/` contains 27 ADRs** → STRUCT-5 FAIL; consolidation strongly advised.

## Edges

- **part_of:** [[entities/skills/audit-meta]]
- **related_to:** [[concepts/rules/am-struct-sizes]]
- **related_to:** [[concepts/rules/am-struct-naming]]
