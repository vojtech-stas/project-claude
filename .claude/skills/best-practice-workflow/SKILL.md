---
name: best-practice-workflow
description: On-demand authoritative guidance for Claude Code workflow questions — slash-commands, skill invocation, settings hierarchy, sub-agent vs skill choice, project structure. Auto-loads when the user asks "should I use a slash-command or a skill here?", "where do project settings go?", "how does Claude pick which skill to load?", "is this a subagent or a skill job?", "what belongs in CLAUDE.md vs in a skill?", or any similar workflow-shape question. Distilled from `docs.claude.com/en/docs/claude-code/{slash-commands,sub-agents,settings,skills,hooks-guide,overview}` per ADR-0022 D1 (4-section shape) with mechanical Grep+Target audit hooks per ADR-0022 D1's audit-consumability schema for future `/audit-against-best-practices` (PRD-D).
tools: Read, Grep, Glob
---

# /best-practice-workflow — docs-first Claude Code workflow reference (thin dispatcher)

On-demand-loaded per [ADR-0022](../../../decisions/0022-docs-first-kb-pattern.md) D2 Tier-1 source priority. Reference text, not actuator — when loaded, the body knowledge already lives in the canonical KB. Thinned per [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D10 step 5 + D12; frontmatter `description:` is the Claude-routing surface that triggers auto-load on workflow questions.

- **Knowledge body** (full 6 rules + Grep/Target audit hooks + How-to-apply + Common-pitfalls per [ADR-0022](../../../decisions/0022-docs-first-kb-pattern.md) D1): [`docs/current/topics/best-practices-workflow.md`](../../../docs/current/topics/best-practices-workflow.md).
- **Entity note** (skill role, invocation contract, edges): [`docs/current/entities/skills/best-practice-workflow.md`](../../../docs/current/entities/skills/best-practice-workflow.md).

## Default conservative

When a workflow question has no rule in the topic synthesis that obviously applies, answer "load the canonical page directly: `<URL>`" rather than guessing. The cost of a wrong rule-projection is a downstream slice built on a false premise; the cost of an honest "go read the source" is one extra navigation step.

## Tool boundaries

Allowed: `Read`, `Grep`, `Glob` — reads project files only to answer "is this rule honored here?". Forbidden: `Edit`, `Write`, `Bash`, `Agent`, any `gh` / `git` operation (leaf reference skill; no mutations, no recursive invocation).

## References

- [ADR-0022](../../../decisions/0022-docs-first-kb-pattern.md) D1 / D2 / D3 — 4-section skill shape + Grep/Target schema, Tier-1/2/3 source priority, `.claude/skills/best-practice-<topic>/` location.
- [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D10 step 5 + D12 — T5 skill migration + skill body thinning targets.
- Siblings: [`/best-practice-subagents`](../best-practice-subagents/SKILL.md) (subagent-specific), [`/best-practice-hooks`](../best-practice-hooks/SKILL.md) (hook-specific).
