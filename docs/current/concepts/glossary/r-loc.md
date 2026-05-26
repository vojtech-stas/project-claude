---
title: R-LOC — reviewer rule capping slice PR diff at 300 runtime-artifact LoC
summary: The reviewer rule that caps a slice PR's diff at at most 300 LoC of runtime-artifact code (canonical definition of "runtime artifact" lives in reviewer.md).
tags: [glossary, reviewer-rule, project-jargon, slicing]
type: concept
last_updated: 2026-05-26
sources:
  - .claude/agents/reviewer.md
  - CLAUDE.md
---

# R-LOC

**R-LOC** is rule 9 in the [`reviewer`](../../../.claude/agents/reviewer.md) rubric. It caps a slice PR's diff at ≤300 LoC of *runtime-artifact* code. The qualifier "runtime-artifact" is load-bearing: docs, tests, configuration, and ADRs are NOT counted; only the agent/skill prompts under `.claude/agents/` and `.claude/skills/` plus the few other runtime-firing files are. The canonical definition of "runtime artifact" lives in `reviewer.md` itself — do not restate it elsewhere.

**Edges**

- **related-to:** [[concepts/glossary/r-closes]]
- **related-to:** [[concepts/glossary/r-meta]]
- **part-of:** [[entities/subagents/reviewer]]

## What

The rule fires on every slice PR the reviewer judges. Mechanics:

- Reviewer runs `git diff --stat origin/main..HEAD` (or equivalent) restricted to the runtime-artifact path set.
- Sums added + deleted lines in those paths.
- If total > 300 → BLOCK with "R-LOC: slice diff is `<N>` LoC of runtime-artifact code; cap is 300. Split the slice or move non-runtime content out of `.claude/`".

What counts as runtime artifact (per the canonical definition in `reviewer.md` — quoted here only by intent, not verbatim):

- `.claude/agents/*.md` — subagent prompts loaded at Agent-tool invocation time.
- `.claude/skills/*/SKILL.md` — skill prompts loaded at slash-command invocation time.
- `.claude/settings.json` — Claude Code hooks and permission configuration.
- `.claude/hooks/*.sh` and any other inline hook scripts.

What does NOT count:

- `decisions/*.md` (ADRs are non-runtime; they're read by humans and agents at slicing time, not at runtime).
- `docs/**/*.md` (documentation surface).
- `CLAUDE.md` (project rules; non-runtime per the canonical definition).
- `README.md`, any `tests/`, `.github/`, `.githooks/` (per the canonical scope).

For mixed PRs, the reviewer computes the sum from runtime paths only.

## Why

R-LOC exists because **slice reviewability degrades non-linearly with diff size**. Past ~300 LoC of runtime-artifact code, reviewer cannot reliably enforce scope (R-CLOSES becomes nominal: the PR says `Closes #N` but actually does 3 PRDs' worth of work) and cannot reliably catch YAGNI violations (drift hides in the volume). The cap is a forcing function: implementer SPIDR-splits before approaching the cap rather than letting reviewer BLOCK after.

Narrowing the cap to *runtime artifact* — rather than counting docs and ADRs — is intentional. Docs and ADR additions are usually expansionary by design (a new ADR adds material; a doc rewrite improves clarity by adding paragraphs). Counting them would force artificial doc-splitting that hurts readability for no reviewability gain. The runtime-artifact-only cap keeps the constraint where it matters (prompts that fire at agent-invocation time) and lets non-runtime additions flow freely.

## Examples from this project

- **Slice PRs in PRD #245 (this glossary migration)** — net runtime LoC ≈ 0 per slice; the 22 atomic notes are non-runtime `docs/current/`, CLAUDE.md is non-runtime, no `.claude/` paths touched. Well under the cap.
- **PRD #189 slice 1 (PreToolUse hooks)** — added `.claude/settings.json` JSON config + a CLAUDE.md row; runtime-counting was strict because hooks fire at every tool call.
- **PRD #80 (implementer subagent)** — slice 1 added `.claude/agents/implementer.md` directly; LoC was budgeted carefully to fit the 300 cap, splitting auto-retry logic into the agent body's prose rather than a separate runtime helper.

## Anti-patterns

- **"It's mostly docs" rationalization on a runtime-heavy PR** — R-LOC counts only runtime LoC; if runtime is over 300, docs justification doesn't help.
- **Moving runtime logic into docs to bypass R-LOC** — the test is INTENT, not just path: prompts copy-pasted into `docs/` while the agent file imports them inline are still runtime per the canonical definition.
- **Splitting one logical slice into two PRs only to stay under R-LOC** — defeats the rule's reviewability purpose; SPIDR-split into two VERTICAL slices (each end-to-end) rather than horizontally chunking one slice's work.

## Scope

(a) project jargon coined here

## Authority

[`.claude/agents/reviewer.md`](../../../.claude/agents/reviewer.md) rule 9

## References

- [`.claude/agents/reviewer.md`](../../../.claude/agents/reviewer.md) rule 9 — canonical R-LOC definition with runtime-artifact scope.
- [CLAUDE.md](../../../CLAUDE.md) I4 — slice-size cap surfaced at project-rule level; defers to reviewer for canonical definition.
- [[concepts/glossary/r-closes]] — sibling reviewer rule binding PR to slice issue.
- [[concepts/glossary/r-meta]] — sibling reviewer rule enforcing ADR provenance.
- [[concepts/glossary/spidr]] — split-fallback techniques to invoke when approaching the cap.
- [[entities/subagents/reviewer]] — the subagent that owns this rule.
