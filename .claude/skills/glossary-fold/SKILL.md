---
name: glossary-fold
description: Bulk-fold mechanism for skill-local `## Local vocabulary` sections per ADR-0014. User-invokable; scans all skills, runs each candidate entry through glossary-critic, and opens one PR proposing APPROVE'd entries to CLAUDE.md. Sibling to `/glossary-add` (single-entry interactive flow).
tools: Read, Glob, Grep, Bash
---

Bulk-fold mechanism for skill-local `## Local vocabulary` sections per [ADR-0014](../../../decisions/0014-skill-local-vocabulary-and-auto-fold.md) D2. User-invokable; scans all skills, runs each candidate entry through `glossary-critic`, and proposes APPROVE'd entries to CLAUDE.md via PR. Sibling skill to [`/glossary-add`](../glossary-add/SKILL.md) (single-entry interactive flow).

## Invocation

```
/glossary-fold
```

No-args — convention across sibling skills ([`/glossary-add`](../glossary-add/SKILL.md), [`/audit-subagents`](../audit-subagents/SKILL.md), [`/promote-to-backlog`](../promote-to-backlog/SKILL.md)). Scans the entire `.claude/skills/` tree on every invocation.

## Process

1. **Glob** `.claude/skills/*/SKILL.md` for files containing a `## Local vocabulary` H2 section. If none found → report `nothing to fold` and emit `RESULT: SUCCESS` with `ENTRIES_PARSED: 0` and exit (no PR).

2. **Parse entries** from each `## Local vocabulary` section. Each entry follows the canonical CLAUDE.md glossary shape per [ADR-0007](../../../decisions/0007-vocabulary-glossary-and-grill-me-extension.md) D2 (term + one-sentence definition + scope + authority + see-also). Skip malformed entries with a `MALFORMED` note in the report (do not BLOCK the fold on shape — `glossary-critic` will catch).

3. **Per-entry checks (mechanical, pre-critic):**
   - **Duplicate vs CLAUDE.md:** `grep -c "^- \*\*<term>\*\*" CLAUDE.md`. If ≥1 → **SKIPPED (already in CLAUDE.md)**.
   - **Citation threshold (per [ADR-0012](../../../decisions/0012-glossary-consolidation-single-tier.md) D2):** count `<term>` occurrences across `decisions/`, `.claude/agents/`, `.claude/skills/` (use `grep -rc` per directory). If total < 3 OR present in < 2 of the 3 directories → **DEFERRED (below threshold: <count> citations across <dir-count> dirs)**.

4. **Invoke `glossary-critic`** per surviving entry (via the `Agent` tool with `subagent_type: "glossary-critic"`). Pass the drafted entry inline (single-tier per [ADR-0012](../../../decisions/0012-glossary-consolidation-single-tier.md) D1; no target-zone argument). Accumulate **APPROVE**'d entries; record **BLOCK**'d entries with the critic's CRITIC trailer in the report.

5. **PR step.**
   - If 0 APPROVE'd entries (all SKIPPED/DEFERRED/BLOCK'd) → emit the report to stdout, do NOT open a PR, and emit `RESULT: SUCCESS` with the per-entry counts. Exit.
   - Otherwise, open one PR adding all APPROVE'd entries to CLAUDE.md `## Glossary (key terms)` section in alphabetical position. Branch: `hotfix/glossary-fold-<YYYYMMDD>`. PR body Verification section = the full report (per-skill / per-entry status).

## Report template

```
## /glossary-fold report

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

## What this skill deliberately does NOT do

Per PRD #121 §3 non-goals:

- **No auto-trigger.** No reviewer rule, no merge hook, no scheduled job. User-invoked only per ADR-0014 D5.
- **No retroactive `## Local vocabulary` addition** to existing skills. Opt-in convention per ADR-0014 D1; existing skills are grandfathered indefinitely.
- **No glossary-critic rubric modifications.** Rules 2 (duplicate) + 5 (threshold) already cover this skill's needs per ADR-0014 D3.
- **No `/glossary-add` modifications.** They coexist per ADR-0014 D2 (sibling skills).
- **No `glossary-fold-critic` subagent.** Honors the 6-critic-cap meta-rule per ADR-0008 D7 and ADR-0014 D4.
- **No ADR-0012 modifications beyond D6.** D1-D5 + D7 of ADR-0012 stand unchanged.
- **No subagent-local vocabulary support.** Scoped to `.claude/skills/*/SKILL.md` only per ADR-0014 open-questions; `.claude/agents/*.md` deferred.
- **No new entry-shape schema.** Uses the existing CLAUDE.md glossary format verbatim per ADR-0007 D2.

## GENERATOR trailer

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

## References

- [ADR-0014](../../../decisions/0014-skill-local-vocabulary-and-auto-fold.md) — D1 (section convention), D2 (this skill), D3 (conflict resolution), D4 (no new critic), D5 (no auto-trigger), D6 (bootstrap-mode).
- [ADR-0012](../../../decisions/0012-glossary-consolidation-single-tier.md) — D1 (single-tier), D2 (≥3-citation inclusion threshold applied at step 3), D5 (~35-entry soft cap).
- [ADR-0007](../../../decisions/0007-vocabulary-glossary-and-grill-me-extension.md) D2 — entry shape.
- [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7 — 6-critic-cap meta-rule (honored).
- [`.claude/agents/glossary-critic.md`](../../agents/glossary-critic.md) — the critic invoked per entry.
- [`.claude/skills/glossary-add/SKILL.md`](../glossary-add/SKILL.md) — sibling single-entry interactive skill.
- `CLAUDE.md` `## Glossary (key terms)` — the destination for folded entries.
