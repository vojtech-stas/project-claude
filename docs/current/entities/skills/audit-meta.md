---
title: audit-meta — mechanical drift-detector for codebase structure + docs currency
summary: /audit-meta skill with subcommand architecture (--structure / --docs / both); applies 10 STRUCT-* + 10 DOCS-* checks per ADR-0017 D2/D3 against repo structure (file counts, sizes, naming) and documentation references (dangling links, stale convention text); emits a single advisory Markdown PASS/WARN/FAIL report.
tags: [skill, audit, generator, mechanical, audit-meta]
type: entity
last_updated: 2026-05-27
sources:
  - .claude/skills/audit-meta/SKILL.md
  - decisions/0017-audit-meta-consolidation.md
  - decisions/0011-subagent-quality-framework.md
  - decisions/0005-output-shape-and-slicing-methodology.md
---

# /audit-meta

The `/audit-meta` skill is the **mechanical drift-detector for codebase structure + documentation currency** under the repo root. Per [ADR-0017](../../../decisions/0017-audit-meta-consolidation.md), it consolidates the structure-audit (backlog #129) and the docs-currency-audit (backlog #130) under a single skill with subcommand architecture — sibling to [`/audit-subagents`](audit-subagents.md) per [ADR-0017](../../../decisions/0017-audit-meta-consolidation.md) D6 (NOT an extension).

## Role and responsibility

`/audit-meta` has two jobs (parameterized by subcommand):

1. **Structure audit** (`--structure` or no-args). 10 STRUCT-* checks per [ADR-0017](../../../decisions/0017-audit-meta-consolidation.md) D2 covering file counts, file sizes (split-candidate detector at >500 LoC), directory depth, naming-convention compliance under `.claude/agents/`, `.claude/skills/`, `decisions/`, plus README + CLAUDE.md existence.
2. **Docs-currency audit** (`--docs` or no-args). 10 DOCS-* checks per [ADR-0017](../../../decisions/0017-audit-meta-consolidation.md) D3 covering: ADR-index ↔ disk parity (both directions), CLAUDE.md Map references to agents/skills resolve, no `N=3` literal in README (post-[ADR-0013](../../../decisions/0013-slicer-n3-contract-refined.md) drift), no `GLOSSARY.md` references anywhere (post-[ADR-0012](../../../decisions/0012-glossary-consolidation-single-tier.md) deletion), every ADR citation resolves, supersession notes in `decisions/README.md` Status column, glossary soft-cap (~35 entries per [ADR-0012](../../../decisions/0012-glossary-consolidation-single-tier.md) D5), no `backlog`-label surfacing instructions remaining in subagent/skill files.

Like `/audit-subagents`, the skill is **advisory output only** per [ADR-0011](../../../decisions/0011-subagent-quality-framework.md) D5 (precedent) + [ADR-0017](../../../decisions/0017-audit-meta-consolidation.md) D4 — no auto-capture, no PR, no critic gate.

## Invocation contract

- **Caller:** the user via one of three invocations only (per [ADR-0017](../../../decisions/0017-audit-meta-consolidation.md) D1):
  - `/audit-meta` (no args) — runs ALL subcommands; combined report
  - `/audit-meta --structure` — structure-audit only
  - `/audit-meta --docs` — docs-currency-audit only
  Any other arguments → `RESULT: INVALID_INPUT`.
- **Input:** the subcommand flag(s) above.
- **Output:** a single Markdown report to stdout with one subsection per active subcommand, each row PASS / WARN / FAIL (plus inline `details:` for non-PASS rows). Trailer carries `SUBCOMMANDS_RUN`, `CHECKS_EVALUATED`, `PASS_COUNT`, `WARN_COUNT`, `FAIL_COUNT` per-agent extensions.
- **Tool boundaries:** `Read`, `Glob`, `Grep`, `Bash` (for executing grep / `wc` / `find` patterns). Forbidden: `Edit`, `Write`, `Agent`, `gh issue create` / `gh pr create` (advisory only).

## Default-conservative rendering

When a grep pattern is ambiguous against file content (e.g., a forbidden literal appears inside a quoted example block), the skill renders **FAIL**. Asymmetric-cost rationale: a spurious FAIL costs one user-glance round; a wrong-PASS lets real drift slip undetected. Mirrors `/audit-subagents` per [ADR-0011](../../../decisions/0011-subagent-quality-framework.md) D2 precedent.

## Ownership choice rationale

Per [ADR-0017](../../../decisions/0017-audit-meta-consolidation.md) D6 + [ADR-0011](../../../decisions/0011-subagent-quality-framework.md) D1: a **skill, not a 7th critic**, because [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7 caps critics at 6; **sibling to `/audit-subagents` (not an extension)** because a three-domain mega-rubric (subagents + structure + docs) would violate single-responsibility shape (Q2 alternatives 2C/2D rejected). Cadence (post-PRD hook? scheduled?) and per-PR boy-scout reviewer rule explicitly deferred per [ADR-0017](../../../decisions/0017-audit-meta-consolidation.md) D7.

## Relationship to other skills and agents

- **Sibling to** [`/audit-subagents`](audit-subagents.md) per [ADR-0017](../../../decisions/0017-audit-meta-consolidation.md) D6 — two independent skills, separate domains.
- **Inspects** repo-root files: `decisions/*.md`, `decisions/README.md`, `CLAUDE.md`, `README.md`, `.claude/agents/*.md`, `.claude/skills/*/SKILL.md`.
- **Honors the 6-critic-cap** per [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7 — `/audit-meta` is a skill, not a critic.
- **Authority:** [ADR-0017](../../../decisions/0017-audit-meta-consolidation.md) — D1 (subcommand architecture), D2 (structure rubric), D3 (docs rubric), D4 (report shape), D5 (bootstrap-mode), D6 (sibling-not-extension), D7 (deferred-cadence + boy-scout); [ADR-0011](../../../decisions/0011-subagent-quality-framework.md) D2 + D5 (mechanical-only + advisory-only precedent).

## Edges

- **part_of:** [[topics/knowledge-architecture]]
- **related_to:** [[entities/skills/audit-subagents]]
- **related_to:** [[concepts/glossary/adr]]
- **related_to:** [[concepts/glossary/generator-trailer]]
- **related_to:** [[topics/output-shapes]]
