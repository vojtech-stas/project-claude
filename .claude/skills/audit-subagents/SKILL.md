---
name: audit-subagents
description: Periodic mechanical audit of subagent-prompt quality. Scans every file under `.claude/agents/*.md`, classifies each as critic or generator, applies the 10-check `scope`-tagged grep rubric, and emits a single Markdown PASS/FAIL report. No-args invocation; advisory output only (no auto-capture, no PR, no critic gate). Use when you suspect subagent drift, after merging a convention-changing ADR, or on the cadence backlog #47 will eventually define.
---

This skill is the mechanical drift-detector for subagent prompts under `.claude/agents/`. Per [ADR-0011](../../../decisions/0011-subagent-quality-framework.md), it codifies the conventions established across [ADR-0001](../../../decisions/0001-foundational-design.md) D6, [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D1, [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D8, and [ADR-0009](../../../decisions/0009-discipline-tightening.md) D3/D4 as literal `grep` patterns producing deterministic PASS/FAIL per (subagent, applicable check) pair.

**Ownership choice rationale** (per ADR-0011 D1): a skill, not a 7th critic, because the [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7 6-critic-cap meta-rule blocks a `subagent-critic`; a skill, not a reviewer rule, because PR-time gating misses drift in unchanged files (the exact failure mode of the 2026-05-19 stale-worktree audit that motivated this).

**Default conservative.** When a grep pattern is ambiguous against the file content (e.g., the literal string appears only inside a quoted example or commented-out block), FAIL. Asymmetric-cost rationale (same as [ADR-0009](../../../decisions/0009-discipline-tightening.md) D3 generalized to advisory audits): a spurious FAIL costs one user-glance round; a wrong-PASS lets a real drift slip past undetected.

## Invocation

```
/audit-subagents
```

No arguments. The skill globs `.claude/agents/*.md`, applies the rubric per file, and prints the report to stdout. Does NOT call `gh issue create`, does NOT open a PR, does NOT modify any tracked file.

## Process

1. **List subagents.** `Glob` for `.claude/agents/*.md` (relative to repo root). Per ADR-0011 D7, this excludes `.claude/skills/audit-subagents/SKILL.md` itself — non-recursive audit pattern per [ADR-0011](../../../decisions/0011-subagent-quality-framework.md) D8.

2. **Classify each file** per ADR-0011 D3 (locked classifier): filename ends `-critic.md` OR is exactly `reviewer.md` → critic; else generator. Current main: `reviewer.md`, `prd-critic.md`, `adr-critic.md`, `slicer-critic.md`, `glossary-critic.md`, `backlog-critic.md` → critic (6); `slicer.md`, `implementer.md` → generator (2).

3. **Apply the rubric** below. Each check declares a `scope:` tag (`all` | `critic` | `generator`) and a literal `grep` pattern. Skip checks whose scope does not match the file's classification.

4. **Aggregate.** Build the Markdown report per the report template below — one table row per subagent, one column per applicable check (`PASS` / `FAIL` / `—` for not-applicable).

5. **Emit the report to stdout** followed by the canonical GENERATOR trailer.

## Rubric (10 checks; ADR-0011 D4)

Each entry: `ID | scope | check | literal grep pattern`. The grep pattern is what the skill executes (case-sensitive, extended-regex where `-E` is shown). When a pattern fails to match in the target file → FAIL for that check; when it matches → PASS.

- **ALL-1** — `scope: all` — Frontmatter present (`name`, `description`, `tools`, `model` fields in the leading YAML block).
  Pattern: `grep -cE "^(name|description|tools|model):" <file>` ≥ `4` → PASS. Source: ADR-0001 D6.

- **ALL-2** — `scope: all` — "Tool boundaries" section heading present.
  Pattern: `grep -cE "^#+\s*Tool boundaries" <file>` ≥ `1` → PASS. Source: ADR-0001 D6.

- **ALL-3** — `scope: all` — "References" section heading present.
  Pattern: `grep -cE "^#+\s*References" <file>` ≥ `1` → PASS. Source: convention across 8 subagents.

- **ALL-4** — `scope: all` — Surfacing-convention prose uses `captured`-label, NOT `backlog`-label (the #93 drift detector).
  Pattern: file contains the surfacing-drift idiom — either ``\`backlog\`-labeled`` prose or `--label backlog` literal → FAIL (drift detected); absent → PASS. Equivalently: ``grep -cE "(\\\`backlog\\\`-labeled|--label backlog)" <file>`` == `0` → PASS. Source: ADR-0008 D8 + ADR-0009 D2. (Default-conservative per skill prompt: if a match appears anywhere in the file — including inside example/quoted blocks — FAIL; the cost of a spurious FAIL is one user-glance; the cost of a missed real drift is the #93 failure mode itself.)

- **ALL-5** — `scope: all` — "Mandatory reading order" OR "When invoked" section heading present.
  Pattern: `grep -cE "^#+\s*(Mandatory reading order|When invoked)" <file>` ≥ `1` → PASS. Source: convention across 8 subagents.

- **CRIT-1** — `scope: critic` — Default-BLOCK clause present (literal "Default conservative" string).
  Pattern: `grep -cF "Default conservative" <file>` ≥ `1` → PASS. Source: ADR-0009 D3.

- **CRIT-2** — `scope: critic` — Adversarial mindset block present ("paranoid" OR "Adversarial mindset" literal string).
  Pattern: `grep -cE "(paranoid|Adversarial mindset)" <file>` ≥ `1` → PASS. Source: ADR-0009 D4.

- **CRIT-3** — `scope: critic` — CRITIC trailer spec present (`VERDICT:`, `REASON:`, `ROUND:` fields in a fenced block).
  Pattern: all three of `grep -cF "VERDICT:" <file>` ≥ `1` AND `grep -cF "REASON:" <file>` ≥ `1` AND `grep -cF "ROUND:" <file>` ≥ `1` → PASS. Source: ADR-0005 D1b.

- **CRIT-4** — `scope: critic` — 5-section verdict template present (Header → Subject of review → Rubric → Findings → Summary headings).
  Pattern: all five of `grep -cF "Subject of review" <file>` ≥ `1` AND `grep -cE "^#+\s*Rubric" <file>` ≥ `1` AND `grep -cE "^#+\s*Findings" <file>` ≥ `1` AND `grep -cE "^#+\s*Summary" <file>` ≥ `1` AND `grep -cE "verdict:" <file>` ≥ `1` → PASS. Source: ADR-0005 D1a.

- **GEN-1** — `scope: generator` — GENERATOR trailer spec present (`RESULT:`, `REASON:`, `ARTIFACTS:` fields in a fenced block).
  Pattern: all three of `grep -cF "RESULT:" <file>` ≥ `1` AND `grep -cF "REASON:" <file>` ≥ `1` AND `grep -cF "ARTIFACTS:" <file>` ≥ `1` → PASS. Source: ADR-0005 D1c.

**Coverage arithmetic** (per ADR-0011 D4): 5 scope-`all` × 8 subagents + 4 scope-`critic` × 6 critics + 1 scope-`generator` × 2 generators = 40 + 24 + 2 = **66 check evaluations** per audit run.

## Report template

Print one Markdown H2 per subagent, then a per-file table whose columns are exactly the applicable check IDs. Use `PASS` / `FAIL` / `—` (em-dash for not-applicable). End with a Summary section enumerating every FAIL by `(file, check ID)`.

```
# /audit-subagents report — <YYYY-MM-DD>

## reviewer.md (critic)

| ALL-1 | ALL-2 | ALL-3 | ALL-4 | ALL-5 | CRIT-1 | CRIT-2 | CRIT-3 | CRIT-4 | GEN-1 |
|---|---|---|---|---|---|---|---|---|---|
| PASS | PASS | PASS | FAIL | PASS | PASS | PASS | PASS | PASS | — |

## slicer.md (generator)

| ALL-1 | ALL-2 | ALL-3 | ALL-4 | ALL-5 | CRIT-1 | CRIT-2 | CRIT-3 | CRIT-4 | GEN-1 |
|---|---|---|---|---|---|---|---|---|---|
| PASS | PASS | PASS | FAIL | PASS | — | — | — | — | PASS |

... (one section per subagent) ...

## Summary

- Total subagents audited: <N>
- Total check evaluations: 66 (5 all × N_all + 4 critic × N_critic + 1 generator × N_generator)
- FAILs:
  - `slicer.md` ALL-4
  - `adr-critic.md` ALL-4
  - ... (one bullet per FAIL)
- Capture status of each FAIL: cross-reference to existing `gh issue list --label captured` / `--label backlog` results so the user can spot duplicates of known drift (e.g., backlog #93 owns the captured-vs-backlog drift family).
```

The Summary cross-reference is advisory — the skill does NOT call `gh issue create`. Per [ADR-0011](../../../decisions/0011-subagent-quality-framework.md) D5, the user reviews the report and captures real follow-ups per CLAUDE.md rule #11 manually.

## Canonical GENERATOR trailer (ADR-0005 D1c)

The skill emits the report body above, then this trailer as a fenced code block:

```
RESULT: SUCCESS | STOPPED | INVALID_INPUT
REASON: <one sentence — e.g., "audited 8 subagents, 5 FAILs (all ALL-4, duplicates of backlog #93)">
ARTIFACTS: <path to report if persisted, else "stdout">
SUBAGENTS_AUDITED: <integer>
CHECK_EVALUATIONS: <integer; expected 66 at slice-1 baseline>
FAIL_COUNT: <integer>
```

`SUBAGENTS_AUDITED`, `CHECK_EVALUATIONS`, and `FAIL_COUNT` are per-agent extensions to the canonical trailer per ADR-0005 D1c, named here so downstream consumers (a future post-PRD-audit skill per backlog #47) can parse without re-reading the report.

`RESULT: SUCCESS` regardless of FAIL count — the audit ran to completion; FAILs are advisory findings, not skill-runtime failures. `RESULT: STOPPED` is reserved for runtime failures (file read errors, glob errors). `RESULT: INVALID_INPUT` is reserved if the skill is invoked with unexpected positional arguments (the no-args contract per ADR-0011 D7).

## Tool boundaries

Allowed: `Read`, `Glob`, `Grep`, `Bash` (for executing the grep patterns above against globbed files).

Forbidden: `Edit`, `Write` (the skill emits a report to stdout; it does NOT modify tracked files); `Agent` (no recursive subagent invocation — the skill is not a critic and has no adversarial pair per ADR-0011 D1); `gh issue create` / `gh pr create` (no auto-capture per ADR-0011 D5; no PR opening — this is a read-only audit).

## What this skill deliberately does NOT do

- Does NOT audit `.claude/skills/*.md` — out of scope per ADR-0011 D8 (non-recursive audit pattern; the skill is a subagent-shaped artifact but is NOT itself a subagent under `.claude/agents/`).
- Does NOT auto-capture FAIL findings as `captured`-labeled issues — deferred per ADR-0011 D5. The slice-1 dogfood is expected to produce ~5 ALL-4 FAILs that mostly duplicate backlog #93; auto-capturing them would force `backlog-critic` to BLOCK duplicates (correct, but noisy).
- Does NOT run a ≤3-round critic loop — this skill is a GENERATOR per ADR-0005 D1c, not a critic; there is no APPROVE/BLOCK verdict.
- Does NOT block PRs that touch `.claude/agents/*.md` — a future `R-SUBAGENT-QUALITY` reviewer rule is explicitly deferred per ADR-0011 D8 future-direction; would require its own bootstrap-mode policy.
- Does NOT apply semantic / LLM judgment — checks are pure mechanical grep per ADR-0011 D2. Catching a mindset block that is "actually a personality novel rather than a scrutiny lens" requires LLM-semantic checks, deferred to a future PRD.
- Does NOT take a `<name>` argument for single-subagent targeting — bulk-audit is the primary use case per ADR-0011 D7; two code paths would inflate slice-1 LoC.

## References

- [ADR-0011](../../../decisions/0011-subagent-quality-framework.md) — D1 (skill ownership), D2 (mechanical-only rubric), D3 (classifier rule), D4 (the 10 checks), D5 (single Markdown report, no auto-capture), D6 (rubric embedded in SKILL.md), D7 (no-args invocation), D8 (bootstrap-mode + non-recursive), D9 (sibling backlog relationships).
- [ADR-0001](../../../decisions/0001-foundational-design.md) D6 — subagent definition; sources ALL-1 and ALL-2.
- [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D1a (5-section verdict — CRIT-4), D1b (CRITIC trailer — CRIT-3), D1c (GENERATOR trailer — GEN-1 + this skill's own output shape).
- [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7 (6-critic-cap, honored by skill-ownership), D8 (captured-tier surfacing — sources ALL-4).
- [ADR-0009](../../../decisions/0009-discipline-tightening.md) D3 (default-BLOCK — sources CRIT-1), D4 (adversarial mindsets — sources CRIT-2).
- Backlog [#93](https://github.com/vojtech-stas/project-claude/issues/93) — the surfacing-convention drift fix that ALL-4 mechanically detects.
- Backlog [#47](https://github.com/vojtech-stas/project-claude/issues/47) — future post-PRD audit pipeline; natural consumer of this skill per ADR-0011 D9.
