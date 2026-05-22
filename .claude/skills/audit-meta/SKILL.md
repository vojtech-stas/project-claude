---
name: audit-meta
description: Periodic mechanical audit of codebase structure + doc-currency. Subcommand architecture — `/audit-meta` (no-args = both), `/audit-meta --structure`, `/audit-meta --docs`. Sibling skill to /audit-subagents per ADR-0017. Mechanical/grep-only rubric; emits a single Markdown PASS/FAIL report. Advisory output only (no auto-capture, no PR, no critic gate). Use when you suspect structural bloat or doc drift, after merging a convention-changing ADR, or on the cadence backlog #47 will eventually define.
---

This skill is the mechanical drift-detector for **codebase structure** (file counts, file sizes, naming) and **documentation currency** (dangling refs, stale convention text) under the repo root. Per [ADR-0017](../../../decisions/0017-audit-meta-consolidation.md), it consolidates backlog #129 (structure) and #130 (docs) under one skill with subcommand architecture, sibling to `/audit-subagents` (ADR-0011) — not an extension.

**Ownership choice rationale** (per ADR-0017 D6 + ADR-0011 D1): a skill, not a 7th critic, because [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7 caps critics at 6; sibling to `/audit-subagents` (not an extension) because three-domain mega-rubric violates single-responsibility shape (Q2 alternatives 2C/2D rejected).

**Default conservative.** When a grep pattern is ambiguous against file content (e.g., a forbidden literal appears inside a quoted example block), FAIL. Asymmetric-cost rationale: a spurious FAIL costs one user-glance round; a wrong-PASS lets real drift slip undetected. Mirrors `/audit-subagents` per ADR-0011 D2 precedent.

## Invocation

- `/audit-meta` (no args) — runs ALL subcommands; emits a single combined report with subcommand subsections
- `/audit-meta --structure` — runs structure-audit only
- `/audit-meta --docs` — runs docs-currency-audit only

## Argument parsing

Shell-style switch (~15-20 LoC); the skill body sets two boolean flags from `$ARGS`:

```bash
RUN_STRUCT=0
RUN_DOCS=0
if [[ -z "$ARGS" ]]; then
  RUN_STRUCT=1; RUN_DOCS=1
else
  [[ "$ARGS" == *"--structure"* ]] && RUN_STRUCT=1
  [[ "$ARGS" == *"--docs"* ]] && RUN_DOCS=1
  if [[ $RUN_STRUCT -eq 0 && $RUN_DOCS -eq 0 ]]; then
    echo "RESULT: INVALID_INPUT"; exit 1
  fi
fi
```

Per ADR-0017 D1, only three valid invocations exist; anything else is `RESULT: INVALID_INPUT`.

## Process

1. **Parse args** (above) — set `RUN_STRUCT` / `RUN_DOCS` flags.
2. **If `RUN_STRUCT=1`** — iterate STRUCT-1..10; each check fires its literal grep / file-count / Glob pattern; record PASS / FAIL / WARN.
3. **If `RUN_DOCS=1`** — iterate DOCS-1..10; each check fires its literal pattern; record PASS / FAIL.
4. **Aggregate** the Markdown report per the report template below — one subsection per active subcommand, one row per check.
5. **Emit the report to stdout** followed by the canonical GENERATOR trailer.

## Structure rubric (10 checks; ADR-0017 D2)

Each check declares `subcommand: structure`. Skip all if `RUN_STRUCT=0`. Pattern is the literal command the skill runs; result column states PASS criterion.

- **STRUCT-1** — `subcommand: structure` — `.claude/agents/` file count ≤ 12 (ADR-0008 D7 6-critic-cap headroom).
  Pattern: `ls .claude/agents/*.md | wc -l` ≤ `12` → PASS; `13..15` → WARN; `>15` → FAIL.

- **STRUCT-2** — `subcommand: structure` — `.claude/skills/` direct-child directory count ≤ 16 (cap bumped from 12 to accommodate ADR-0022 D3+D8 best-practice sibling skills B/C/E/F; see #184).
  Pattern: `ls -d .claude/skills/*/ | wc -l` ≤ `16` → PASS; `17..19` → WARN; `>19` → FAIL.

- **STRUCT-3** — `subcommand: structure` — no markdown file > 500 LoC (split-candidate detector).
  Pattern: `find . -name "*.md" -not -path "./.git/*" -exec wc -l {} \; | awk '$1 > 500'` → empty → PASS; non-empty → WARN (list offenders).

- **STRUCT-4** — `subcommand: structure` — no directory depth > 4 (nesting-bloat detector, relative to repo root, excluding `.git/`).
  Pattern: `find . -type d -not -path "./.git*" | awk -F/ 'NF-1 > 5'` → empty → PASS; non-empty → FAIL.

- **STRUCT-5** — `subcommand: structure` — `decisions/` ADR count ≤ 20 (informational; flags consolidation candidate when high).
  Pattern: `ls decisions/[0-9]*.md | wc -l` ≤ `20` → PASS; `21..25` → WARN; `>25` → FAIL.

- **STRUCT-6** — `subcommand: structure` — every file under `.claude/agents/*.md` matches naming pattern `[a-z-]+(-critic)?\.md`.
  Pattern: `ls .claude/agents/ | grep -vE '^[a-z-]+\.md$'` → empty → PASS; non-empty → FAIL (list offenders).

- **STRUCT-7** — `subcommand: structure` — every `.claude/skills/*/` directory contains exactly one `SKILL.md` and no other `.md` files at that depth (single-SKILL.md convention).
  Pattern: `find .claude/skills -mindepth 2 -maxdepth 2 -name "*.md" -not -name "SKILL.md"` → empty → PASS; non-empty → FAIL.

- **STRUCT-8** — `subcommand: structure` — every `decisions/NNNN-*.md` matches `NNNN-<kebab-slug>.md` pattern.
  Pattern: `ls decisions/ | grep -E '\.md$' | grep -vE '^[0-9]{4}-[a-z0-9-]+\.md$|^README\.md$'` → empty → PASS; non-empty → FAIL.

- **STRUCT-9** — `subcommand: structure` — root `README.md` exists and is non-empty.
  Pattern: `test -s README.md` → PASS; else FAIL.

- **STRUCT-10** — `subcommand: structure` — root `CLAUDE.md` exists and is non-empty.
  Pattern: `test -s CLAUDE.md` → PASS; else FAIL.

## Docs-currency rubric (10 checks; ADR-0017 D3)

Each check declares `subcommand: docs`. Skip all if `RUN_DOCS=0`.

- **DOCS-1** — `subcommand: docs` — every `decisions/NNNN-*.md` link referenced in `decisions/README.md` resolves to an existing file (no dangling index rows).
  Pattern: extract every `(NNNN-[a-z0-9-]+\.md)` from `decisions/README.md`; for each, `test -f decisions/<m>` → all PASS → PASS; any missing → FAIL (list).

- **DOCS-2** — `subcommand: docs` — every `decisions/NNNN-*.md` on disk has a row in `decisions/README.md` (no missing index entries).
  Pattern: `for f in decisions/[0-9]*.md; do grep -qF "$(basename $f)" decisions/README.md || echo MISSING $f; done` → empty → PASS; non-empty → FAIL.

- **DOCS-3** — `subcommand: docs` — every `.claude/agents/*.md` referenced in `CLAUDE.md` Map exists (no dangling Map rows).
  Pattern: extract `\.claude/agents/[a-z-]+\.md` references from `CLAUDE.md`; for each, `test -f` → all PASS → PASS; any missing → FAIL.

- **DOCS-4** — `subcommand: docs` — every `.claude/skills/*/SKILL.md` referenced in `CLAUDE.md` Map exists.
  Pattern: extract `\.claude/skills/[a-z-]+/SKILL\.md` references from `CLAUDE.md`; for each, `test -f` → all PASS → PASS; any missing → FAIL.

- **DOCS-5** — `subcommand: docs` — no `N=3` literal references in `README.md` (post-ADR-0013 drift detector; PR #125 fix).
  Pattern: `grep -cF "N=3" README.md` == `0` → PASS; ≥ `1` → FAIL.

- **DOCS-6** — `subcommand: docs` — no `GLOSSARY.md` references anywhere in `*.md` files (post-ADR-0012; file was deleted).
  Pattern: `grep -rlF "GLOSSARY.md" --include="*.md" . | grep -v "^./.git/"` → empty → PASS; non-empty → FAIL.

- **DOCS-7** — `subcommand: docs` — every ADR cited as `[ADR-NNNN](decisions/NNNN-*.md)` in any tracked `.md` resolves to an existing file.
  Pattern: extract every `decisions/[0-9]{4}-[a-z0-9-]+\.md` link target; for each, `test -f` → all PASS → PASS; any missing → FAIL (list).

- **DOCS-8** — `subcommand: docs` — `decisions/README.md` Status column has explicit "superseded by ADR-NNNN" notes for every ADR whose D-IDs carry supersession headers. Pattern: enumerate `Supersedes:` headers across `decisions/*.md`; for each superseded D-ID, grep the Status column for `superseded by` → all PASS → PASS; any missing → WARN.

- **DOCS-9** — `subcommand: docs` — `CLAUDE.md` glossary section entry count ≤ 35 (per ADR-0012 D5 cap).
  Pattern: count top-level glossary bullets in `CLAUDE.md` `## Glossary` section: `awk '/^## Glossary/,/^## /' CLAUDE.md | grep -cE '^- \*\*'` ≤ `35` → PASS; > `35` → WARN.

- **DOCS-10** — `subcommand: docs` — no `backlog`-label surfacing instructions remain in subagent / skill files (per PR #105 + PR #107 drift detector).
  Pattern: `grep -rE '(\`backlog\`-labeled|--label backlog)' .claude/agents .claude/skills` → empty → PASS; non-empty → FAIL (with `backlog-critic.md` allowlisted per ADR-0011 ALL-4 precedent).

## Report template

Single Markdown report; subsections per active subcommand. Use one of three rendering tokens per check: `PASS` / `FAIL` / `WARN` (plus inline `details:` listing offenders for non-PASS rows).

```
# /audit-meta report — <YYYY-MM-DD>

Invocation: `/audit-meta [--structure] [--docs]`
Subcommands run: structure, docs

## Structure findings

| Check | Result | Details |
|---|---|---|
| STRUCT-1 | PASS | .claude/agents/ count = 8 (≤ 12) |
| STRUCT-2 | PASS | .claude/skills/ count = 14 (≤ 16) |
| STRUCT-3 | WARN | 3 files > 500 LoC: decisions/0003-*.md (612), ... |
| STRUCT-4 | PASS | max depth = 4 |
| ... | ... | ... |

## Docs findings

| Check | Result | Details |
|---|---|---|
| DOCS-1 | PASS | all 15 ADR refs resolve |
| DOCS-5 | PASS | no N=3 literal in README.md |
| DOCS-10 | PASS | no backlog-label surfacing drift |
| ... | ... | ... |

## Summary

- Subcommands run: <list>
- Total checks evaluated: <int>
- PASS / WARN / FAIL counts: <int> / <int> / <int>
- FAILs: enumerated as `(subcommand, check ID, file:line)` for the user to triage manually per CLAUDE.md rule #11.
```

End with the canonical GENERATOR trailer (below). Per ADR-0017 D4 + ADR-0011 D5 precedent, the report is advisory; the skill does NOT call `gh issue create`.

## Canonical GENERATOR trailer (ADR-0005 D1c)

```
RESULT: SUCCESS | STOPPED | INVALID_INPUT
REASON: <one sentence — e.g., "audit-meta ran structure + docs; 18 PASS, 2 WARN, 0 FAIL">
ARTIFACTS: <path to report if persisted, else "stdout">
SUBCOMMANDS_RUN: structure,docs | structure | docs
CHECKS_EVALUATED: <integer>
PASS_COUNT: <integer>
WARN_COUNT: <integer>
FAIL_COUNT: <integer>
```

`SUBCOMMANDS_RUN`, `CHECKS_EVALUATED`, `PASS_COUNT`, `WARN_COUNT`, `FAIL_COUNT` are per-agent extensions to the canonical trailer per ADR-0005 D1c, named here so downstream consumers (a future post-PRD-audit skill per backlog #47) can parse without re-reading the report.

`RESULT: SUCCESS` regardless of WARN/FAIL count — the audit ran to completion; non-PASS rows are advisory findings, not skill-runtime failures. `RESULT: STOPPED` is reserved for runtime failures (file-read errors, glob errors). `RESULT: INVALID_INPUT` is reserved if invoked with unexpected positional arguments (only the three modes from ADR-0017 D1 are valid).

## Tool boundaries

Allowed: `Read`, `Glob`, `Grep`, `Bash` (for executing the grep / `wc` / `find` patterns above).

Forbidden: `Edit`, `Write` (the skill emits a report to stdout; it does NOT modify tracked files); `Agent` (no recursive subagent invocation — this skill is not a critic and has no adversarial pair per ADR-0017 D6); `gh issue create` / `gh pr create` (no auto-capture per ADR-0017 D4 + ADR-0011 D5; no PR opening — this is a read-only audit).

## What this skill deliberately does NOT do

- Does NOT audit subagent prompts — that's `/audit-subagents`'s job (ADR-0011). The two skills are siblings (ADR-0017 D6).
- Does NOT auto-fire on a cadence (post-PRD-merge hook, cron, etc.) — deferred per ADR-0017 D7 (cadence-PRD future work, source-of-truth backlog #47).
- Does NOT enforce a boy-scout reviewer rule — deferred per ADR-0017 D7 (boy-scout-PRD future work).
- Does NOT auto-fix findings — strictly advisory per ADR-0011 D5 precedent.
- Does NOT auto-capture findings as `captured`-labeled issues — user-driven follow-up per CLAUDE.md rule #11.
- Does NOT apply semantic / LLM checks — pure mechanical grep per ADR-0011 D2 precedent (rejected Alt-E in ADR-0017).
- Does NOT block PRs that touch structure or docs — no reviewer-rule extension here (deferred to boy-scout PRD).

## References

- [ADR-0017](../../../decisions/0017-audit-meta-consolidation.md) — D1 (subcommand architecture), D2 (structure rubric), D3 (docs rubric), D4 (report shape), D5 (bootstrap-mode), D6 (sibling-not-extension), D7 (deferred-cadence + boy-scout).
- [ADR-0011](../../../decisions/0011-subagent-quality-framework.md) — D1 (skill ownership), D2 (mechanical-only), D5 (no auto-capture), D6 (rubric embedded), D7 (no-args default — extended here). The precedent template this SKILL.md mirrors.
- [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D1c — GENERATOR trailer shape.
- [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7 — 6-critic-cap (honored; this is a skill, not a critic). D8 surfacing convention (drift detector DOCS-10).
- [ADR-0012](../../../decisions/0012-glossary-consolidation-single-tier.md) D5 — ~35-entry glossary cap (DOCS-9 enforces).
- [ADR-0013](../../../decisions/0013-slicer-n3-contract-refined.md) — N=3 default convention (DOCS-5 enforces no stale `N=3` in README).
- Backlog [#129](https://github.com/vojtech-stas/project-claude/issues/129) — structure auditor (consolidated as `--structure`).
- Backlog [#130](https://github.com/vojtech-stas/project-claude/issues/130) — doc-currency auditor (consolidated as `--docs`).
- Backlog [#47](https://github.com/vojtech-stas/project-claude/issues/47) — future cadence + boy-scout PRDs per ADR-0017 D7.
- `.claude/skills/audit-subagents/SKILL.md` — sibling skill (preserved unchanged per ADR-0017 D6).
