---
name: glossary-add
description: Add a single glossary term — interactive single-term flow that captures definition, scope category, authority, and target zone, then invokes glossary-critic before opening a trivial-lane PR. Use when the user (or a discretionary-surfacing agent) wants to land a new vocabulary term.
---

This skill adds **one** glossary term per invocation. It interviews the user for the required fields, invokes the [`glossary-critic`](../../agents/glossary-critic.md) subagent in a ≤3-round APPROVE/BLOCK loop, and on APPROVE opens a `hotfix/glossary-<term>` PR with the `trivial` label.

Per [ADR-0007](../../../decisions/0007-vocabulary-glossary-and-grill-me-extension.md) D4, this is the **explicit** write path. The complementary **discretionary surfacing** path (subagents inlining *"Heads up: 'X' looks glossary-worthy — run `/glossary-add` to capture"*) is non-mandatory and described in each agent's own body file.

## Process

1. **Collect the required fields** — either from inline arguments or by asking one question at a time. Required fields:
   - **term** — the word or phrase being defined. Must not already exist in either tier (the critic enforces).
   - **definition** — one declarative sentence. Multi-sentence, vague, or tutorial-shaped definitions are rejected by the critic per [ADR-0007](../../../decisions/0007-vocabulary-glossary-and-grill-me-extension.md) D2.
   - **scope category** — exactly one of `a` (project jargon coined here), `b` (external standard adopted), or `c` (common word with narrowed meaning here) per [ADR-0007](../../../decisions/0007-vocabulary-glossary-and-grill-me-extension.md) D3.
   - **authority** — one of: `ADR-NNNN D-X` (project decision), a URL (named external source), or the literal string `external` (industry-standard, no project-specific authority).
   - **zone** — defaults to **long-tail** (`GLOSSARY.md`). Pass `--key` to target the key-zone (`## Glossary (key terms)` in `CLAUDE.md`).

   Inline-args form: `/glossary-add <term> --definition "..." --category a|b|c --authority "..." [--key]`. Missing fields fall back to one-question-at-a-time prompts.

2. **Draft the entry markdown.** Use the canonical shape from [ADR-0007](../../../decisions/0007-vocabulary-glossary-and-grill-me-extension.md) D2: term + one-sentence definition + authority + (optional) see-also.

   - **Long-tail (`GLOSSARY.md`)** — append a new section/bullet under the alphabetically-correct position.
   - **Key-zone (`CLAUDE.md` `## Glossary (key terms)`)** — append under the alphabetically-correct position. Before drafting, count existing entries; if the count is at or above the ~25 cap per [ADR-0007](../../../decisions/0007-vocabulary-glossary-and-grill-me-extension.md) D1, STOP and report that key-zone is full — the user must demote an existing entry to long-tail first (deliberate trivial-lane edit; no auto-shuffle).
   - When adding to key-zone, also consider whether a cross-reference pointer in long-tail is warranted. When adding to long-tail, no key-zone pointer is required.

3. **Invoke the critic.** State the round number explicitly (start at round 1). Pass the drafted entry inline along with the **target zone** (`key-zone` or `long-tail`) — `glossary-critic`'s `When invoked` contract requires it. Per [ADR-0007](../../../decisions/0007-vocabulary-glossary-and-grill-me-extension.md) D5, the critic runs a single-entry rubric: scope category (a/b/c), no duplicate, one-sentence definition, authority field.

4. **Critic loop (≤3 rounds):**
   - On **APPROVE** → proceed to step 5.
   - On **BLOCK** with `ROUND < 3` → apply each finding from the itemized list, increment the round, re-invoke. Do not invent fixes the critic did not request; do not skip any finding.
   - On **BLOCK** with `ROUND == 3` (or `ESCALATE: needs-human`) → STOP. Do not open the PR. Surface the verdict to the user with the failing findings. Per I5 escalation pattern, this is the user-revises-and-retries surface.

5. **Open the trivial-lane PR.** Only after APPROVE.

   ```bash
   git checkout main
   git pull --ff-only origin main
   git checkout -b hotfix/glossary-<kebab-term>
   # apply the entry edit
   git add CLAUDE.md GLOSSARY.md   # whichever file was edited
   git commit -m "docs(glossary): add <term>" -m "<one-sentence why>" -m "Co-authored-by: Claude <noreply@anthropic.com>"
   git push -u origin hotfix/glossary-<kebab-term>
   gh pr create --title "docs(glossary): add <term>" --body "<see template below>" --label trivial
   ```

   PR body MUST include:
   - **`Closes`** — none required; trivial-lane PRs skip the slice ceremony per CLAUDE.md I3.
   - **Scope** — "Adds glossary entry for `<term>` to `<zone>`."
   - **Critic audit trail** — paste the `glossary-critic` APPROVE verdict (or at minimum its CRITIC trailer) so reviewer-time inspection is one click away.

6. **Return the GENERATOR trailer.** Per [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D1c:

   ```
   RESULT: SUCCESS | STOPPED | INVALID_INPUT
   REASON: <one sentence>
   ARTIFACTS: <PR URL on SUCCESS; empty on STOPPED/INVALID_INPUT>
   TERM: <the term that was added>
   ZONE: key-zone | long-tail
   CRITIC_ROUND: <the round that produced APPROVE, or "n/a" on STOPPED>
   ```

## What this skill deliberately does NOT do

- It does NOT add multiple terms in one invocation. One term per `/glossary-add` per [ADR-0007](../../../decisions/0007-vocabulary-glossary-and-grill-me-extension.md) D4. For batch backfills, invoke once per term.
- It does NOT auto-promote or demote terms between zones based on usage stats. Promotion is a deliberate trivial-lane edit per [ADR-0007](../../../decisions/0007-vocabulary-glossary-and-grill-me-extension.md) Alt-F.
- It does NOT bypass the critic. The `glossary-critic` is the sole authority on entry shape; this skill's self-checks during step 1 are a fast-path convenience, not a substitute.
- It does NOT edit any file other than `CLAUDE.md` (for key-zone additions) or `GLOSSARY.md` (for long-tail additions). ADR edits, README edits, and Map-table edits are out of scope.
- It does NOT open a PR on round-3 BLOCK. The skill is the gatekeeper for the trivial-lane PR; a thrice-blocked entry never reaches `reviewer`.

## References

- [ADR-0007](../../../decisions/0007-vocabulary-glossary-and-grill-me-extension.md) — D1 (two-tier location); D2 (entry shape); D3 (scope rule); D4 (this skill is the explicit write path); D5 (critic rubric); D7 (bootstrap-mode).
- [`.claude/agents/glossary-critic.md`](../../agents/glossary-critic.md) — the critic this skill invokes.
- [`.claude/skills/to-prd/SKILL.md`](../to-prd/SKILL.md) — the parent pattern (interactive skill that invokes a critic in a ≤3-round loop before publishing).
