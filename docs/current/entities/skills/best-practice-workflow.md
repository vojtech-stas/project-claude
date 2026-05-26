---
title: best-practice-workflow — on-demand authoritative Claude Code workflow guidance
summary: On-demand-loaded per ADR-0022 D2 Tier-1 source priority; auto-activates via description-matching on workflow questions (slash-commands vs skills, settings hierarchy, subagent-vs-skill, CLAUDE.md vs skill vs hook); 6 numbered rules distilled from docs.claude.com, each with Grep+Target audit hooks for the future PRD-D /audit-against-best-practices.
tags: [skill, kb, best-practice, docs-first, best-practice-workflow]
type: entity
last_updated: 2026-05-27
sources:
  - .claude/skills/best-practice-workflow/SKILL.md
  - decisions/0022-docs-first-kb-pattern.md
  - decisions/0019-best-practices-kb-pattern.md
---

# /best-practice-workflow

The `/best-practice-workflow` skill is the **docs-first authoritative reference for Claude Code workflow questions**. It encapsulates the rules Anthropic publishes at `docs.claude.com` so the project doesn't re-derive them per session or per critic round. On-demand-loaded per [ADR-0022](../../../decisions/0022-docs-first-kb-pattern.md) D2 Tier-1 source priority — **zero CLAUDE.md bloat** per the rationale in ADR-0022 Context.

## Role and responsibility

`/best-practice-workflow` is a **reference skill**, not an actuator. Its two jobs:

1. **Answer Claude Code workflow questions** when the user asks something workflow-shaped: "should I use a slash-command or a skill?", "where do project settings go?", "is this a subagent or a skill job?", "what belongs in CLAUDE.md vs in a skill?". The skill's `description:` frontmatter is the Claude-routing surface that triggers auto-load on these question shapes.
2. **Carry mechanical audit hooks** for the future PRD-D `/audit-against-best-practices` skill per [ADR-0022](../../../decisions/0022-docs-first-kb-pattern.md) D1 + D4. Each rule includes `**Grep:**` + `**Target:**` lines naming the literal pattern and target file glob — so a downstream auditor can mechanically verify rule compliance without LLM judgment.

## The 4-section body shape

Per [ADR-0022](../../../decisions/0022-docs-first-kb-pattern.md) D1, every `best-practice-*` skill follows the same 4-section shape:

1. **Authoritative guidance** — 6 numbered rules distilled from `docs.claude.com/en/docs/claude-code/{slash-commands,sub-agents,settings,skills,hooks-guide,overview}` fetched 2026-05-22. Each rule has `**Rule:**` / `**Why:**` / `**Authority:**`; 4 of 6 carry `**Grep:**` + `**Target:**` audit hooks.
2. **Supplementary** — Tier-3 pointers to existing `docs/best-practices/` video distillations covering adjacent workflow material (Anthropic-authored channels per [ADR-0019](../../../decisions/0019-best-practices-kb-pattern.md)).
3. **How to apply to this project** — concrete checks against current project files (which existing skills/subagents/settings already honor each rule).
4. **Common pitfalls** — anti-patterns drawn from the docs + project history.

## The 6 rules (distilled from docs.claude.com)

Brief summary; the canonical text + Grep/Target hooks live in [`.claude/skills/best-practice-workflow/SKILL.md`](../../../.claude/skills/best-practice-workflow/SKILL.md):

1. Every skill MUST declare a `description:` explaining both what it does AND when to use it.
2. Skill body content stays in context for every subsequent turn — keep it concise.
3. Subagents are for context isolation; use one when a task would flood the main thread with bytes you won't reference again.
4. Subagents and skills MUST limit tool access to the minimum needed for their job.
5. Settings live in a 4-scope precedence hierarchy — choose the scope deliberately (Managed > Local > Project > User).
6. CLAUDE.md is for cross-cutting standards; skills are for repeatable workflows; hooks are for deterministic mechanical actions.

## Invocation contract

- **Caller:** auto-activated by Claude on description-matching workflow questions. Can also be loaded explicitly by the user.
- **Input:** none (the skill is a reference text — it just loads into context).
- **Output:** the loaded skill body itself; no separate emitted output. Cross-references to project files come from the "How to apply" section.
- **Tool boundaries:** `Read`, `Grep`, `Glob` — the skill reads project files only to answer "is this rule honored here?" when asked. Forbidden: `Edit`, `Write` (no mutations from a reference skill), `Bash` (no shell execution), `Agent` (leaf reference skill, no recursive invocation), any `gh`/`git` operation.

## Default-conservative — "go read the source"

When a workflow question has no rule below that obviously applies, answer "load the canonical page directly: `<URL>`" rather than guessing. The cost of a wrong rule-projection is a downstream slice built on a false premise; the cost of an honest "go read the source" is one extra navigation step.

## Relationship to other skills and agents

- **Sibling to** [`best-practice-subagents`](best-practice-subagents.md) (subagent-specific deep cut) and [`best-practice-hooks`](best-practice-hooks.md) (hook-specific deep cut). This skill is the cross-cutting workflow surface; the siblings cover their topic in depth without duplication.
- **Complements** [`/audit-subagents`](audit-subagents.md) — that skill is the mechanical *what* audit; this skill is the docs-grounded *why* layer.
- **Consumes** existing video distillations under `docs/best-practices/` produced by [`/distill-video`](distill-video.md) as Tier-3 supplementary references.
- **Future consumer:** PRD-D `/audit-against-best-practices` per [ADR-0022](../../../decisions/0022-docs-first-kb-pattern.md) D4 will mechanically execute the Grep/Target hooks across project files.
- **Honors the 6-critic-cap** per [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7 — this is a reference skill, not a critic.
- **Authority:** [ADR-0022](../../../decisions/0022-docs-first-kb-pattern.md) — D1 (4-section skill shape + Grep/Target audit-hook schema), D2 (Tier-1/2/3 source priority), D3 (`.claude/skills/best-practice-<topic>/` location convention), D5 (hand-curated curl-based ingest), D9 (existing video distillations preserved as Tier 3 supplementary), D11 (surgical supersession of [ADR-0019](../../../decisions/0019-best-practices-kb-pattern.md) D3 yt-dlp bits only).

## Edges

- **part_of:** [[topics/best-practices-workflow]]
- **related_to:** [[entities/skills/best-practice-subagents]]
- **related_to:** [[entities/skills/best-practice-hooks]]
- **related_to:** [[entities/skills/distill-video]]
- **related_to:** [[entities/skills/audit-subagents]]
- **related_to:** [[concepts/glossary/subagent]]
