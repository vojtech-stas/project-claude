---
name: best-practice-subagents
description: On-demand authoritative guidance for Claude Code subagent-design questions — frontmatter fields, tool boundaries, model choice, preloaded skills, the no-nested-spawn rule, and the description-driven delegation contract. Auto-loads when the user asks "how should I write a subagent?", "what tools should this subagent have?", "should this be a subagent or a skill?", "what model should this subagent use?", "can a subagent spawn another subagent?", "how do I preload skills into a subagent?", or any similar subagent-shape question. Distilled from `docs.claude.com/en/docs/claude-code/sub-agents` per ADR-0022 D1 (4-section shape) with mechanical Grep+Target audit hooks per ADR-0022 D1's audit-consumability schema for future `/audit-against-best-practices` (PRD-D).
tools: Read, Grep, Glob
---

# /best-practice-subagents — docs-first subagent-design reference (thin dispatcher)

On-demand-loaded per [ADR-0022](../../../decisions/0022-docs-first-kb-pattern.md) D2 Tier-1 source priority. Sibling to [`/best-practice-workflow`](../best-practice-workflow/SKILL.md) (cross-cutting); this skill is the **subagent-specific deep cut**. Reference text, not actuator; thinned per [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D10 step 5 + D12 — frontmatter `description:` triggers auto-load on subagent-design questions.

- **Knowledge body** (full 6 rules + Grep/Target audit hooks + How-to-apply + Common-pitfalls per [ADR-0022](../../../decisions/0022-docs-first-kb-pattern.md) D1): [`docs/current/topics/best-practices-subagents.md`](../../../docs/current/topics/best-practices-subagents.md).
- **Entity note** (skill role, invocation contract, edges): [`docs/current/entities/skills/best-practice-subagents.md`](../../../docs/current/entities/skills/best-practice-subagents.md).

## Default conservative

When a subagent-design question has no rule in the topic synthesis that obviously applies, answer "load the canonical page directly: `https://docs.claude.com/en/docs/claude-code/sub-agents`" rather than guessing. The cost of a wrong rule-projection is a downstream subagent shipped on a false premise; the cost of an honest "go read the source" is one extra navigation step.

## Tool boundaries

Allowed: `Read`, `Grep`, `Glob` — reads project files only to answer "is this rule honored here?". Forbidden: `Edit`, `Write`, `Bash`, `Agent`, any `gh` / `git` operation (leaf reference skill; no mutations; no recursive invocation, consistent with the no-nested-spawn rule covered in the topic synthesis).

## References

- [ADR-0022](../../../decisions/0022-docs-first-kb-pattern.md) D1 / D2 / D3 / D8 — 4-section skill shape + Grep/Target schema, Tier priority, `.claude/skills/best-practice-<topic>/` location, DAG sequencing.
- [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D10 step 5 + D12 — T5 skill migration + skill body thinning targets.
- Siblings: [`/best-practice-workflow`](../best-practice-workflow/SKILL.md) (cross-cutting), [`/best-practice-hooks`](../best-practice-hooks/SKILL.md) (hook-specific).
