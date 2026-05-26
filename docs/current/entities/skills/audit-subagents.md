---
title: audit-subagents — mechanical drift-detector for subagent prompts
summary: Periodic /audit-subagents skill that globs .claude/agents/*.md, classifies each as critic or generator, applies the 10-check scope-tagged grep rubric (ALL-1..5 + CRIT-1..4 + GEN-1 per ADR-0011 D4), and emits a single advisory Markdown PASS/FAIL report — no auto-capture, no PR, no critic gate.
tags: [skill, audit, generator, mechanical, audit-subagents]
type: entity
last_updated: 2026-05-27
sources:
  - .claude/skills/audit-subagents/SKILL.md
  - decisions/0011-subagent-quality-framework.md
  - decisions/0008-workflow-autolog-bootstrap-and-naming.md
  - decisions/0005-output-shape-and-slicing-methodology.md
---

# /audit-subagents

The `/audit-subagents` skill is the **mechanical drift-detector for subagent prompts** under `.claude/agents/`. Per [ADR-0011](../../../decisions/0011-subagent-quality-framework.md), it codifies the conventions established across [ADR-0001](../../../decisions/0001-foundational-design.md) D6, [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D1, [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D8, and [ADR-0009](../../../decisions/0009-discipline-tightening.md) D3/D4 as literal `grep` patterns producing deterministic PASS/FAIL per (subagent, applicable check) pair.

## Role and responsibility

`/audit-subagents` has two jobs:

1. **Classify each subagent** per [ADR-0011](../../../decisions/0011-subagent-quality-framework.md) D3 (locked classifier): filename ends `-critic.md` OR is exactly `reviewer.md` → critic; else generator. Skip checks whose `scope:` tag does not match the file's classification.
2. **Apply the 10-check rubric** per [ADR-0011](../../../decisions/0011-subagent-quality-framework.md) D4: 5 `scope: all` checks (ALL-1..5), 4 `scope: critic` checks (CRIT-1..4), 1 `scope: generator` check (GEN-1). At the current 6-critic + 2-generator baseline, this yields baseline 66 evaluations (effective 64 after CRIT-2 + ALL-4 exclusions of `backlog-critic.md` per the `excludes:` schema). Emit a single Markdown PASS/FAIL report to stdout, followed by the canonical [GENERATOR trailer](../../concepts/glossary/generator-trailer.md).

The skill is **advisory output only** per [ADR-0011](../../../decisions/0011-subagent-quality-framework.md) D5 — no auto-capture, no PR opened, no critic gate. The user reads the report and captures real drift findings per CLAUDE.md rule #11 manually.

## Ownership choice rationale

Per [ADR-0011](../../../decisions/0011-subagent-quality-framework.md) D1: a **skill, not a 7th critic**, because the [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7 6-critic-cap meta-rule blocks a `subagent-critic`; a **skill, not a reviewer rule**, because PR-time gating misses drift in unchanged files (the exact failure mode of the 2026-05-19 stale-worktree audit that motivated this).

## Invocation contract

- **Caller:** the user via `/audit-subagents` (no-args). No positional arguments per [ADR-0011](../../../decisions/0011-subagent-quality-framework.md) D7.
- **Input:** none. The skill globs `.claude/agents/*.md` automatically.
- **Output:** a single Markdown report to stdout — one H2 per subagent, one row per applicable check, plus a Summary section enumerating every FAIL by `(file, check ID)`. Trailer carries `SUBAGENTS_AUDITED`, `CHECK_EVALUATIONS`, `FAIL_COUNT` per-agent extensions.
- **Tool boundaries:** `Read`, `Glob`, `Grep`, `Bash` (for executing grep patterns). Forbidden: `Edit`, `Write` (advisory only), `Agent` (no recursive invocation; this is not a critic), `gh issue create` / `gh pr create` (no auto-capture per [ADR-0011](../../../decisions/0011-subagent-quality-framework.md) D5).

## Default-conservative rendering

When a grep pattern is ambiguous against file content (e.g., the literal string appears inside a quoted example or commented-out block), the skill renders **FAIL**. Asymmetric-cost rationale (same as [ADR-0009](../../../decisions/0009-discipline-tightening.md) D3 generalized to advisory audits): a spurious FAIL costs one user-glance round; a wrong-PASS lets a real drift slip past undetected.

## Per-check `excludes:` allowlist

The rubric schema includes an optional `excludes:` field per check whose value is a comma-separated list of subagent filenames legitimately exempt from the otherwise-correct mechanical check. Current exclusions: `ALL-4` and `CRIT-2` both exclude `backlog-critic.md`. Excluded `(subagent, check)` pairs render as `N/A (excluded per rubric)` in the report and are omitted from the FAIL enumeration. Each exclusion carries an inline rationale citing the authoritative ADR so future readers see WHY the exception exists.

## Non-recursive scope

Per [ADR-0011](../../../decisions/0011-subagent-quality-framework.md) D8, the skill does NOT audit itself — `.claude/skills/audit-subagents/SKILL.md` is excluded from the Glob target. The skill is a subagent-shaped artifact but is NOT itself a subagent under `.claude/agents/`. Auditing `.claude/skills/*` is out of scope (separate cadence backlog item).

## Relationship to other skills and agents

- **Sibling to** [`/audit-meta`](audit-meta.md) per [ADR-0017](../../../decisions/0017-audit-meta-consolidation.md) D6 (not an extension — two siblings, separate domains: subagent prompts vs codebase structure + docs currency).
- **Inspects** every file under `.claude/agents/*.md` — the 6 critics + 2 generators currently.
- **Honors the 6-critic-cap** per [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7 — `/audit-subagents` is a skill, not a critic.
- **Authority:** [ADR-0011](../../../decisions/0011-subagent-quality-framework.md) — D1 (skill ownership), D2 (mechanical-only rubric), D3 (classifier rule), D4 (the 10 checks), D5 (single Markdown report, no auto-capture), D6 (rubric embedded in SKILL.md), D7 (no-args invocation), D8 (bootstrap-mode + non-recursive), D9 (sibling backlog relationships).

## Edges

- **part_of:** [[topics/knowledge-architecture]]
- **related_to:** [[entities/skills/audit-meta]]
- **related_to:** [[entities/subagents/reviewer]]
- **related_to:** [[entities/subagents/implementer]]
- **related_to:** [[concepts/glossary/critic]]
- **related_to:** [[concepts/glossary/generator-trailer]]
- **related_to:** [[topics/output-shapes]]
