---
title: glossary-fold — bulk-fold of skill-local vocabulary into the canonical glossary
summary: User-invokable bulk-fold per ADR-0014 D2; scans .claude/skills/*/SKILL.md for ## Local vocabulary sections, runs each entry through glossary-critic, and proposes APPROVE'd entries to CLAUDE.md via a single PR.
tags: [skill, glossary, generator, bulk, glossary-fold]
type: entity
last_updated: 2026-05-27
sources:
  - .claude/skills/glossary-fold/SKILL.md
  - decisions/0014-skill-local-vocabulary-and-auto-fold.md
  - decisions/0012-glossary-consolidation-single-tier.md
---

# /glossary-fold

The `/glossary-fold` skill is the **bulk-fold mechanism** for skill-local `## Local vocabulary` sections per [ADR-0014](../../../decisions/0014-skill-local-vocabulary-and-auto-fold.md) D2. User-invokable; on every invocation it scans the entire `.claude/skills/` tree, runs each candidate entry through [`glossary-critic`](../subagents/glossary-critic.md), and proposes APPROVE'd entries to `CLAUDE.md` via PR. Sibling skill to [`/glossary-add`](glossary-add.md) (single-entry interactive flow).

## Role and responsibility

`/glossary-fold` has four jobs:

1. **Glob** `.claude/skills/*/SKILL.md` for files containing a `## Local vocabulary` H2 section. If none found → report `nothing to fold` and exit with `RESULT: SUCCESS` + `ENTRIES_PARSED: 0` (no PR).
2. **Parse entries** from each `## Local vocabulary` section per the canonical CLAUDE.md glossary shape ([ADR-0007](../../../decisions/0007-vocabulary-glossary-and-grill-me-extension.md) D2). Skip malformed entries with a `MALFORMED` note in the report; do not BLOCK on shape — `glossary-critic` catches downstream.
3. **Run per-entry mechanical pre-critic checks:**
   - **Duplicate vs CLAUDE.md:** if `grep -c "^- \*\*<term>\*\*" CLAUDE.md` ≥ 1 → **SKIPPED**.
   - **Citation threshold** per [ADR-0012](../../../decisions/0012-glossary-consolidation-single-tier.md) D2: count `<term>` occurrences across `decisions/`, `.claude/agents/`, `.claude/skills/`. If total < 3 OR present in < 2 of 3 directories → **DEFERRED**.
4. **Invoke `glossary-critic`** per surviving entry; accumulate **APPROVE**'d entries. Open one PR adding all APPROVE'd entries to CLAUDE.md `## Glossary` section in alphabetical position (branch `hotfix/glossary-fold-<YYYYMMDD>`); PR body Verification = full report. If 0 APPROVE'd → emit report, no PR.

## Invocation contract

- **Caller:** the user via `/glossary-fold` (no-args, sibling convention with `/glossary-add` / `/audit-subagents` / `/promote-to-backlog`).
- **Input:** none.
- **Output:** a per-skill / per-entry status report (Markdown table) PLUS the canonical [GENERATOR trailer](../../concepts/glossary/generator-trailer.md) with `ENTRIES_PARSED`, `ENTRIES_APPROVED`, `ENTRIES_SKIPPED`, `ENTRIES_DEFERRED` per-agent extensions.
- **Tool boundaries:** `Read`, `Glob`, `Grep`, `Bash` (`git`, `gh pr create`), `Agent` (glossary-critic dispatch). Frontmatter `tools:` field explicitly declared.

## Non-goals (preserved by design per PRD #121 §3)

- **No auto-trigger** — no reviewer rule, no merge hook, no scheduled job. User-invoked only per [ADR-0014](../../../decisions/0014-skill-local-vocabulary-and-auto-fold.md) D5.
- **No retroactive `## Local vocabulary` addition** to existing skills. Opt-in convention per [ADR-0014](../../../decisions/0014-skill-local-vocabulary-and-auto-fold.md) D1.
- **No `glossary-fold-critic` subagent** — honors the 6-critic-cap meta-rule per [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7 + [ADR-0014](../../../decisions/0014-skill-local-vocabulary-and-auto-fold.md) D4.
- **No subagent-local vocabulary support** — scoped to `.claude/skills/*/SKILL.md` only; `.claude/agents/*.md` deferred.

## Relationship to other skills and agents

- **Sibling to** [`/glossary-add`](glossary-add.md) per [ADR-0014](../../../decisions/0014-skill-local-vocabulary-and-auto-fold.md) D2 — single-entry interactive vs bulk-fold.
- **Invokes** [`glossary-critic`](../subagents/glossary-critic.md) per surviving entry.
- **Inspects** every `## Local vocabulary` section across `.claude/skills/*/SKILL.md`.
- **Honors the 6-critic-cap** per [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7 — `/glossary-fold` is a skill; its gate is `glossary-critic`.
- **Authority:** [ADR-0014](../../../decisions/0014-skill-local-vocabulary-and-auto-fold.md) — D1 (section convention), D2 (this skill), D3 (conflict resolution), D4 (no new critic), D5 (no auto-trigger), D6 (bootstrap-mode); [ADR-0012](../../../decisions/0012-glossary-consolidation-single-tier.md) D1 + D2 + D5 (single-tier, citation threshold, soft cap).

## Edges

- **part_of:** [[topics/knowledge-architecture]]
- **related_to:** [[entities/skills/glossary-add]]
- **related_to:** [[entities/subagents/glossary-critic]]
- **related_to:** [[concepts/glossary/trivial-lane]]
- **related_to:** [[concepts/glossary/generator-trailer]]
