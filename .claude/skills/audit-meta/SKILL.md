---
name: audit-meta
description: Periodic mechanical audit of codebase structure + doc-currency. Subcommand architecture — `/audit-meta` (no-args = both), `/audit-meta --structure`, `/audit-meta --docs`. Sibling skill to /audit-subagents per ADR-0017. Mechanical/grep-only rubric; emits a single Markdown PASS/WARN/FAIL report. Advisory output only (no auto-capture, no PR, no critic gate). Use when you suspect structural bloat or doc drift, after merging a convention-changing ADR, or on the cadence backlog #47 will eventually define.
---

This skill is the mechanical drift-detector for **codebase structure** (file counts, file sizes, naming) and **documentation currency** (dangling refs, stale convention text) under the repo root. Per [ADR-0017](../../../decisions/0017-audit-meta-consolidation.md), it consolidates backlog #129 (structure) and #130 (docs) under one skill with subcommand architecture, sibling to [`/audit-subagents`](../audit-subagents/SKILL.md) per ADR-0017 D6 ([ADR-0011](../../../decisions/0011-subagent-quality-framework.md) precedent). Full role synthesis: [entities/skills/audit-meta](../../../docs/current/entities/skills/audit-meta.md).

**Ownership rationale** (ADR-0017 D6 + ADR-0011 D1): skill not 7th critic (ADR-0008 D7 cap); sibling not extension (three-domain mega-rubric violates single-responsibility).

**Default conservative.** When a grep pattern is ambiguous (forbidden literal inside a quoted example), FAIL. Asymmetric-cost: spurious FAIL costs one user-glance; wrong-PASS lets real drift slip past. Mirrors `/audit-subagents` per ADR-0011 D2 precedent.

---

## Invocation

- `/audit-meta` (no args) — runs ALL subcommands; combined report.
- `/audit-meta --structure` — structure-audit only.
- `/audit-meta --docs` — docs-currency-audit only.

Any other arguments → `RESULT: INVALID_INPUT` per [ADR-0017](../../../decisions/0017-audit-meta-consolidation.md) D1.

Argument-parsing logic (shell-style switch): set `RUN_STRUCT` / `RUN_DOCS` flags from `$ARGS` — no args sets both; `--structure` / `--docs` set one each; neither match → `RESULT: INVALID_INPUT`. Full parser snippet in [entities/skills/audit-meta](../../../docs/current/entities/skills/audit-meta.md).

---

## Process

1. **Parse args** — set `RUN_STRUCT` / `RUN_DOCS` flags (above).
2. **If `RUN_STRUCT=1`** — iterate AM-STRUCT-* rule atoms; each check fires its literal grep / `wc` / Glob pattern; record PASS / WARN / FAIL.
3. **If `RUN_DOCS=1`** — iterate AM-DOCS-* rule atoms; each check fires its literal pattern; record PASS / WARN / FAIL.
4. **Aggregate** the Markdown report — one subsection per active subcommand, one row per check (`PASS` / `WARN` / `FAIL` plus inline `details:` for non-PASS rows).
5. **Emit the report to stdout** followed by the canonical [GENERATOR trailer](../../../docs/current/topics/output-shapes.md).

---

## Rubric (20 checks → 11 atoms; ADR-0017 D2 + D3)

Each criterion's full mechanic + literal pattern + rationale + examples lives in the linked atomic note; this shell carries the ID + subcommand + one-line trigger only.

**Structure rubric** (`subcommand: structure`; skip if `RUN_STRUCT=0`):

- [AM-STRUCT-COUNTS](../../../docs/current/concepts/rules/am-struct-counts.md) — covers STRUCT-1/2/5 — directory cardinality caps for `.claude/agents/` (≤12), `.claude/skills/` (≤16), `decisions/` (≤20).
- [AM-STRUCT-SIZES](../../../docs/current/concepts/rules/am-struct-sizes.md) — covers STRUCT-3/4 — no markdown file > 500 LoC; no directory depth > 4.
- [AM-STRUCT-NAMING](../../../docs/current/concepts/rules/am-struct-naming.md) — covers STRUCT-6/7/8 — naming + single-SKILL.md invariants across agents/skills/decisions.
- [AM-STRUCT-ROOT-FILES](../../../docs/current/concepts/rules/am-struct-root-files.md) — covers STRUCT-9/10 — root `README.md` + `CLAUDE.md` exist and non-empty.

**Docs-currency rubric** (`subcommand: docs`; skip if `RUN_DOCS=0`):

