---
name: audit-meta
description: Periodic mechanical audit of codebase structure + doc-currency. Subcommand architecture — `/audit-meta` (no-args = both), `/audit-meta --structure`, `/audit-meta --docs`. Sibling skill to /audit-subagents per ADR-0017. Mechanical/grep-only rubric; emits a single Markdown PASS/WARN/FAIL report. Advisory output only (no auto-capture, no PR, no critic gate). Use when you suspect structural bloat or doc drift, after merging a convention-changing ADR, or on the cadence backlog #47 will eventually define.
---

This skill is the mechanical drift-detector for **codebase structure** (file counts, file sizes, naming) and **documentation currency** (dangling refs, stale convention text) under the repo root. Per [ADR-0017](../../../decisions/0017-audit-meta-consolidation.md), it consolidates backlog #129 (structure) and #130 (docs) under one skill with subcommand architecture, sibling to [`/audit-subagents`](../audit-subagents/SKILL.md) per ADR-0017 D6 ([ADR-0011](../../../decisions/0011-subagent-quality-framework.md) precedent).

**Ownership rationale** (ADR-0017 D6 + ADR-0011 D1): skill not 7th critic (ADR-0008 D7 cap); sibling not extension (three-domain mega-rubric violates single-responsibility).

**Default conservative.** When a grep pattern is ambiguous (forbidden literal inside a quoted example), FAIL. Asymmetric-cost: spurious FAIL costs one user-glance; wrong-PASS lets real drift slip past. Mirrors `/audit-subagents` per ADR-0011 D2 precedent.

---

## Invocation

- `/audit-meta` (no args) — runs ALL subcommands; combined report.
- `/audit-meta --structure` — structure-audit only.
- `/audit-meta --docs` — docs-currency-audit only.

Any other arguments → `RESULT: INVALID_INPUT` per [ADR-0017](../../../decisions/0017-audit-meta-consolidation.md) D1.

Argument-parsing logic (shell-style switch): set `RUN_STRUCT` / `RUN_DOCS` flags from `$ARGS` — no args sets both; `--structure` / `--docs` set one each; neither match → `RESULT: INVALID_INPUT`.

---

## Process

1. **Parse args** — set `RUN_STRUCT` / `RUN_DOCS` flags (above).
2. **If `RUN_STRUCT=1`** — iterate STRUCT-* rule checks below; each fires its literal grep / `wc` / find pattern; record PASS / WARN / FAIL.
3. **If `RUN_DOCS=1`** — iterate DOCS-* rule checks below; each fires its literal pattern; record PASS / WARN / FAIL.
4. **Aggregate** the Markdown report — one subsection per active subcommand, one row per check (`PASS` / `WARN` / `FAIL` plus inline `details:` for non-PASS rows).
5. **Emit the report to stdout** followed by the canonical GENERATOR trailer.

---

## Rubric — Structure subcommand (skip if `RUN_STRUCT=0`)

### STRUCT-1 — `.claude/agents/` file count cap (≤ 12)

**Mechanic:** `ls .claude/agents/*.md | wc -l` → ≤ 12 → PASS; 13–15 → WARN; > 15 → FAIL.

