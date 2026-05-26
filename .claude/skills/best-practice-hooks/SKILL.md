---
name: best-practice-hooks
description: On-demand authoritative guidance for Claude Code hooks — when to use PreToolUse vs PostToolUse, where hook scripts live, whether a hook can invoke a skill, what scope (project/user/local) fits a given rule, how to block a tool call from a hook, and how SessionStart `additionalContext` injects state. Auto-loads when the user asks "should I use a PreToolUse or PostToolUse hook?", "where do hook scripts live?", "can a hook invoke a skill or subagent?", "what hook scope should I use (project/user/local)?", "how do I block a tool call from a hook?", "how do I inject session-start context?", or similar hook-shape questions. Distilled from `docs.claude.com/en/docs/claude-code/{hooks-guide,hooks}` per ADR-0022 D1 (4-section shape) with mechanical Grep+Target audit hooks per ADR-0022 D1's audit-consumability schema for future `/audit-against-best-practices` (PRD-D).
tools: Read, Grep, Glob
---

# /best-practice-hooks — docs-first Claude Code hooks reference (thin dispatcher)

On-demand-loaded per [ADR-0022](../../../decisions/0022-docs-first-kb-pattern.md) D2 Tier-1 source priority. Sibling to [`/best-practice-workflow`](../best-practice-workflow/SKILL.md) (cross-cutting) and [`/best-practice-subagents`](../best-practice-subagents/SKILL.md) (subagent-specific); this skill is the **hook-specific deep cut**. Reference text, not actuator; thinned per [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D10 step 5 + D12 — frontmatter `description:` triggers auto-load on hook questions.

- **Knowledge body** (full 7 rules + Grep/Target audit hooks + How-to-apply + Common-pitfalls per [ADR-0022](../../../decisions/0022-docs-first-kb-pattern.md) D1): [`docs/current/topics/best-practices-hooks.md`](../../../docs/current/topics/best-practices-hooks.md).
- **Entity note** (skill role, invocation contract, edges): [`docs/current/entities/skills/best-practice-hooks.md`](../../../docs/current/entities/skills/best-practice-hooks.md).

## Default conservative

When a hook question has no rule in the topic synthesis that obviously applies, answer "load the canonical page directly: `https://docs.claude.com/en/docs/claude-code/hooks`" rather than guessing. The cost of a wrong rule-projection is a downstream hook built on a false premise (e.g., a PreToolUse hook that exits 1 thinking it blocks — it doesn't; only exit 2 blocks); the cost of an honest "go read the source" is one extra navigation step.

## Tool boundaries

Allowed: `Read`, `Grep`, `Glob` — reads project files only to answer "is this rule honored here?". Forbidden: `Edit`, `Write`, `Bash` (no shell execution from a doc skill), `Agent`, any `gh` / `git` operation (leaf reference skill; no mutations, no recursive invocation).

## References

- [ADR-0022](../../../decisions/0022-docs-first-kb-pattern.md) D1 / D2 / D3 / D8 — 4-section skill shape + Grep/Target schema, Tier-1/2/3 source priority, `.claude/skills/best-practice-<topic>/` location, DAG sequencing.
- [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D10 step 5 + D12 — T5 skill migration + skill body thinning targets.
- [ADR-0015](../../../decisions/0015-claude-code-hooks-adoption.md) D1-D6 — project hooks policy (logging/validation/notification only; no skill auto-invocation).
- Siblings: [`/best-practice-workflow`](../best-practice-workflow/SKILL.md) (cross-cutting), [`/best-practice-subagents`](../best-practice-subagents/SKILL.md) (subagent-specific).
