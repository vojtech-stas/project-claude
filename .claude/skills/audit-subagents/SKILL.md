---
name: audit-subagents
description: Periodic mechanical audit of subagent-prompt quality. Scans every file under `.claude/agents/*.md`, classifies each as critic or generator, applies the 10-check `scope`-tagged grep rubric, and emits a single Markdown PASS/FAIL report. No-args invocation; advisory output only (no auto-capture, no PR, no critic gate). Use when you suspect subagent drift, after merging a convention-changing ADR, or on the cadence backlog #47 will eventually define.
---

This skill is the mechanical drift-detector for subagent prompts under `.claude/agents/`. Per [ADR-0011](../../../decisions/0011-subagent-quality-framework.md), it codifies conventions from [ADR-0001](../../../decisions/0001-foundational-design.md) D6, [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D1, [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D8, and [ADR-0009](../../../decisions/0009-discipline-tightening.md) D3/D4 as literal `grep` patterns producing deterministic PASS/FAIL per (subagent, applicable check) pair.

Full role synthesis: [entities/skills/audit-subagents](../../../docs/current/entities/skills/audit-subagents.md). Sibling skill of [`/audit-meta`](../audit-meta/SKILL.md) per [ADR-0017](../../../decisions/0017-audit-meta-consolidation.md) D6 (not an extension — separate domains).

**Ownership rationale** (ADR-0011 D1): skill (not 7th critic — ADR-0008 D7 cap) and not a reviewer rule (PR-time gating misses drift in unchanged files).

**Default conservative.** When a grep pattern is ambiguous (literal string only inside a quoted example), FAIL. Asymmetric-cost: spurious FAIL costs one user-glance; wrong-PASS lets real drift slip past (the #93 failure mode).

---

## Invocation

```
/audit-subagents
```

No arguments per [ADR-0011](../../../decisions/0011-subagent-quality-framework.md) D7. Globs `.claude/agents/*.md`, applies the rubric per file, prints the report to stdout. Does NOT call `gh issue create`, does NOT open a PR, does NOT modify any tracked file.

---

## Process

1. **List subagents.** `Glob` `.claude/agents/*.md`. Non-recursive per [ADR-0011](../../../decisions/0011-subagent-quality-framework.md) D8 — the skill does NOT audit `.claude/skills/audit-subagents/SKILL.md` itself.
2. **Classify each file** per [ADR-0011](../../../decisions/0011-subagent-quality-framework.md) D3: filename ends `-critic.md` OR is exactly `reviewer.md` → critic; else generator.
3. **Apply the rubric** below. Each check declares a `scope:` tag (`all` | `critic` | `generator`). Skip checks whose scope does not match the file's classification. Honor each check's optional `excludes:` allowlist — excluded pairs render `N/A (excluded per rubric)` and are omitted from FAIL enumeration.
4. **Aggregate** into the Markdown report — one H2 per subagent, one row per applicable check (`PASS` / `FAIL` / `N/A (excluded per rubric)` / `—`).
5. **Emit the report to stdout** followed by the canonical [GENERATOR trailer](../../../docs/current/topics/output-shapes.md).

---

## Rubric (10 checks; ADR-0011 D4)

Each criterion's full mechanic + grep pattern + rationale + examples lives in the linked atomic note; this shell carries the ID + scope + one-line trigger only.

- [AS-ALL-1](../../../docs/current/concepts/rules/as-all-1.md) — `scope: all` — frontmatter declares `name` / `description` / `tools` / `model` fields.
- [AS-ALL-2](../../../docs/current/concepts/rules/as-all-2.md) — `scope: all` — "Tool boundaries" section heading present.
- [AS-ALL-3](../../../docs/current/concepts/rules/as-all-3.md) — `scope: all` — cross-link section heading present (References / Related / See also / Cross-refs).
- [AS-ALL-4](../../../docs/current/concepts/rules/as-all-4.md) — `scope: all` — surfacing prose uses `captured`-label NOT `backlog`-label (the #93 drift detector). `excludes: backlog-critic.md`.
- [AS-ALL-5](../../../docs/current/concepts/rules/as-all-5.md) — `scope: all` — "Mandatory reading order" OR "When invoked" section heading present.
- [AS-CRIT-1](../../../docs/current/concepts/rules/as-crit-1.md) — `scope: critic` — Default-BLOCK clause present (`Default conservative` literal).
- [AS-CRIT-2](../../../docs/current/concepts/rules/as-crit-2.md) — `scope: critic` — adversarial mindset block present (`paranoid` OR `Adversarial mindset`). `excludes: backlog-critic.md`.
- [AS-CRIT-3](../../../docs/current/concepts/rules/as-crit-3.md) — `scope: critic` — CRITIC trailer spec present (`VERDICT:` / `REASON:` / `ROUND:` fields).
- [AS-CRIT-4](../../../docs/current/concepts/rules/as-crit-4.md) — `scope: critic` — 5-section verdict template present (Header / Subject of review / Rubric / Findings / Summary).
- [AS-GEN-1](../../../docs/current/concepts/rules/as-gen-1.md) — `scope: generator` — GENERATOR trailer spec present (`RESULT:` / `REASON:` / `ARTIFACTS:` fields).

**Coverage arithmetic** (ADR-0011 D4 at current 6-critic + 2-generator baseline): 5 × 8 + 4 × 6 + 1 × 2 = baseline 66 evaluations; effective 64 after CRIT-2 + ALL-4 exclusions of `backlog-critic.md`.

**Per-check `excludes:` schema.** A check MAY declare `excludes: <comma-separated subagent filenames>`. For excluded pairs the runner renders `N/A (excluded per rubric)` instead of PASS/FAIL and omits the pair from the FAIL enumeration. Each exclusion carries an inline rationale (in the atomic note) citing the authoritative ADR.

---

## Report shape

Print one Markdown H2 per subagent, then a per-file table whose columns are the applicable check IDs. End with a Summary section enumerating every FAIL by `(file, check ID)`. Excluded pairs appear only in the per-subagent table as `N/A (excluded per rubric)`; not in the FAIL list.

Per [ADR-0011](../../../decisions/0011-subagent-quality-framework.md) D5, the report is advisory only — the user reads it and captures real drift findings per CLAUDE.md rule #11 manually. Full report template (with example rows) lives in [entities/skills/audit-subagents](../../../docs/current/entities/skills/audit-subagents.md).

---

## Canonical GENERATOR trailer (ADR-0005 D1c)

```
RESULT: SUCCESS | STOPPED | INVALID_INPUT
REASON: <one sentence — e.g., "audited 8 subagents, 5 FAILs (all ALL-4, duplicates of backlog #93)">
ARTIFACTS: <path to report if persisted, else "stdout">
SUBAGENTS_AUDITED: <integer>
CHECK_EVALUATIONS: <integer; baseline 66, effective 64 with current CRIT-2 + ALL-4 exclusions of backlog-critic.md>
FAIL_COUNT: <integer>
```

`SUBAGENTS_AUDITED` / `CHECK_EVALUATIONS` / `FAIL_COUNT` are per-agent extensions per ADR-0005 D1c. `RESULT: SUCCESS` regardless of FAIL count — the audit ran; FAILs are advisory findings, not runtime failures. `RESULT: STOPPED` for runtime errors (file-read, glob); `RESULT: INVALID_INPUT` if invoked with unexpected positional arguments (the no-args contract per ADR-0011 D7).

---

## Tool boundaries

Allowed: `Read`, `Glob`, `Grep`, `Bash` (for executing the grep patterns above against globbed files).

Forbidden: `Edit`, `Write` (advisory only); `Agent` (no recursive invocation — not a critic, no adversarial pair per ADR-0011 D1); `gh issue create` / `gh pr create` (no auto-capture per ADR-0011 D5).

---

## References

- [ADR-0011](../../../decisions/0011-subagent-quality-framework.md) — D1 (skill ownership), D2 (mechanical-only rubric), D3 (classifier), D4 (the 10 checks), D5 (single Markdown report, no auto-capture), D6 (rubric embedded), D7 (no-args invocation), D8 (bootstrap-mode + non-recursive), D9 (sibling backlog relationships).
- [ADR-0001](../../../decisions/0001-foundational-design.md) D6 — subagent definition (sources AS-ALL-1, AS-ALL-2).
- [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D1a/D1b/D1c — verdict template + CRITIC + GENERATOR trailers (sources AS-CRIT-3, AS-CRIT-4, AS-GEN-1, this skill's own output shape).
- [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7 (6-critic-cap, honored), D8 (surfacing convention — sources AS-ALL-4).
- [ADR-0009](../../../decisions/0009-discipline-tightening.md) D3 (default-BLOCK — sources AS-CRIT-1), D4 (adversarial mindsets — sources AS-CRIT-2).
- [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) — T5 thin-prompt migration; full rule bodies live in `docs/current/concepts/rules/as-*.md`; full skill synthesis in `docs/current/entities/skills/audit-subagents.md`.
- Backlog [#93](https://github.com/vojtech-stas/project-claude/issues/93) — surfacing-convention drift fix that AS-ALL-4 detects.
- Backlog [#47](https://github.com/vojtech-stas/project-claude/issues/47) — future post-PRD audit pipeline; natural consumer of this skill per ADR-0011 D9.