**Rationale:** The 6-critic-cap from [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7 implies ~12 subagents at full saturation (6 critics + ~6 generators). Past that, the cognitive cost of maintaining a unified mental model of the agent fleet rises sharply. The three-band shape gives one round of soft warning before FAIL, absorbing a temporary excess during a multi-PRD wave.

### STRUCT-2 — `.claude/skills/` directory count cap (≤ 16)

**Mechanic:** `ls -d .claude/skills/*/ | wc -l` → ≤ 16 → PASS; 17–19 → WARN; > 19 → FAIL.

**Rationale:** The 16-skill cap accommodates the planned sibling-skill expansion ([ADR-0022](../../../decisions/0022-docs-first-kb-pattern.md)) but no further. New skills past 16 should justify why an existing skill cannot absorb the concern. Cap bumped from 12 to accommodate ADR-0022 D3+D8 best-practice sibling skills.

### STRUCT-3 — no markdown file > 500 LoC (split-candidate detector)

**Mechanic:** `find . -name "*.md" -not -path "./.git/*" -exec wc -l {} \; | awk '$1 > 500'` → empty → PASS; non-empty → WARN (list offending files with their LoC count).

**Rationale:** The 500-LoC threshold is the "split me" smoke alarm — anything past 500 lines in a single file outruns one-read comprehension. WARN-level because some files (CLAUDE.md, certain ADRs) legitimately grow large; the audit surfaces split candidates for the user to triage. The audit does NOT force a split.

### STRUCT-4 — no directory depth > 4 (nesting-bloat detector)

**Mechanic:** `find . -type d -not -path "./.git*" | awk -F/ 'NF-1 > 5'` → empty → PASS; non-empty → FAIL (list offending directories).

**Rationale:** The depth-4 cap (NF-1 > 5 flags depth > 5 path segments) reflects the project's natural tree: `repo/.claude/agents/foo.md` is depth 3; a 5-segment path like `repo/docs/x/y/z/foo.md` is at the cap, not over. New trees deeper than that FAIL. FAIL-level because nesting > 4 is a hard structural smell.

### STRUCT-5 — `decisions/` ADR count cap (≤ 20)

**Mechanic:** `ls decisions/[0-9]*.md | wc -l` → ≤ 20 → PASS; 21–25 → WARN; > 25 → FAIL.

**Rationale:** Past 20, the README index becomes painful to scan. Consolidation candidates (deprecated + superseded chains) should be reviewed. Informational cap — hitting it is a signal to review, not a hard error.

### STRUCT-6 — `.claude/agents/*.md` filenames match kebab-case pattern

**Mechanic:** `ls .claude/agents/ | grep -vE '^[a-z-]+\.md$'` → empty → PASS; non-empty → FAIL (list offenders).

**Rationale:** The `[a-z-]+(-critic)?\.md` shape is how the [ADR-0011](../../../decisions/0011-subagent-quality-framework.md) D3 classifier distinguishes critics from generators. A file named `Reviewer.md` (uppercase) or `prd_critic.md` (snake_case) breaks the classifier. Naming is a hard contract — FAIL, not WARN.

### STRUCT-7 — each `.claude/skills/*/` directory contains exactly one `SKILL.md`

**Mechanic:** `find .claude/skills -mindepth 2 -maxdepth 2 -name "*.md" -not -name "SKILL.md"` → empty → PASS; non-empty → FAIL (list offenders).

**Rationale:** The one-SKILL.md-per-directory convention is the Claude Code skills runtime contract. A skill directory with multiple `.md` files at depth 2 will either not load the skill correctly or load the wrong file as the entry point. FAIL on any extra `.md`.

### STRUCT-8 — `decisions/NNNN-*.md` filenames match `NNNN-<kebab-slug>.md` pattern

**Mechanic:** `ls decisions/ | grep -E '\.md$' | grep -vE '^[0-9]{4}-[a-z0-9-]+\.md$|^README\.md$'` → empty → PASS; non-empty → FAIL (list offenders).

**Rationale:** The `NNNN-<kebab-slug>.md` shape is how ADR cross-references resolve. An ADR named `0011_skill_quality.md` (underscore) will not match the `[ADR-NNNN](decisions/NNNN-*.md)` link pattern that propagates through every other doc. The `README.md` carve-out accommodates the `decisions/README.md` index (the only non-NNNN `.md` legitimately in that directory).

### STRUCT-9 — root `README.md` exists and is non-empty

**Mechanic:** `test -s README.md` → PASS if exit 0; FAIL if exit non-zero.

**Rationale:** `README.md` is what GitHub renders on the repo landing page — the first thing a human visitor sees. A missing or empty README is a hard signal of repo abandonment or misconfiguration. The `test -s` flag returns true only if the file exists AND is non-empty; an empty file FAILs just as decisively as a missing one.

### STRUCT-10 — root `CLAUDE.md` exists and is non-empty

**Mechanic:** `test -s CLAUDE.md` → PASS if exit 0; FAIL if exit non-zero.

**Rationale:** `CLAUDE.md` is what Claude Code auto-loads on every session; it's the first thing every AI agent sees. A missing or empty `CLAUDE.md` means agents operate without project rules, conventions, and the load-bearing glossary — they default to generic behavior. Same `test -s` mechanic as STRUCT-9.

---

## Rubric — Docs-currency subcommand (skip if `RUN_DOCS=0`)

### DOCS-1 — every `decisions/README.md` index entry resolves to an existing file

**Mechanic:** Extract every `(NNNN-[a-z0-9-]+\.md)` pattern from `decisions/README.md`; for each extracted target, run `test -f decisions/<target>`. All exist → PASS. Any missing → FAIL (list dangling refs).

**Rationale:** The ADR index is the primary discovery surface for the project's decision history. If the index links to ADRs that no longer exist (dangling rows), readers chase 404s and lose trust. Dangling rows typically come from renaming or deleting an ADR file without updating the index. Auditing only one direction catches half the drift.

### DOCS-2 — every `decisions/NNNN-*.md` on disk has a row in `decisions/README.md`

**Mechanic:** `for f in decisions/[0-9]*.md; do grep -qF "$(basename $f)" decisions/README.md || echo MISSING $f; done` → empty → PASS; non-empty → FAIL (list missing index entries).

**Rationale:** If the index omits ADRs that DO exist, readers don't discover them — the ADR's authority is silently invisible. Missing rows typically come from creating a new ADR file but forgetting the index update (a common slip when the slice's checklist doesn't enumerate "update decisions/README.md"). DOCS-1 + DOCS-2 together guarantee the index neither lies nor omits.

### DOCS-3 — every `.claude/agents/*.md` ref in CLAUDE.md Map resolves

**Mechanic:** Extract every `\.claude/agents/[a-z-]+\.md` reference from `CLAUDE.md`; for each, run `test -f`. All exist → PASS. Any missing → FAIL (list dangling refs).

**Rationale:** The CLAUDE.md Map is the agent/skill discovery surface for every Claude Code session. A dangling reference means an agent goes looking for a skill, the Map says it lives at a path, the file does not exist, and the agent fails silently or falls back to default behavior. Forward-direction only (Map → file) — reverse is intentionally not checked because the Map is curated (some agents are deliberately undocumented).

### DOCS-4 — every `.claude/skills/*/SKILL.md` ref in CLAUDE.md Map resolves

**Mechanic:** Extract every `\.claude/skills/[a-z-]+/SKILL\.md` reference from `CLAUDE.md`; for each, run `test -f`. All exist → PASS. Any missing → FAIL.

**Rationale:** Same Map-forward rationale as DOCS-3, applied to the skill half of the Map. A skill directory renamed without updating the Map → FAIL. The patterns use lowercase-kebab-only classes, mirroring the STRUCT-NAMING invariant.

### DOCS-5 — no bare `N=3` literal in `README.md` without adjacent ADR-0013 reference (±2-line proximity)

**Mechanic:**
```
grep -nF "N=3" README.md | while IFS= read -r hit; do
  lineno=$(echo "$hit" | cut -d: -f1)
  ctx=$(awk "NR>=$((lineno-2)) && NR<=$((lineno+2))" README.md)
  echo "$ctx" | grep -qF "ADR-0013" || echo "$hit"
done
```
Output empty → PASS; any output → FAIL with offending lines.

**Rationale:** [ADR-0013](../../../decisions/0013-slicer-n3-contract-refined.md) refined the slicer's N-decompositions contract; PR #125 fixed README but the literal could regress. DOCS-5 ensures it stays gone. The ±2-line ADR-0013 proximity check allows the legitimate citation `(N=3 or N=1 decompositions per ADR-0013)` that explicitly references the ADR as context. Scoped to README.md only (the file that historically carried the wrong literal).

**Generated-region exemption (per [ADR-0034](../../../decisions/0034-build-orchestrator-and-generated-docs.md)):** The `{{GENERATED:*}}` regions of README.md are machine-produced by `dashboard/server.py --generate-readme` and may legitimately contain `N=3` in auto-generated agent-description text (e.g., the `slicer` / `slicer-critic` component descriptions). The ADR-0013-adjacency check applies only to hand-written static template prose in `README.template.md`; generated regions are exempt. Practically: when DOCS-5 fires on a README.md hit, verify whether the offending line falls within a `{{GENERATED:*}}` region; if so, mark PASS (generated) rather than FAIL.

### DOCS-6 — no `GLOSSARY.md` references in `*.md` files outside the known-legitimate allowlist

**Mechanic:**
```
grep -rlF "GLOSSARY.md" --include="*.md" . \
  | grep -v "^\./\.git/" \
  | grep -v "^\./\.claude/worktrees/" \
  | grep -v "^\./tool-results/" \
  | grep -vE "^\./decisions/" \
  | grep -vF "./.claude/skills/audit-meta/SKILL.md" \
  | grep -vF "./.claude/skills/grill-me/SKILL.md"
```
Empty → PASS; non-empty → FAIL with file list.

**Rationale:** [ADR-0012](../../../decisions/0012-glossary-consolidation-single-tier.md) consolidated the glossary into CLAUDE.md and deleted the standalone `GLOSSARY.md` file. Any remaining reference to that filename is dead — either a broken link or a stale instruction. Two files legitimately reference it (this skill body and `grill-me/SKILL.md`); both are allowlisted. ADRs are allowlisted wholesale via `decisions/*` (immutable historical record per the `decisions/README.md` immutability convention). (Previously 5 allowlisted files; 3 KB-layer entries removed per [ADR-0032](../../../decisions/0032-workflow-only-architecture.md) D1.)

### DOCS-7 — every `[ADR-NNNN](decisions/NNNN-*.md)` citation in any tracked `.md` resolves

**Mechanic:**
1. Find every tracked `.md` file (excluding `.git/`).
2. For each, extract all `decisions/[0-9]{4}-[a-z0-9-]+\.md` link targets.
3. Filter out fake-example slugs matching `decisions/00[0-9]{2}-(old-name|fictional|fictional-adr|new-adr|new-decision)\.md`.
4. For each remaining unique target, run `test -f`.
5. PASS if all exist; FAIL with the (source-file, dangling-target) list otherwise.

**Rationale:** ADR references propagate aggressively through the codebase — subagent bodies, skill bodies, CLAUDE.md, other ADRs. A dangling citation means readers chase 404s, agents can't ground behavior in the ADR, and supersession chains break silently after ADR renames or consolidations. This is the broadest dangling-link check in the docs rubric (repo-wide vs DOCS-1's narrow scope). The fake-example allowlist (slug-shape regex) prevents rule-body atomic notes from triggering false positives when they illustrate the check with pedagogical slug strings (e.g., `0007-old-name.md`, `0099-fictional.md`).