- [AM-DOCS-ADR-INDEX](../../../docs/current/concepts/rules/am-docs-adr-index.md) — covers DOCS-1/2 — bidirectional sync between `decisions/README.md` index and on-disk `decisions/NNNN-*.md` files.
- [AM-DOCS-CLAUDE-MD-MAP](../../../docs/current/concepts/rules/am-docs-claude-md-map.md) — covers DOCS-3/4 — every `.claude/agents/*.md` and `.claude/skills/*/SKILL.md` ref in `CLAUDE.md` Map resolves.
- [AM-DOCS-LITERAL-DRIFT](../../../docs/current/concepts/rules/am-docs-literal-drift.md) — covers DOCS-5/6 — no `N=3` in README lacking ADR-0013 proximity (±2-line check); no `GLOSSARY.md` refs outside 5-file allowlist + `decisions/*` wholesale allowlist (post-ADR-0012).
- [AM-DOCS-ADR-CITATIONS](../../../docs/current/concepts/rules/am-docs-adr-citations.md) — DOCS-7 — every `[ADR-NNNN](decisions/NNNN-*.md)` citation resolves; fake-example slugs (`old-name`, `fictional`, `fictional-adr`, `new-adr`, `new-decision`) allowlisted by slug-shape regex.
- [AM-DOCS-SUPERSESSION-NOTES](../../../docs/current/concepts/rules/am-docs-supersession-notes.md) — DOCS-8 — `decisions/README.md` Status column carries supersession annotations; mechanic uses `grep -nE '^- \*\*Supersedes:\*\*'` matching actual ADR line-prefix format (WARN not FAIL).
- [AM-DOCS-GLOSSARY-CAP](../../../docs/current/concepts/rules/am-docs-glossary-cap.md) — DOCS-9 — `CLAUDE.md` glossary entry count ≤ 35 (ADR-0012 D5 cap); awk state-flag pattern `{f=1; next}` avoids false-start on `## Glossary (key terms)` heading (WARN not FAIL).
- [AM-DOCS-BACKLOG-SURFACING](../../../docs/current/concepts/rules/am-docs-backlog-surfacing.md) — DOCS-10 — no `backlog`-label surfacing in subagent/skill files; `backlog-critic.md` + `promote-to-backlog/SKILL.md` allowlisted as legitimate carriers.

---

## Report shape

Single Markdown report with one subsection per active subcommand and a per-check table (`Check | Result | Details`). End with a Summary section (subcommands run / total checks / PASS-WARN-FAIL counts / FAIL enumeration). Per [ADR-0017](../../../decisions/0017-audit-meta-consolidation.md) D4 + [ADR-0011](../../../decisions/0011-subagent-quality-framework.md) D5, the report is advisory — user captures real findings per CLAUDE.md rule #11. Full template lives in [entities/skills/audit-meta](../../../docs/current/entities/skills/audit-meta.md).

---

## Canonical [GENERATOR trailer](../../../docs/current/topics/output-shapes.md) (ADR-0005 D1c)

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

`SUBCOMMANDS_RUN` / `CHECKS_EVALUATED` / `PASS_COUNT` / `WARN_COUNT` / `FAIL_COUNT` are per-agent extensions per ADR-0005 D1c. `RESULT: SUCCESS` regardless of WARN/FAIL count — the audit ran; non-PASS rows are advisory findings. `RESULT: STOPPED` for runtime errors; `RESULT: INVALID_INPUT` if invoked with unexpected positional arguments (only three modes from ADR-0017 D1 are valid).

---

## Tool boundaries

Allowed: `Read`, `Glob`, `Grep`, `Bash` (for executing grep / `wc` / `find` patterns).

Forbidden: `Edit`, `Write` (advisory only); `Agent` (no recursive invocation — not a critic, no adversarial pair per ADR-0017 D6); `gh issue create` / `gh pr create` (no auto-capture per ADR-0017 D4 + ADR-0011 D5).

---

## References

- [ADR-0017](../../../decisions/0017-audit-meta-consolidation.md) — D1 (subcommand architecture), D2 (structure rubric), D3 (docs rubric), D4 (report shape), D5 (bootstrap-mode), D6 (sibling-not-extension), D7 (deferred-cadence + boy-scout).
- [ADR-0011](../../../decisions/0011-subagent-quality-framework.md) — D1 (skill ownership), D2 (mechanical-only), D5 (no auto-capture), D6 (rubric embedded), D7 (no-args precedent — extended here with subcommands). The template this SKILL.md mirrors.
- [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D1c — GENERATOR trailer shape.
- [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7 (6-critic-cap, honored), D8 (surfacing convention — sources AM-DOCS-BACKLOG-SURFACING).
- [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) — T5 thin-prompt migration; full rule bodies live in `docs/current/concepts/rules/am-*.md`; full skill synthesis in `docs/current/entities/skills/audit-meta.md`.
- Backlog [#129](https://github.com/vojtech-stas/project-claude/issues/129) — structure auditor (consolidated as `--structure`).
- Backlog [#130](https://github.com/vojtech-stas/project-claude/issues/130) — doc-currency auditor (consolidated as `--docs`).
- Backlog [#47](https://github.com/vojtech-stas/project-claude/issues/47) — future cadence + boy-scout PRDs per ADR-0017 D7.
