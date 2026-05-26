# Subagents — current capability table

Status: current as of 2026-05-26
Date: 2026-05-26

## Active subagents (10)

Per [ADR-0027](../../decisions/0027-subagent-model-selection.md) D3 two-tier model assignment policy. Critic vs generator role per [ADR-0005](../../decisions/0005-output-shape-and-slicing-methodology.md) D1c. Honors [ADR-0008](../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7 6-critic-cap.

| name | role | model | tools | when invoked | why this model |
|---|---|---|---|---|---|
| reviewer | critic | sonnet | Read/Glob/Grep/Bash | per PR by /ship stage 4b OR direct dispatch | Multi-file diff + 12-rule rubric + cross-ADR consistency requires substantial reasoning |
| prd-critic | critic | sonnet | Read/Glob/Grep/Bash | per PRD by /to-prd | 6-section template + 9-criterion rubric + ADR cross-consistency requires substantial reasoning |
| adr-critic | critic | sonnet | Read/Glob/Grep/Bash | per draft ADR by /to-prd | Convention compliance + cross-ADR consistency + supersession + D-ID verification requires substantial reasoning |
| slicer-critic | critic | sonnet | Read/Glob/Grep/Bash | per slicer output by /to-issues | 10-criterion rubric × N decompositions + INVEST analysis requires substantial reasoning |
| glossary-critic | critic | haiku | Read/Glob/Grep/Bash | per glossary draft by /glossary-add | 5-rule rubric on a single term — structured single-item audit; Haiku sufficient |
| backlog-critic | critic | haiku | Read/Glob/Grep/Bash | per captured issue by /promote-to-backlog | 4-criterion rubric on a single item — structured single-item audit; Haiku sufficient |
| slicer | generator | sonnet | Read/Glob/Grep/Bash | per PRD by /to-issues | N=3 decomposition + INVEST + cascade-doc analysis requires substantial reasoning |
| implementer | generator | sonnet | Read/Edit/Write/Bash/Glob/Grep | per slice by /ship stage 4a | Code-editing + multi-file judgment + commit/PR plumbing requires substantial reasoning per user req #8 |
| qa-tester | generator | sonnet | Read/Bash/Grep + mcp__playwright__* | per PRD by /qa-plan | Dual-mode: bash-mode mechanical (Haiku could work) + ui-mode Playwright + LLM-judge screenshots (Sonnet required); model = max-of-modes |
| current-state-reader | generator | haiku | Read/Glob/Grep | per topic-keyword by user-prompt-submit-topic-nudge hook | Single-file read + ≤15-line synthesis — purely structured output; Haiku sufficient |

## Decision policy

Per ADR-0027 D2: Sonnet 4.6 when role requires reasoning-heavy judgment across multiple files OR multi-criterion rubrics with cross-reference. Haiku when role is mechanical execution OR structured single-item audit (≤5 criteria, single artifact). Opus reserved for future explicit justification.

`qa-tester` model uses max-of-modes rule: ui-mode's Playwright + LLM-judge-screenshots load dominates the bash-mode mechanical load, so the subagent runs at Sonnet.

## Sources

- [ADR-0001](../../decisions/0001-foundational-design.md) D6 — subagent definition + tool boundaries pattern
- [ADR-0005](../../decisions/0005-output-shape-and-slicing-methodology.md) D1c — GENERATOR / CRITIC role classification
- [ADR-0008](../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7 — 6-critic-cap meta-rule (preserved unchanged)
- [ADR-0011](../../decisions/0011-subagent-quality-framework.md) D4 — audit-subagents 10-check rubric (`current-state-reader.md` must pass ALL-1..5 + GEN-1; CRIT-* don't apply per generator classifier)
- [ADR-0022](../../decisions/0022-docs-first-kb-pattern.md) D3 — `/best-practice-subagents` skill is the external-distillation sibling to this internal-state synthesis
- [ADR-0026](../../decisions/0026-knowledge-architecture-truth-docs.md) — truth-doc surface (this file lives on it)
- [ADR-0027](../../decisions/0027-subagent-model-selection.md) — canonical policy + per-agent rationale for "why this model"
- Each subagent's own `.claude/agents/<name>.md` body for behavior detail
