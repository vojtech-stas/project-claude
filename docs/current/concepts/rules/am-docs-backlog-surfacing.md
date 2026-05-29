---
title: AM-DOCS-BACKLOG-SURFACING — audit-meta docs check, no backlog-label surfacing instructions in subagent or skill files (DOCS-10)
summary: The audit-meta docs-subcommand mechanical check (PR #105 + PR #107 drift detector) that no subagent or skill body contains `backlog`-labeled prose or `--label backlog` literal; backlog-critic.md and promote-to-backlog/SKILL.md allowlisted as legitimate carriers.
tags: [rule, audit-meta-rubric, docs]
type: concept
last_updated: 2026-05-29
sources:
  - .claude/skills/audit-meta/SKILL.md DOCS-10
  - decisions/0017-audit-meta-consolidation.md D3
  - decisions/0008-workflow-autolog-bootstrap-and-naming.md D8
  - decisions/0009-discipline-tightening.md D2
---

# AM-DOCS-BACKLOG-SURFACING

**AM-DOCS-BACKLOG-SURFACING** is the [`/audit-meta`](../../entities/skills/audit-meta.md) `--docs` subcommand check (DOCS-10) that detects the **#105 / #107 surfacing-convention drift across both subagent AND skill files**: any body containing ``\`backlog\`-labeled`` prose or `--label backlog` literal FAILs the check. Per [ADR-0017](../../../decisions/0017-audit-meta-consolidation.md) D3, mirroring the [AS-ALL-4](as-all-4.md) precedent that detects the same drift in subagent files only.

The `backlog-critic.md` allowlist is honored per the [ADR-0011](../../../decisions/0011-subagent-quality-framework.md) ALL-4 precedent. The `promote-to-backlog/SKILL.md` allowlist is honored because that skill's job is the captured→backlog label-swap operation per [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D3 — it legitimately instructs `--label backlog` as its operational mechanic.

## What

The check fires under the `docs` subcommand. Mechanics:

- Run: `grep -rE '(`backlog`-labeled|--label backlog)' .claude/agents .claude/skills`.
- If the result is empty → **PASS** (no drift idiom present).
- If non-empty → **FAIL** (list offending files with matching lines), excluding:
  - `backlog-critic.md` (allowlisted per [ADR-0011](../../../decisions/0011-subagent-quality-framework.md) ALL-4 precedent)
  - `promote-to-backlog/SKILL.md` (allowlisted — that skill IS the captured→backlog autopilot per [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D3; its `--label backlog` usage is the intended operation, not drift)

The scope is **both `.claude/agents/` and `.claude/skills/`** — a strict superset of AS-ALL-4's subagents-only scope. This is the key contribution of DOCS-10: catching drift in skill bodies (where AS-ALL-4 doesn't look) that would otherwise sneak through.

## Why

The captured-vs-backlog two-tier surfacing convention from [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D8 + [ADR-0009](../../../decisions/0009-discipline-tightening.md) D2 applies to **every agent and skill that instructs deferred-work capture**, not just subagents. Skills like `/promote-to-backlog` orchestrate the captured → backlog flow, and other skills (`/ship`, `/grill-me`) instruct agents to surface follow-ups during their runs. If any of those skill bodies say "capture as `backlog`-labeled", they tell agents to skip the [`backlog-critic`](../../entities/subagents/backlog-critic.md) gate — the exact #105/#107 regression.

The `/promote-to-backlog` skill is the single exception: it IS the gate (captured→backlog label-swap operation per ADR-0008 D3), so its body legitimately contains `--label backlog` as part of its operational mechanic. This is the defining distinction between allowlisted hits (the label-swap operator itself) and FAIL hits (any other skill telling agents to apply `backlog` label directly to new captures).

AS-ALL-4 already catches the subagent half. DOCS-10 extends the same drift detector to the skill half, completing the coverage. The two checks together (AS-ALL-4 + AM-DOCS-BACKLOG-SURFACING) form the project's full mechanical defense against surfacing-convention regression.

## How to check

When `--docs` is active:

1. Run `grep -rE '(`backlog`-labeled|--label backlog)' .claude/agents .claude/skills`.
2. If empty → PASS.
3. If non-empty → FAIL with file:line list, **excluding** hits in `backlog-critic.md` (ADR-0011 ALL-4 precedent) and `promote-to-backlog/SKILL.md` (ADR-0008 D3 label-swap operator).

## Examples

- **No subagent or skill file uses the backlog-label surfacing idiom** → DOCS-10 PASS.
- **`/ship` skill body says "open follow-ups as `backlog`-labeled issues"** → DOCS-10 FAIL.
- **`/promote-to-backlog` skill body uses `--label backlog` as part of its label-swap operation** → DOCS-10 PASS (allowlisted — that skill's job IS swapping labels per ADR-0008 D3).
- **`backlog-critic.md` mentions `` `backlog`-labeled `` in its domain prose** → DOCS-10 PASS (allowlisted per ADR-0011 ALL-4 precedent).

## Edges

- **part_of:** [[entities/skills/audit-meta]]
- **related_to:** [[concepts/rules/as-all-4]]
- **related_to:** [[entities/subagents/backlog-critic]]