### DOCS-8 — `decisions/README.md` Status column carries "superseded by ADR-NNNN" annotations (WARN)

**Mechanic:**
1. `grep -nE '^- \*\*Supersedes:\*\*' decisions/*.md` — enumerate supersession declarations using the actual ADR line-prefix format (`- **Supersedes:** ADR-NNNN Dx`).
2. For each matched line, extract the superseded D-ID.
3. For each pair, grep `decisions/README.md` Status column for the `superseded by` annotation referencing the superseder.
4. PASS if all annotations present (or no supersessions found); WARN with missing-annotation list otherwise.

**Rationale:** ADR supersession is the project's primary mechanism for evolving decisions without losing history (per the `decisions/README.md` immutability convention). Readers landing on a superseded ADR need a clear "replaced by ADR-NNNN" pointer in the index. WARN-level (not FAIL) because the ADR body has the authoritative `- **Supersedes:**` line; the README annotation is a discoverability convenience that lags by convention. Note: the pattern `^- \*\*Supersedes:\*\*` (with `- ` prefix) matches the actual ADR bullet format; the bare `^\*\*Supersedes:\*\*` pattern silently never fires since no ADR uses that format.

### DOCS-9 — CLAUDE.md glossary entry count ≤ 35 (ADR-0012 D5 soft cap; WARN)

