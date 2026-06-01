---
name: glossary
description: Glossary management skill with two subcommands — `/glossary add` for single-term interactive entry flow; `/glossary fold` for bulk-fold of skill-local vocabulary sections. Both flows gate through glossary-critic before opening a PR. Use `/glossary add` when the user wants to land a new vocabulary term; use `/glossary fold` to scan and promote skill-local vocabulary entries to CLAUDE.md. Per ADR-0038 D3 (consolidation of former /glossary-add + /glossary-fold skills).
tools: Read, Glob, Grep, Bash
---

# /glossary — glossary management (add | fold)

Merged per [ADR-0038](../../../decisions/0038-skill-vs-agent-rule.md) D3 from the former `/glossary-add` (interactive single-entry flow) and `/glossary-fold` (bulk auto-fold flow). Both subcommands are preserved verbatim; both gate through [`glossary-critic`](../../agents/glossary-critic.md) before opening a PR. Per [ADR-0017](../../../decisions/0017-audit-meta-consolidation.md) subcommand-consolidation precedent.

## Dispatch

```
/glossary add [<term> --definition "..." --category a|b|c --authority "..."]
/glossary fold
```

- **`/glossary add`** → single-term interactive write path (below, §Add flow).
- **`/glossary fold`** → bulk-fold of skill-local vocabulary sections (below, §Fold flow).
- **No-arg / unknown subcommand** → print usage: "`/glossary add` | `/glossary fold`" and stop.

The first positional argument after `/glossary` is the subcommand. Branch on it before any other logic.

---

## §Add flow — single-term interactive write path

Adds **one** glossary term per invocation: interview the user for the required fields, draft a CLAUDE.md INDEX row, invoke [`glossary-critic`](../../agents/glossary-critic.md) in a ≤3-round APPROVE/BLOCK loop, and on APPROVE open a `hotfix/glossary-<term>` PR with the `trivial` label.

This is the **explicit** write path per [ADR-0007](../../../decisions/0007-vocabulary-glossary-and-grill-me-extension.md) D4 (as consolidated by ADR-0038 D3). The complementary discretionary-surfacing path is non-mandatory and described in each agent's own body.

Full role synthesis (jobs, invocation contract, cap warning, round-3 handling, edges): this file. Vocabulary: adr, trivial-lane, generator-trailer (see CLAUDE.md glossary).

### Process

1. **Collect the required fields** — either from inline arguments or by asking one question at a time:
   - **term** — the word or phrase being defined. Must not already exist in the CLAUDE.md glossary (critic enforces).
   - **definition** — one declarative sentence. Multi-sentence, vague, or tutorial-shaped definitions are rejected per [ADR-0007](../../../decisions/0007-vocabulary-glossary-and-grill-me-extension.md) D2.
   - **scope category** — exactly one of `a` (project jargon), `b` (external standard adopted), `c` (common word narrowed) per [ADR-0007](../../../decisions/0007-vocabulary-glossary-and-grill-me-extension.md) D3.
   - **authority** — `ADR-NNNN D-X`, a URL, or the literal `external`.

   Inline-args form: `/glossary add <term> --definition "..." --category a|b|c --authority "..."`. Missing fields fall back to one-question-at-a-time prompts.

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

### What the add subcommand deliberately does NOT do

- Add multiple terms per invocation — one term per `/glossary add` per [ADR-0007](../../../decisions/0007-vocabulary-glossary-and-grill-me-extension.md) D4. Batch backfills invoke once per term.
- Bypass the critic — `glossary-critic` is the sole authority on entry shape; the step-1 self-checks are fast-path convenience.
- Edit any files other than `CLAUDE.md`. ADR/README/Map-table edits are out of scope.
- Open a PR on round-3 BLOCK — the skill is the gatekeeper; a thrice-blocked entry never reaches `reviewer`.

---

## §Fold flow — bulk auto-fold of skill-local vocabulary

Bulk-fold mechanism for skill-local `## Local vocabulary` sections per [ADR-0014](../../../decisions/0014-skill-local-vocabulary-and-auto-fold.md) D2 (as consolidated by ADR-0038 D3). User-invokable; scans all skills, runs each candidate entry through `glossary-critic`, and proposes APPROVE'd entries to CLAUDE.md via PR.

### Invocation

```
/glossary fold
```

No additional args — scans the entire `.claude/skills/` tree on every invocation.

### Process

1. **Glob** `.claude/skills/*/SKILL.md` for files containing a `## Local vocabulary` H2 section. If none found → report `nothing to fold` and emit `RESULT: SUCCESS` with `ENTRIES_PARSED: 0` and exit (no PR).

2. **Parse entries** from each `## Local vocabulary` section. Each entry follows the canonical CLAUDE.md glossary shape per [ADR-0007](../../../decisions/0007-vocabulary-glossary-and-grill-me-extension.md) D2 (term + one-sentence definition + scope + authority + see-also). Skip malformed entries with a `MALFORMED` note in the report (do not BLOCK the fold on shape — `glossary-critic` will catch).

3. **Per-entry checks (mechanical, pre-critic):**
   - **Duplicate vs CLAUDE.md:** `grep -c "^- \*\*<term>\*\*" CLAUDE.md`. If ≥1 → **SKIPPED (already in CLAUDE.md)**.
   - **Citation threshold (per [ADR-0012](../../../decisions/0012-glossary-consolidation-single-tier.md) D2):** count `<term>` occurrences across `decisions/`, `.claude/agents/`, `.claude/skills/` (use `grep -rc` per directory). If total < 3 OR present in < 2 of the 3 directories → **DEFERRED (below threshold: <count> citations across <dir-count> dirs)**.

