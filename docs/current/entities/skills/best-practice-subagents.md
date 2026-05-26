---
title: best-practice-subagents — on-demand authoritative subagent-design guidance
summary: On-demand-loaded sibling-A of the docs-first KB pattern per ADR-0022 D8 DAG; auto-activates via description-matching on subagent-design questions (tools, model, description, no-nested-spawn, preloaded skills); 6 numbered rules distilled from docs.claude.com/sub-agents, 5 with Grep+Target audit hooks for the future PRD-D /audit-against-best-practices.
tags: [skill, kb, best-practice, docs-first, subagents, best-practice-subagents]
type: entity
last_updated: 2026-05-27
sources:
  - .claude/skills/best-practice-subagents/SKILL.md
  - decisions/0022-docs-first-kb-pattern.md
  - decisions/0011-subagent-quality-framework.md
---

# /best-practice-subagents

The `/best-practice-subagents` skill is the **docs-first authoritative reference for Claude Code subagent-design questions**. It encapsulates the rules Anthropic publishes at `docs.claude.com/en/docs/claude-code/sub-agents` so this project doesn't re-derive them per session or per critic round. Sibling to [`/best-practice-workflow`](best-practice-workflow.md) (which covers cross-cutting workflow questions); this skill is the **subagent-specific deep cut**.

## Role and responsibility

Same shape as the other on-demand best-practice skills per [ADR-0022](../../../decisions/0022-docs-first-kb-pattern.md) D1's 4-section convention:

1. **Answer subagent-design questions** when the user asks something subagent-shaped: "how should I write a subagent?", "what tools should this subagent have?", "should this be a subagent or a skill?", "what model should this subagent use?", "can a subagent spawn another subagent?", "how do I preload skills into a subagent?". Auto-loads via description-matching.
2. **Carry mechanical audit hooks** for the future PRD-D `/audit-against-best-practices` skill per [ADR-0022](../../../decisions/0022-docs-first-kb-pattern.md) D1 + D4. 5 of the 6 rules carry `**Grep:**` + `**Target:**` lines.

## The 6 rules (distilled from docs.claude.com/sub-agents)

Brief summary; canonical text + audit hooks live in [`.claude/skills/best-practice-subagents/SKILL.md`](../../../.claude/skills/best-practice-subagents/SKILL.md):

1. **Design focused subagents** — each subagent should excel at one specific task.
2. **Limit tool access** — grant only the tools the subagent's job requires (explicit `tools:` allowlist or `disallowedTools:` denylist; omitting inherits everything).
3. **Write detailed descriptions** — Claude uses the `description:` field to decide when to delegate (auto-routing is description-matching).
4. **Choose the model deliberately** — `sonnet` / `opus` / `haiku` / `inherit` (default-on-omission is `inherit`).
5. **Preload skills via the `skills:` field** when the subagent needs domain knowledge at startup.
6. **Subagents CANNOT spawn other subagents** — do not put `Agent` in a subagent's `tools:` list (no-op at best, misleading at worst).

## Invocation contract

- **Caller:** auto-activated by Claude on description-matching subagent-shaped questions. Can also be loaded explicitly.
- **Input:** none (reference skill — loads into context).
- **Output:** the loaded skill body itself.
- **Tool boundaries:** `Read`, `Grep`, `Glob` only. Forbidden: `Edit`, `Write`, `Bash`, `Agent`, any `gh`/`git` operation. The skill is a leaf reference; per Rule 6 it would itself never spawn a subagent.

## Default-conservative — "go read the source"

When a subagent-design question has no rule below that obviously applies, answer "load the canonical page directly: `https://docs.claude.com/en/docs/claude-code/sub-agents`" rather than guessing. The cost of a wrong rule-projection is a downstream subagent shipped on a false premise; the cost of an honest "go read the source" is one extra navigation step.

## Authority chain

Tier 1 is `docs.claude.com/en/docs/claude-code/sub-agents` (canonical, Anthropic-maintained). Tier 3 is `docs/best-practices/*.md` video distillations (Anthropic-authored channels per [ADR-0019](../../../decisions/0019-best-practices-kb-pattern.md)). The Authoritative-guidance section cites Tier 1; the Supplementary section points to Tier 3 for the same topic (notably `what-are-subagents-jKErNxuxPXg.md` — the canonical Anthropic intro to the subagent abstraction).

## Relationship to other skills and agents

- **Sibling to** [`/best-practice-workflow`](best-practice-workflow.md) (cross-cutting) and [`/best-practice-hooks`](best-practice-hooks.md) (hooks-specific). All three share the [ADR-0022](../../../decisions/0022-docs-first-kb-pattern.md) D1 4-section shape.
- **Complements** [`/audit-subagents`](audit-subagents.md) by providing the docs-grounded *why* layer behind each mechanical convention — that skill is the *what* (10-check rubric per [ADR-0011](../../../decisions/0011-subagent-quality-framework.md) D4); this skill is the *why* (6 rules distilled from `docs.claude.com`).
- **Future consumer:** PRD-D `/audit-against-best-practices` per [ADR-0022](../../../decisions/0022-docs-first-kb-pattern.md) D4 mechanically executes the Grep/Target hooks across `.claude/agents/*.md`.
- **Honors the 6-critic-cap** per [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7 — reference skill, not a critic.
- **Authority:** [ADR-0022](../../../decisions/0022-docs-first-kb-pattern.md) — D1 (4-section shape + Grep/Target schema), D2 (Tier-1/2/3 source priority), D3 (`best-practice-<topic>` location convention applied to topic = `subagents`), D5 (hand-curated ingest), D8 (PRD-A → siblings DAG; this is the subagents-sibling), D9 (Tier-3 preservation), D11 (surgical supersession of [ADR-0019](../../../decisions/0019-best-practices-kb-pattern.md) D3 yt-dlp bits only); [ADR-0011](../../../decisions/0011-subagent-quality-framework.md) D2 + D5 (mechanical/grep + advisory-only precedent).

## Edges

- **part_of:** [[topics/best-practices-subagents]]
- **related_to:** [[entities/skills/best-practice-workflow]]
- **related_to:** [[entities/skills/best-practice-hooks]]
- **related_to:** [[entities/skills/audit-subagents]]
- **related_to:** [[entities/skills/distill-video]]
- **related_to:** [[concepts/glossary/subagent]]
- **related_to:** [[concepts/glossary/critic]]