**Mechanic:** `awk '/^## Glossary/{f=1; next} /^## /{f=0} f' CLAUDE.md | grep -cE '^- \*\*'` → ≤ 35 → PASS (report actual count); > 35 → WARN (consolidation candidate).

**Rationale:** The glossary is auto-loaded into every Claude Code session's context. Past ~35 entries, the cost-benefit shifts unfavorably: context-window cost inflates the per-session base load; discoverability degrades from "load-bearing terms only" to "general dictionary"; maintenance pressure on each entry's defensibility relaxes. WARN (not FAIL) — hitting the cap is a signal to act, not a failure mode. Options: consolidate related entries, demote generic-leaning terms, or accept if a new entry is genuinely load-bearing. The awk state-flag pattern `{f=1; next}` avoids the false-start bug of the range pattern `/^## Glossary/,/^## /` where both start and end patterns match the heading `## Glossary (key terms)`, causing the range to immediately close and returning zero.

### DOCS-10 — no `` `backlog`-labeled `` prose or `--label backlog` literal in agent or skill files

**Mechanic:** `grep -rE '(`backlog`-labeled|--label backlog)' .claude/agents .claude/skills` → empty → PASS; non-empty → FAIL with file:line list, excluding:
- `backlog-critic.md` (allowlisted per [ADR-0011](../../../decisions/0011-subagent-quality-framework.md) ALL-4 precedent)
- `promote-to-backlog/SKILL.md` (allowlisted — that skill IS the captured→backlog label-swap operator per [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D3; its `--label backlog` usage is the intended operation, not drift)
- `audit-meta/SKILL.md` (allowlisted — post-#341 the rubric was inlined here, so this file contains the `` `backlog`-labeled `` / `--label backlog` literals as rule-definition text, not as a capture instruction)
- `audit-subagents/SKILL.md` (allowlisted — same rationale as `audit-meta/SKILL.md`; the AS-ALL-4 check text is reproduced here as rule-definition text after #341 inlined the rubric)

**Rationale:** The captured-vs-backlog two-tier surfacing convention from [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D8 + [ADR-0009](../../../decisions/0009-discipline-tightening.md) D2 applies to every agent and skill that instructs deferred-work capture. If any skill body says "capture as `backlog`-labeled", it tells agents to skip the `backlog-critic` gate — the exact #105/#107 regression. DOCS-10 extends the AS-ALL-4 subagent-only check to the full skill layer, completing the coverage. Scope is `.claude/agents/` AND `.claude/skills/` — a strict superset of AS-ALL-4.

---

## Report shape

Single Markdown report with one subsection per active subcommand and a per-check table (`Check | Result | Details`). End with a Summary section (subcommands run / total checks / PASS-WARN-FAIL counts / FAIL enumeration). Per [ADR-0017](../../../decisions/0017-audit-meta-consolidation.md) D4 + [ADR-0011](../../../decisions/0011-subagent-quality-framework.md) D5, the report is advisory — user captures real findings per CLAUDE.md rule #11.

---

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
- [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7 (6-critic-cap, honored), D8 (surfacing convention — sources DOCS-10).
- [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) — T5 thin-prompt migration; former `am-*.md` atomic rule bodies are now inlined above.
- Backlog [#129](https://github.com/vojtech-stas/project-claude/issues/129) — structure auditor (consolidated as `--structure`).
- Backlog [#130](https://github.com/vojtech-stas/project-claude/issues/130) — doc-currency auditor (consolidated as `--docs`).
- Backlog [#47](https://github.com/vojtech-stas/project-claude/issues/47) — future cadence + boy-scout PRDs per ADR-0017 D7.
