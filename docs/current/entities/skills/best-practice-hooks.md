---
title: best-practice-hooks — on-demand authoritative Claude Code hooks guidance
summary: On-demand-loaded per ADR-0022 D2 + D8; auto-activates on hook questions (PreToolUse vs PostToolUse, where hook scripts live, can a hook invoke a skill, scope policy, blocking from a hook, SessionStart additionalContext, git hook taxonomy); 7 numbered rules distilled from docs.claude.com/hooks{,-guide} plus git-scm/githooks, 5 with Grep+Target audit hooks.
tags: [skill, kb, best-practice, docs-first, hooks, best-practice-hooks]
type: entity
last_updated: 2026-05-27
sources:
  - .claude/skills/best-practice-hooks/SKILL.md
  - decisions/0022-docs-first-kb-pattern.md
  - decisions/0015-claude-code-hooks-adoption.md
  - decisions/0016-workflow-event-log-jsonl.md
---

# /best-practice-hooks

The `/best-practice-hooks` skill is the **docs-first authoritative reference for Claude Code hook questions**. It encapsulates the rules Anthropic publishes at `docs.claude.com/en/docs/claude-code/{hooks-guide,hooks}` plus the canonical git hook taxonomy at `git-scm.com/docs/githooks` so the project doesn't re-derive them per session or per critic round. On-demand-loaded per [ADR-0022](../../../decisions/0022-docs-first-kb-pattern.md) D2 Tier-1 source priority — **zero CLAUDE.md bloat**.

## Role and responsibility

Same shape as the other on-demand best-practice skills per [ADR-0022](../../../decisions/0022-docs-first-kb-pattern.md) D1's 4-section convention:

1. **Answer hook questions** when the user asks something hook-shaped: "should I use a PreToolUse or PostToolUse hook?", "where do hook scripts live?", "can a hook invoke a skill or subagent?", "what hook scope (project/user/local)?", "how do I block a tool call from a hook?", "how do I inject session-start context?". Auto-loads via description-matching.
2. **Carry mechanical audit hooks** for the future PRD-D `/audit-against-best-practices` skill per [ADR-0022](../../../decisions/0022-docs-first-kb-pattern.md) D1 + D4. 5 of the 7 rules carry `**Grep:**` + `**Target:**` lines.

## The 7 rules (distilled from docs.claude.com + git-scm.com)

Brief summary; canonical text + audit hooks live in [`.claude/skills/best-practice-hooks/SKILL.md`](../../../.claude/skills/best-practice-hooks/SKILL.md):

1. **Hooks are shell commands** — they can validate, log, or notify, but cannot invoke skills or subagents (the most-common hook anti-pattern, technically impossible).
2. **Pick the hook event by intent** — Pre to gate, Post to react, Session/Stop for boundaries.
3. **Configuration scope determines who the hook binds** — choose project / user / local deliberately (4-scope precedence: Managed > Local > Project > User).
4. **Hook command contract** — read JSON from stdin, write JSON to stdout, exit 0 succeeds, exit 2 blocks (NOT exit 1 — the most common scripting bug).
5. **PreToolUse decisions go in `hookSpecificOutput.permissionDecision`** — allow / deny / ask / defer. Prefer `ask` over `deny` for "legitimate edits that might match my pattern by accident".
6. **SessionStart `additionalContext`** is the highest-leverage state-injection pattern — use it for branch / issue / config state.
7. **Git hook taxonomy** — `pre-commit` ≠ `commit-msg` ≠ `pre-push` (commit-message-content validation requires `commit-msg`, NOT `pre-commit`).

## Invocation contract

- **Caller:** auto-activated by Claude on description-matching hook-shaped questions. Can also be loaded explicitly.
- **Input:** none (reference skill — loads into context).
- **Output:** the loaded skill body itself.
- **Tool boundaries:** `Read`, `Grep`, `Glob` only. Forbidden: `Edit`, `Write`, `Bash` (no shell execution from a doc skill), `Agent` (leaf reference skill), any `gh`/`git` operation.

## Default-conservative — "go read the source"

When a hook question has no rule below that obviously applies, answer "load the canonical page directly: `https://docs.claude.com/en/docs/claude-code/hooks`" rather than guessing. The cost of a wrong rule-projection is a downstream hook built on a false premise (e.g., a PreToolUse hook that exits 1 thinking it blocks — it doesn't; only exit 2 blocks); the cost of an honest "go read the source" is one extra navigation step.

## Authority chain

Tier 1 is `docs.claude.com/en/docs/claude-code/{hooks-guide,hooks}` (canonical, Anthropic-maintained). Tier 3 is `docs/best-practices/*.md` video distillations — **intentionally empty** for hooks as of 2026-05-22 per [ADR-0022](../../../decisions/0022-docs-first-kb-pattern.md) D2 Tier-3-supplementary-is-optional (no hook-focused video distillation exists; the existing 5 distillations mention hooks only adjacently).

## Anti-pattern alert

The canonical hook anti-pattern called out throughout the skill body: **"trying to use a hook to invoke `/audit-subagents` (or any skill / subagent)"** — technically impossible per the docs.claude.com Limitations section. Command hooks communicate ONLY via stdin / stdout / stderr / exit-code; they cannot call `/`-commands or load skills. The project's [ADR-0015](../../../decisions/0015-claude-code-hooks-adoption.md) D2 scope policy codifies this at the project-policy level: hooks may log, validate by exit code, or notify via stderr — they MAY NOT auto-invoke skills / subagents.

## Relationship to other skills and agents

- **Sibling to** [`/best-practice-workflow`](best-practice-workflow.md) (cross-cutting) and [`/best-practice-subagents`](best-practice-subagents.md) (subagent-specific). All three share the [ADR-0022](../../../decisions/0022-docs-first-kb-pattern.md) D1 4-section shape.
- **Complements** the project's existing hook layer at `.claude/settings.json` + `.claude/hooks/` (per [ADR-0015](../../../decisions/0015-claude-code-hooks-adoption.md)) and the JSONL workflow event log at `.claude/logs/workflow-events.jsonl` (per [ADR-0016](../../../decisions/0016-workflow-event-log-jsonl.md)) by providing the docs-grounded *why* behind each hook-design convention.
- **Future consumer:** PRD-D `/audit-against-best-practices` per [ADR-0022](../../../decisions/0022-docs-first-kb-pattern.md) D4 mechanically executes the Grep/Target hooks across `.claude/settings.json` and `.githooks/*`.
- **Honors the 6-critic-cap** per [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7 — reference skill, not a critic.
- **Authority:** [ADR-0022](../../../decisions/0022-docs-first-kb-pattern.md) — D1 (4-section shape + Grep/Target schema), D2 (Tier-1/2/3 source priority), D3 (`best-practice-<topic>` location, topic = `hooks`), D5 (hand-curated ingest), D8 (PRD-A → siblings DAG; this is the hooks-sibling), D9 (Tier-3 preservation); [ADR-0015](../../../decisions/0015-claude-code-hooks-adoption.md) D1-D6 (project hooks policy); [ADR-0016](../../../decisions/0016-workflow-event-log-jsonl.md) D1-D4 (JSONL workflow event log).

## Edges

- **part_of:** [[topics/best-practices-hooks]]
- **part_of:** [[topics/hooks]]
- **related_to:** [[entities/skills/best-practice-workflow]]
- **related_to:** [[entities/skills/best-practice-subagents]]
- **related_to:** [[entities/skills/audit-subagents]]
- **related_to:** [[entities/skills/distill-video]]
