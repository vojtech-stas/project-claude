---
title: R-LOC — reviewer hard-block on slice PR exceeding 300 runtime-artifact LoC
summary: The reviewer rule that caps a slice PR's diff at ≤300 LoC of runtime-artifact code (under `.claude/agents/` and `.claude/skills/`); docs, ADRs, and config are uncapped.
tags: [rule, reviewer-rubric, hard-block]
type: concept
last_updated: 2026-05-26
sources:
  - .claude/agents/reviewer.md rule 9
  - CLAUDE.md
---

# R-LOC

**R-LOC** is rule 9 in the [`reviewer`](../../../.claude/agents/reviewer.md) rubric. It hard-blocks any slice PR whose diff exceeds **300 LoC of runtime-artifact code**. The canonical definition of "runtime artifact" lives in `reviewer.md` itself; this rule note expands the operational mechanics. The glossary stub at [[concepts/glossary/r-loc]] is the short vocabulary entry; this note is the full rule definition.

## What

The rule fires on every slice PR. Mechanics:

- Reviewer runs `git diff --stat origin/main..HEAD` restricted to the runtime-artifact path set.
- Sums added + deleted lines in those paths (absolute LoC, not net).
- If total > 300 → BLOCK with `R-LOC: slice diff is <N> LoC of runtime-artifact code; cap is 300. Split the slice or move non-runtime content out of .claude/`.

**Runtime artifact** (counted toward the cap):

- `.claude/agents/*.md` — subagent prompts loaded at Agent-tool invocation time.
- `.claude/skills/*/SKILL.md` — skill prompts loaded at slash-command invocation time.
- `.claude/settings.json` — Claude Code hooks and permission configuration.
- `.claude/hooks/*.sh` — hook scripts that fire on Claude Code events.

**Non-runtime** (NOT counted, uncapped):

- `decisions/*.md` (ADRs are non-runtime; read by humans and agents at slicing/review time).
- `docs/**/*.md` (documentation surface, including the KB compiled wiki).
- `CLAUDE.md` (project rules; non-runtime per the canonical scope).
- `README.md`, anything under `tests/`, `.github/`, `.githooks/`.

For mixed PRs, the reviewer computes the sum from runtime paths only.

## Why

R-LOC exists because **slice reviewability degrades non-linearly with diff size**. Past ~300 LoC of runtime-artifact code, the reviewer cannot reliably enforce scope (R-CLOSES becomes nominal: the PR says `Closes #N` but actually does 3 PRDs' worth of work) and cannot reliably catch YAGNI violations (drift hides in the volume). The cap is a forcing function: implementer SPIDR-splits before approaching it rather than letting reviewer BLOCK after.

Narrowing the cap to *runtime artifact* — rather than counting docs and ADRs — is intentional. Docs and ADR additions are usually expansionary by design (new ADR adds material; doc rewrite improves clarity by adding paragraphs). Counting them would force artificial doc-splitting that hurts readability for no reviewability gain. The runtime-artifact-only cap keeps the constraint where it matters (prompts that fire at agent-invocation time) and lets non-runtime additions flow freely.

## How to check

```bash
gh pr view <PR> --json files --jq '.files[] | select(.path | startswith(".claude/agents/") or startswith(".claude/skills/") or startswith(".claude/hooks/") or (.path == ".claude/settings.json")) | .additions + .deletions' | awk '{s+=$1} END {print s}'
```

If the sum > 300 → BLOCK. Count ONLY runtime-artifact paths; ignore non-runtime paths entirely (do not count them, do not blend them).

## Exemptions

- **Trivial-lane PRs** labeled `trivial` (≤10 LoC runtime diff, no behavior change): not subject to the cap; fast-path independently.
- **PRD-tier PRs** labeled `prd` (the PRD itself, not a slice): docs-only and exempt.

## Recovery

When approaching the cap, invoke SPIDR fallback techniques (per [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D2): **S**pike split (research-first slice), **I**nterface split (different interface surface), **R**ules split (different business rules). For this domain, S/I/R are most applicable; P and D rarely fit. The slice body's "What ships" should include a SPIDR fallback hint pre-named by the slicer.

## Examples

- **Slice 1 of PRD #245 (glossary migration)** — net runtime LoC = 0; the 22 atomic notes are all under `docs/current/`, no `.claude/` paths touched. Well under cap.
- **PRD #189 slice 1 (PreToolUse hooks)** — added `.claude/settings.json` + hooks; runtime-counting was strict.
- **Slice 3 of PRD #253** (the planned reviewer.md thinning) is ~580 absolute LoC and MUST be split per the slicer-critic per the PRD itself.

## Edges

- **part_of:** [[entities/subagents/reviewer]]
- **defines:** [[concepts/glossary/r-loc]]
- **related_to:** [[concepts/rules/r-closes]]
- **related_to:** [[concepts/rules/r-meta]]
- **related_to:** [[concepts/glossary/spidr]]
- **part_of:** [[topics/reviewer-philosophy]]
