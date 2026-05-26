---
title: promote-to-backlog — captured→backlog autopilot half (label-swap on backlog-critic APPROVE)
summary: Inline-fired skill per ADR-0008 D3 invoked by whatever agent just ran gh issue create --label captured; dispatches backlog-critic, swaps labels captured→backlog on APPROVE, leaves the captured label on BLOCK; non-interactive single-issue argument, no PR (label-swap only).
tags: [skill, backlog, generator, autopilot, promote-to-backlog]
type: entity
last_updated: 2026-05-27
sources:
  - .claude/skills/promote-to-backlog/SKILL.md
  - decisions/0008-workflow-autolog-bootstrap-and-naming.md
---

# /promote-to-backlog

The `/promote-to-backlog` skill is the **autopilot half of the captured→backlog mechanism** (the critic half is [`backlog-critic`](../subagents/backlog-critic.md)). Per [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D2 + D3, it runs **inline in the same agent context** that just created the `captured`-labeled issue — there is no daemon, no webhook, no GitHub Action.

## Role and responsibility

`/promote-to-backlog` has three jobs:

1. **Verify the issue is in scope.** Run `gh issue view <N> --json number,title,labels,body,state`. INVALID_INPUT if the issue doesn't exist, isn't labeled `captured`, or is closed.
2. **Invoke the critic** ([`backlog-critic`](../subagents/backlog-critic.md)) via the `Agent` tool. The critic fires **once** per item — no ≤3-round revision loop (per [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D2 autopilot semantics). Do not re-prompt; do not "fix" the captured body on BLOCK and re-invoke.
3. **Act on the verdict.**
   - **On APPROVE** — swap the labels: `gh issue edit <N> --remove-label captured --add-label backlog`. Post the verdict as a comment for audit trail. The issue is now in the curated backlog tier; it will surface in `gh issue list --label backlog`.
   - **On BLOCK** — post the verdict as a comment, leave the `captured` label in place. Do NOT close. The user reviews the captured tier on whatever cadence they prefer; per-item options are (a) cull (close as won't-promote), (b) rescue (manually relabel), or (c) restructure-and-recapture.

## Invocation contract

- **Caller:** any agent (subagent, skill, or main Claude) that just wrote a `captured`-labeled issue. Invoked **inline** in that agent's context per [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D3.
- **Input:** a single argument — the issue number (e.g., `/promote-to-backlog 73`). Missing argument → `INVALID_INPUT: no issue number supplied`.
- **Output:** the canonical [GENERATOR trailer](../../concepts/glossary/generator-trailer.md) with `ISSUE`, `VERDICT`, `PROMOTED` per-agent extensions. `RESULT: SUCCESS` covers BOTH APPROVE-and-promoted AND BLOCK-and-left-in-captured (the autopilot ran to completion in both cases). `RESULT: STOPPED` is reserved for unexpected runtime errors (gh auth failure, network error mid-swap).
- **Tool boundaries:** `Bash` (`gh issue view/edit/comment`), `Agent` (backlog-critic dispatch). No PR; no `Write`/`Edit` — label-swap is an issue mutation, not a code change.

## Shape differs from `/glossary-add`

This skill is **non-interactive** and takes the issue number as its single positional argument. Because it performs a label swap (not a code change), it does **NOT** open a PR. The agent that invoked it stays in control of the surrounding workflow; this skill just runs the autopilot beat. Contrast with `/glossary-add`, which is interactive AND opens a trivial-lane PR.

## Why single-fire (no ≤3-round loop)

Per [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D2, the autopilot fires once per item; BLOCK leaves the item in the captured tier for **lazy user review**, it does not trigger a revise-and-retry cycle. The captured tier IS the safety net — the user reviews and decides per-item. There is no `needs-human` escalation in autopilot mode; the user-rescue path *is* the escalation surface.

## Relationship to other skills and agents

- **Called inline by** any agent that just ran `gh issue create --label captured` — per CLAUDE.md rules #11 (forward-work captures) + #13 (root-cause workflow captures).
- **Invokes** [`backlog-critic`](../subagents/backlog-critic.md) once per item.
- **Sibling to** [`/glossary-add`](glossary-add.md) — both autopilot skills that invoke a critic before publishing; diverge in interactivity (interactive vs non-interactive) and side-effect shape (PR vs label-swap).
- **Honors the 6-critic-cap** per [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7 — `/promote-to-backlog` is a skill; its gate is `backlog-critic`.
- **Authority:** [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) — D1 (two-tier architecture), D2 (autopilot semantics this skill implements), D3 (inline-firing convention), D4 (rubric the critic enforces), D8 (bootstrap-mode acknowledgment).

## Edges

- **part_of:** [[topics/knowledge-architecture]]
- **related_to:** [[entities/subagents/backlog-critic]]
- **related_to:** [[entities/skills/glossary-add]]
- **related_to:** [[concepts/glossary/backlog]]
- **related_to:** [[concepts/glossary/generator-trailer]]
