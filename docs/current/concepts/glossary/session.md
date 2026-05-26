---
title: session — a single Claude Code conversation in this repo
summary: A single Claude Code conversation in this repo (auto-loaded with CLAUDE.md on start), reconstructed by new sessions from live state rather than a formal handoff document.
tags: [glossary, runtime, common-word-narrowed, continuity]
type: concept
last_updated: 2026-05-26
sources:
  - decisions/0006-backlog-and-session-continuity.md
  - CLAUDE.md
---

# session

A **session** is a single Claude Code conversation in this repo — bounded by when the user opens Claude Code and when they end the conversation. Each session auto-loads CLAUDE.md, the project glossary, the user's memory file, and any in-flight subagent state. Session continuity across sessions is reconstructed from **live state** (`git log`, `gh issue list`, project board, workflow event log) rather than a formal handoff document.

**Edges**

- **related-to:** [[concepts/glossary/backlog]]
- **related-to:** [[concepts/glossary/prd]]
- **part-of:** [[topics/continuity]]

## What

What auto-loads at session start (per [ADR-0015](../../../decisions/0015-claude-code-hooks-adoption.md) and CLAUDE.md's auto-load policy):

- **CLAUDE.md** at the repo root — cross-cutting rules, hierarchy, glossary, operational git workflow.
- **The user's persistent memory file** at `~/.claude/projects/<project>/memory/MEMORY.md`.
- **The SessionStart hook's `additionalContext`** (per [ADR-0023](../../../decisions/0023-validation-and-notification-hooks-extension.md) D7) — branch, divergence vs `origin/main`, recent commits, open slice/PR/captured counts.

What does NOT auto-load — and what new sessions reconstruct from live state (per [ADR-0006](../../../decisions/0006-backlog-and-session-continuity.md) D2):

- Recent commits → `git log --oneline -10`
- In-flight slices → `gh issue list --state open --label slice`
- In-flight PRs → `gh pr list --state open`
- Forward queue → `gh issue list --label backlog`
- Visual progress → project board #2 column states
- Recent agent/bash events → `tail .claude/logs/workflow-events.jsonl`

The deliberate non-load of conversational history is the load-bearing design choice. Sessions are **stateless** between starts; the live-state surfaces are the source of truth.

## Why

Sessions exist as a unit because **conversational context is bounded and lossy**. Long sessions accumulate token-cost; cross-session conversational handoff is brittle (the next session would have to read a long transcript before doing useful work). The live-state reconstruction pattern is the answer: instead of trying to preserve conversational context, preserve only the artifacts (commits, issues, PRs, board state, event log) and let the new session reconstruct intent from those artifacts.

The natural pipeline milestones (`/grill-me` end, `/ship` end, `/qa-plan` end) always leave a new session in a state where live reconstruction is sufficient. Mid-task interruption (mid-grill or mid-slice) loses conversational context regardless of mechanism — accepted trade-off per [ADR-0006](../../../decisions/0006-backlog-and-session-continuity.md) D2.

The session-bounded-state property also enables the bootstrap-mode policy at finer granularity: in-flight pipeline runs use the CLAUDE.md they loaded at session start; mid-pipeline CLAUDE.md changes don't reach the running pipeline per [ADR-0010](../../../decisions/0010-implementer-subagent-auto-pipeline.md) D9.

## Examples from this project

- A typical session: open Claude Code, run `/grill-me`, run `/ship`, watch the autonomous pipeline complete the PRD, close session.
- Multi-session work: session 1 grills PRD #245, session 2 ships slice 1 via implementer subagent, session 3 ships slice 2 (this very slice).
- Mid-task interruption: session 4 starts mid-debugging of slice 3; reconstructs from `git status`, the open PR list, and the workflow event log.

## Anti-patterns

- **Hand-authored "session handoff" document** — duplicates live state and goes stale; rule #9 (DRY for docs) rejects.
- **Relying on conversational memory across sessions** — sessions don't share history; capture state in issues/commits/PRs instead.
- **Mid-pipeline re-reading of CLAUDE.md** — violates [ADR-0010](../../../decisions/0010-implementer-subagent-auto-pipeline.md) D9 in-flight bootstrap-mode; use the version loaded at session start for the duration of the pipeline run.

## Scope

(c) common word with narrowed meaning here

## Authority

[ADR-0006](../../../decisions/0006-backlog-and-session-continuity.md) D2

## References

- [ADR-0006](../../../decisions/0006-backlog-and-session-continuity.md) D2 — session-continuity-via-live-state design.
- [ADR-0010](../../../decisions/0010-implementer-subagent-auto-pipeline.md) D9 — in-flight-session bootstrap-mode for CLAUDE.md.
- [ADR-0015](../../../decisions/0015-claude-code-hooks-adoption.md) — Claude Code hooks (incl. SessionStart) adoption.
- [ADR-0016](../../../decisions/0016-workflow-event-log-jsonl.md) — workflow event log substrate consumed at session start.
- [ADR-0023](../../../decisions/0023-validation-and-notification-hooks-extension.md) D7 — SessionStart `additionalContext` shape.
- [CLAUDE.md](../../../CLAUDE.md) "Session continuity" — operational reconstruction commands.
