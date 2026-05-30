---
name: glossary-add
description: Add a single glossary term — interactive single-term flow that captures definition, scope category, and authority, then invokes glossary-critic before opening a trivial-lane PR. Use when the user (or a discretionary-surfacing agent) wants to land a new vocabulary term.
---

# /glossary-add — single-term interactive write path

Adds **one** glossary term per invocation: interview the user for the required fields, draft a CLAUDE.md INDEX row, invoke [`glossary-critic`](../../agents/glossary-critic.md) in a ≤3-round APPROVE/BLOCK loop, and on APPROVE open a `hotfix/glossary-<term>` PR with the `trivial` label.

This is the **explicit** write path per [ADR-0007](../../../decisions/0007-vocabulary-glossary-and-grill-me-extension.md) D4. The complementary discretionary-surfacing path is non-mandatory and described in each agent's own body.

Full role synthesis (jobs, invocation contract, cap warning, round-3 handling, edges): this file. Vocabulary: adr, trivial-lane, generator-trailer (see CLAUDE.md glossary).

## Process

1. **Collect the required fields** — either from inline arguments or by asking one question at a time:
   - **term** — the word or phrase being defined. Must not already exist in the CLAUDE.md glossary (critic enforces).
   - **definition** — one declarative sentence. Multi-sentence, vague, or tutorial-shaped definitions are rejected per [ADR-0007](../../../decisions/0007-vocabulary-glossary-and-grill-me-extension.md) D2.
   - **scope category** — exactly one of `a` (project jargon), `b` (external standard adopted), `c` (common word narrowed) per [ADR-0007](../../../decisions/0007-vocabulary-glossary-and-grill-me-extension.md) D3.
   - **authority** — `ADR-NNNN D-X`, a URL, or the literal `external`.

   Inline-args form: `/glossary-add <term> --definition "..." --category a|b|c --authority "..."`. Missing fields fall back to one-question-at-a-time prompts.

2. **Draft the INDEX row** — a single-line entry appended to the `## Glossary` section of `CLAUDE.md` at the alphabetically-correct position. Per [ADR-0032](../../../decisions/0032-workflow-only-architecture.md) D1, the KB layer is retired; the CLAUDE.md INDEX row is the sole artifact.

   Before drafting, count existing INDEX rows; at/above the ~35 soft cap per [ADR-0012](../../../decisions/0012-glossary-consolidation-single-tier.md) D5, surface a warning but proceed (the cap is soft).

3. **Invoke the critic** — state the round number explicitly (start at 1). Pass the drafted entry inline; `glossary-critic` no longer requires a target-zone argument (single-tier per [ADR-0012](../../../decisions/0012-glossary-consolidation-single-tier.md) D1). The 5-rule rubric: scope (a/b/c), no duplicate, one-sentence definition, authority field, inclusion threshold (≥3 citations across ≥2 of {`decisions/`, `.claude/agents/`, `.claude/skills/`}).

4. **Critic loop (≤3 rounds):**
   - **APPROVE** → step 5.
   - **BLOCK** with `ROUND < 3` → apply each finding from the itemized list, increment the round, re-invoke. Do not invent fixes the critic did not request.
   - **BLOCK** with `ROUND == 3` (or `ESCALATE: needs-human`) → STOP. Do NOT open the PR. Surface the verdict + failing findings; this is the user-revises-and-retries surface per the I5 escalation pattern.

5. **Open the trivial-lane PR** (only after APPROVE):

   ```bash
   git checkout main && git pull --ff-only origin main
   git checkout -b hotfix/glossary-<kebab-term>
   git add CLAUDE.md
   git commit -m "docs(glossary): add <term>" -m "<one-sentence why>" -m "Co-authored-by: Claude <noreply@anthropic.com>"
   git push -u origin hotfix/glossary-<kebab-term>
   gh pr create --title "docs(glossary): add <term>" --body "<see template>" --label trivial
   ```

   PR body MUST include: **Scope** ("Adds glossary entry for `<term>` to CLAUDE.md.") + **Critic audit trail** (the `glossary-critic` APPROVE verdict, or at minimum its CRITIC trailer). No `Closes` required — trivial-lane PRs skip slice ceremony per CLAUDE.md I3.

6. **Return the GENERATOR trailer** per [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D1c:

   ```
   RESULT: SUCCESS | STOPPED | INVALID_INPUT
   REASON: <one sentence>
   ARTIFACTS: <PR URL on SUCCESS; empty on STOPPED/INVALID_INPUT>
   TERM: <the term that was added>
   CRITIC_ROUND: <the round that produced APPROVE, or "n/a" on STOPPED>
   ```

## What this skill deliberately does NOT do

- Add multiple terms per invocation — one term per `/glossary-add` per [ADR-0007](../../../decisions/0007-vocabulary-glossary-and-grill-me-extension.md) D4. Batch backfills invoke once per term.
- Bypass the critic — `glossary-critic` is the sole authority on entry shape; the step-1 self-checks are fast-path convenience.
- Edit any files other than `CLAUDE.md`. ADR/README/Map-table edits are out of scope.
- Open a PR on round-3 BLOCK — the skill is the gatekeeper; a thrice-blocked entry never reaches `reviewer`.

## References

- Full role synthesis (invocation contract, edges): this file.
- [ADR-0007](../../../decisions/0007-vocabulary-glossary-and-grill-me-extension.md) — D2 (entry shape), D3 (scope rule), D4 (explicit write path), D7 (bootstrap-mode).
- [ADR-0012](../../../decisions/0012-glossary-consolidation-single-tier.md) — D1 (single-tier consolidation), D2 (≥3-citations threshold), D4 (5-rule rubric), D5 (~35-entry soft cap).
- [ADR-0032](../../../decisions/0032-workflow-only-architecture.md) — D1 (single-tier CLAUDE.md INDEX only; separate KB layer retired).
- [`.claude/agents/glossary-critic.md`](../../agents/glossary-critic.md) — the critic this skill invokes.
- Sibling: [`/glossary-fold`](../glossary-fold/SKILL.md) — bulk auto-fold of skill-local vocabulary.