4. **Invoke `glossary-critic`** per surviving entry (via the `Agent` tool with `subagent_type: "glossary-critic"`). Pass the drafted entry inline (single-tier per [ADR-0012](../../../decisions/0012-glossary-consolidation-single-tier.md) D1; no target-zone argument). Accumulate **APPROVE**'d entries; record **BLOCK**'d entries with the critic's CRITIC trailer in the report.

5. **PR step.**
   - If 0 APPROVE'd entries (all SKIPPED/DEFERRED/BLOCK'd) → emit the report to stdout, do NOT open a PR, and emit `RESULT: SUCCESS` with the per-entry counts. Exit.
   - Otherwise, open one PR adding all APPROVE'd entries to CLAUDE.md `## Glossary (key terms)` section in alphabetical position. Branch: `hotfix/glossary-fold-<YYYYMMDD>`. PR body Verification section = the full report (per-skill / per-entry status).

### Report template

```
## /glossary fold report

Skills scanned: <N>
Entries parsed: <M>

| Source skill | Term | Status | Reason |
|---|---|---|---|
| <path/to/SKILL.md> | <term> | APPROVE | critic round <r>/3 |
| <path/to/SKILL.md> | <term> | SKIPPED | already in CLAUDE.md |
| <path/to/SKILL.md> | <term> | DEFERRED | below threshold: <count> citations across <dir-count> dirs |
| <path/to/SKILL.md> | <term> | BLOCK | <one-line critic reason> (round <r>/3) |
| <path/to/SKILL.md> | <term> | MALFORMED | <one-line parse error> |

PR opened: <URL or "none — no APPROVE'd entries">
```

### GENERATOR trailer

Per [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D1c, emit at the END of the run:

```
RESULT: SUCCESS | STOPPED | INVALID_INPUT
REASON: <one sentence — e.g., "K entries APPROVE'd; PR opened" or "nothing to fold" or "all entries SKIPPED/DEFERRED — no PR">
ARTIFACTS: <PR URL if opened; empty otherwise>
ENTRIES_PARSED: <total entries parsed across all skills>
ENTRIES_APPROVED: <count APPROVE'd by glossary-critic>
ENTRIES_SKIPPED: <count SKIPPED (already in CLAUDE.md)>
ENTRIES_DEFERRED: <count DEFERRED (below threshold)>
```

`ENTRIES_PARSED`, `ENTRIES_APPROVED`, `ENTRIES_SKIPPED`, `ENTRIES_DEFERRED` are per-agent extensions for downstream audit. BLOCK'd or MALFORMED counts surface in the report body, not the trailer.

### What the fold subcommand deliberately does NOT do

Per PRD #121 §3 non-goals:

- **No auto-trigger.** No reviewer rule, no merge hook, no scheduled job. User-invoked only per ADR-0014 D5.
- **No retroactive `## Local vocabulary` addition** to existing skills. Opt-in convention per ADR-0014 D1; existing skills are grandfathered indefinitely.
- **No glossary-critic rubric modifications.** Rules 2 (duplicate) + 5 (threshold) already cover this skill's needs per ADR-0014 D3.
- **No `glossary-fold-critic` subagent.** Honors the 6-critic-cap meta-rule per ADR-0008 D7 and ADR-0014 D4.
- **No ADR-0012 modifications beyond D6.** D1-D5 + D7 of ADR-0012 stand unchanged.
- **No subagent-local vocabulary support.** Scoped to `.claude/skills/*/SKILL.md` only per ADR-0014 open-questions; `.claude/agents/*.md` deferred.
- **No new entry-shape schema.** Uses the existing CLAUDE.md glossary format verbatim per ADR-0007 D2.

---

## References

- [ADR-0038](../../../decisions/0038-skill-vs-agent-rule.md) D3 — consolidation decision that merged these two skills.
- [ADR-0007](../../../decisions/0007-vocabulary-glossary-and-grill-me-extension.md) — D2 (entry shape), D3 (scope rule), D4 (add write path, as superseded by ADR-0038 D3), D7 (bootstrap-mode).
- [ADR-0012](../../../decisions/0012-glossary-consolidation-single-tier.md) — D1 (single-tier), D2 (≥3-citation threshold), D4 (5-rule rubric), D5 (~35-entry soft cap).
- [ADR-0014](../../../decisions/0014-skill-local-vocabulary-and-auto-fold.md) — D1 (section convention), D2 (fold skill, as superseded by ADR-0038 D3), D3 (conflict resolution), D4 (no new critic), D5 (no auto-trigger), D6 (bootstrap-mode).
- [ADR-0017](../../../decisions/0017-audit-meta-consolidation.md) — subcommand-consolidation precedent.
- [ADR-0032](../../../decisions/0032-workflow-only-architecture.md) — D1 (single-tier CLAUDE.md INDEX only; separate KB layer retired).
- [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D1c — GENERATOR trailer schema.
- [`.claude/agents/glossary-critic.md`](../../agents/glossary-critic.md) — the critic both subcommands invoke.
- `CLAUDE.md` `## Glossary (key terms)` — the destination for added/folded entries.
