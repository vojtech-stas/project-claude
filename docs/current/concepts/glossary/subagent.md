---
title: subagent — specialist agent with isolated context
summary: A specialist agent invoked via the `Agent` tool with its own model, restricted tool set, and isolated context window, defined under `.claude/agents/<name>.md`.
tags: [glossary, runtime, common-word-narrowed, agents]
type: concept
last_updated: 2026-05-26
sources:
  - decisions/0001-foundational-design.md
  - CLAUDE.md
  - https://docs.claude.com/en/docs/claude-code/sub-agents
---

# subagent

A **subagent** is a specialist agent defined under [`.claude/agents/<name>.md`](../../../.claude/agents/) and invoked by the main agent (or by orchestrators like [`/ship`](../../../.claude/skills/ship/SKILL.md)) via Claude Code's `Agent` tool. Each subagent has its own isolated context window, its own model choice, and its own restricted tool set — three properties that together make subagents fundamentally different from skills.

**Edges**

- **related-to:** [[concepts/glossary/critic]]
- **related-to:** [[entities/skills]]
- **part-of:** [[topics/agents-and-orchestration]]

## What

A subagent file at `.claude/agents/<name>.md` declares (per [Anthropic's subagent docs](https://docs.claude.com/en/docs/claude-code/sub-agents)):

- **Frontmatter** — `name`, `description` (drives auto-delegation matching), `tools` (the restricted set), `model` (often Opus for critics, Sonnet for generators).
- **Body** — the agent's prompt: role, methodology, tool boundaries, output shape, references.

Properties that matter operationally:

- **Isolated context window** — a subagent does NOT see the main agent's conversation history. The dispatching agent passes input via the `Agent` tool prompt; the subagent returns a finite output. This isolation is the load-bearing reason for the project's no-nested-spawn rule (subagents cannot invoke other subagents; the [`implementer`](../../../.claude/agents/implementer.md) is explicitly forbidden from using `Agent` per [ADR-0010](../../../decisions/0010-implementer-subagent-auto-pipeline.md) D6).
- **Restricted tool set** — declared at the subagent file level; the runtime enforces. Critics typically have Read/Grep only (cannot write); generators add Edit/Write/Bash.
- **Deliberate model choice** — Opus for adversarial judgment (critics), Sonnet for execution (generators). Mismatched model choices waste cost or under-power the role.

The project currently hosts 8 subagents under `.claude/agents/`: 6 critics (`reviewer`, `prd-critic`, `adr-critic`, `slicer-critic`, `glossary-critic`, `backlog-critic`) per the [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7 6-critic-cap, plus 2 generators (`slicer`, `implementer`) and [`qa-tester`](../../../.claude/agents/qa-tester.md) (generator per [ADR-0020](../../../decisions/0020-qa-automation-writer-executor.md) D9).

## Why

Subagents exist because **specialization beats generalization for bounded jobs**. A critic that only judges PRDs is sharper than a critic that judges PRDs, ADRs, slices, and PRs — the rubric stays tight, the failure modes are well-known, and the agent doesn't have to context-switch between rubrics. The isolated context window enforces the specialization: a subagent literally cannot drift into adjacent concerns because it cannot see them.

The restricted tool set is the second load-bearing property. A critic with Write tools could quietly fix its own mistakes rather than blocking — the conflict-of-interest failure mode the generator/critic pattern exists to prevent. The runtime enforcement of tool boundaries makes the prevention mechanical, not merely conventional.

The no-nested-spawn rule (subagents cannot use `Agent`) prevents runaway spawning and keeps the cost surface bounded; orchestration responsibility stays with the main agent or with skills (`/ship`).

## Examples from this project

- **[`implementer`](../../../.claude/agents/implementer.md)** — the generator that ships slice PRs end-to-end; tools Read/Edit/Write/Bash/Glob/Grep, model Opus, dispatched by [`/ship`](../../../.claude/skills/ship/SKILL.md) stage 4 per [ADR-0010](../../../decisions/0010-implementer-subagent-auto-pipeline.md) D2.
- **[`reviewer`](../../../.claude/agents/reviewer.md)** — the critic that judges every slice PR; auto-merges on APPROVE per [ADR-0002](../../../decisions/0002-autonomous-merge-policy.md).
- **[`qa-tester`](../../../.claude/agents/qa-tester.md)** — the QA executor; Read/Bash/Grep only (per [ADR-0020](../../../decisions/0020-qa-automation-writer-executor.md) D3); walks the writer's plan one-by-one.

## Anti-patterns

- **Subagent that writes when it should only judge** — violates the judge-not-write separation; reintroduces the conflict-of-interest the critic pattern exists to prevent.
- **Subagent invoking another subagent** — runaway-spawn risk; orchestration is the main agent's or a skill's job per [ADR-0010](../../../decisions/0010-implementer-subagent-auto-pipeline.md) D6.
- **Subagent with the maximum tool set "just in case"** — defeats the restricted-tool property; reviewer can no longer reason about the subagent's possible actions.
- **Subagent role overlap** — two critics judging the same artifact with different rubrics — pick one or merge per the 6-critic-cap rule.

## Scope

(c) common word with narrowed meaning here

## Authority

[ADR-0001](../../../decisions/0001-foundational-design.md) D6

## References

- [ADR-0001](../../../decisions/0001-foundational-design.md) D6 — subagent definition and `.claude/agents/` layout.
- [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7 — 6-critic-cap meta-rule.
- [ADR-0010](../../../decisions/0010-implementer-subagent-auto-pipeline.md) D6 — `implementer` no-nested-spawn rule; subagent tool boundaries pattern.
- [ADR-0011](../../../decisions/0011-subagent-quality-framework.md) — subagent quality audit framework.
- [Anthropic subagents docs](https://docs.claude.com/en/docs/claude-code/sub-agents) — upstream specification.
- [`.claude/skills/best-practice-subagents/SKILL.md`](../../../.claude/skills/best-practice-subagents/SKILL.md) — docs-grounded subagent-design rules.
