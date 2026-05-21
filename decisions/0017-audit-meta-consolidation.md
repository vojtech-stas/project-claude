# ADR-0017: Audit-meta consolidation — /audit-meta skill with subcommand architecture (sibling to /audit-subagents)

- **Status:** Accepted
- **Date:** 2026-05-21
- **Supersedes:** none
- **Extends:** [ADR-0011](0011-subagent-quality-framework.md) D1 (skill ownership for periodic audits — pattern reused for /audit-meta), D2 (mechanical/grep-only rubric — same approach), D3 (scope-tagged checks — adapted to subcommand-tagged here), D5 (single Markdown report, no auto-capture — same), D6 (rubric embedded in SKILL.md — same), D7 (no-args invocation default — extended with subcommand args here). [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 (6-critic-cap meta-rule — honored; no new critic). [ADR-0004](0004-bypass-prevention.md) D2 (bootstrap-mode policy cited in D5 below).

## Context

PRD-α (PRD #132 → commit `a1d71f3` + hook-fix PR #135 → `1e57d13`) and PRD-β (in flight) established Claude Code hooks + workflow event log. This PRD (PRD-γ in the 3-PRD Cluster A roadmap) ships the third leg: an `/audit-meta` skill that consolidates two captured meta-quality concerns (#129 structure auditor + #130 doc-currency auditor) under one skill with subcommands.

Per the 2026-05-21 meta-grill:
- **Q1=1A**: PRD-β and PRD-γ ship as separate PRDs
- **Q2=2A**: ONE /audit-meta skill with subcommands (over 3 separate skills, or extending /audit-subagents)
- **Q3=3B**: PRD-γ scope = /audit-meta skill only (post-PRD cadence + boy-scout reviewer rule from #47 deferred to follow-up PRDs)

The skill follows /audit-subagents (ADR-0011) as the reference precedent: mechanical/grep-only rubric, scope-tagged checks, single Markdown report, no auto-capture, embedded rubric. The difference: /audit-meta has two domains (structure + docs) and uses subcommands to scope each run.

## Decisions

### D1: Subcommand architecture

`/audit-meta` is a user-invokable skill with three invocation modes:
- `/audit-meta` (no args) — runs all subcommands; emits a single combined report with subcommand subsections
- `/audit-meta --structure` — runs structure-audit only
- `/audit-meta --docs` — runs docs-currency-audit only

Argument-parsing logic lives in the skill body (~15-20 LoC of shell-style argument handling). Per ADR-0011 D7 precedent, no-args is the default; this ADR extends with subcommand args.

### D2: Structure-audit rubric

`subcommand: structure` checks (~10 mechanical/grep checks):

- **STRUCT-1**: `.claude/agents/` file count ≤ 12 (subagent-count threshold; ADR-0008 D7 6-critic-cap headroom)
- **STRUCT-2**: `.claude/skills/` direct-child directory count ≤ 12 (skill-count health)
- **STRUCT-3**: no markdown file > 500 LoC (file-size threshold — flags candidates for splitting)
- **STRUCT-4**: no directory depth > 4 (relative to repo root; flags nesting bloat)
- **STRUCT-5**: `decisions/` ADR count ≤ 20 (ADR-count health; mostly informational)
- **STRUCT-6**: every file under `.claude/agents/*.md` matches naming pattern `[a-z-]+(-critic)?\.md`
- **STRUCT-7**: every file under `.claude/skills/*/SKILL.md` (no other `.md` files at the same depth — enforces single-SKILL.md-per-skill convention)
- **STRUCT-8**: every `decisions/*.md` matches `NNNN-<kebab-slug>.md` pattern
- **STRUCT-9**: root README.md exists + is non-empty
- **STRUCT-10**: root CLAUDE.md exists + is non-empty

Each check: mechanical (grep / file-count / Glob); PASS/FAIL output; concrete WARN where threshold-near-cap.

### D3: Docs-currency rubric

`subcommand: docs` checks (~10 mechanical/grep checks):

- **DOCS-1**: every `decisions/NNNN-*.md` referenced in `decisions/README.md` exists (no dangling index rows)
- **DOCS-2**: every `decisions/NNNN-*.md` on disk has a row in `decisions/README.md` (no missing index entries)
- **DOCS-3**: every `.claude/agents/*.md` referenced in `CLAUDE.md` Map exists (no dangling Map rows)
- **DOCS-4**: every `.claude/skills/*/SKILL.md` referenced in `CLAUDE.md` Map exists
- **DOCS-5**: no `N=3` literal references in `README.md` (post-ADR-0013; concrete drift detector for the 2026-05-21 case)
- **DOCS-6**: no `GLOSSARY.md` references anywhere in `*.md` files (post-ADR-0012; file was deleted)
- **DOCS-7**: every ADR cited as `[ADR-NNNN](decisions/NNNN-*.md)` resolves to an existing file
- **DOCS-8**: `decisions/README.md` Status column has explicit "superseded by ADR-NNNN" notes for all ADRs whose D-IDs have supersession headers
- **DOCS-9**: `CLAUDE.md` glossary section count ≤ 35 (per ADR-0012 D5 cap)
- **DOCS-10**: no `backlog`-label surfacing instructions remain in subagent/skill files (per PRD #103 + #106; concrete drift detector)

Each check: mechanical (grep / file-existence / pattern-match); PASS/FAIL output.

### D4: Report shape

Single Markdown report per invocation. Sections:
- Header with invocation summary (subcommands run + timestamp)
- `## Structure findings` (only if --structure or no-args)
- `## Docs findings` (only if --docs or no-args)
- Per-check format matches ADR-0011 precedent (table or list with PASS/FAIL + concrete file:line citations)
- GENERATOR trailer per ADR-0005 D1c at end

Advisory only — no auto-capture per ADR-0011 D5 precedent. User reviews and decides follow-up captures per rule #11.

### D5: Bootstrap-mode acknowledgment (per ADR-0004 D2)

The rubric applies forward from slice-1 merge. Existing structure + docs state at merge time is audited by the slice-1 dogfood — findings are ADVISORY (not blocking; not auto-captured). Per ADR-0011 D8 precedent, the rubric does NOT retroactively mark anything as violating; it surfaces drift for user triage.

The 6-critic-cap (ADR-0008 D7) is unaffected — /audit-meta is a skill, not a critic.

### D6: Relationship to /audit-subagents (sibling, not extension)

/audit-subagents (per ADR-0011) is preserved unchanged. Its rubric stays scoped to subagent-prompt quality (10 checks on `.claude/agents/*.md`). /audit-meta is a **sibling skill** with separate rubrics for structure + docs.

Rationale (per Q2 alternatives 2C/2D rejection):
- Extending /audit-subagents to cover structure + docs would inflate its rubric from 10 to ~30 checks across 3 domains — violates single-responsibility shape ADR-0011 codified
- Two skills with focused scopes is cleaner than one kitchen-sink skill

Future PRD MAY refactor to share infrastructure (e.g., factor out a common report-rendering helper) — that's a separable DRY concern, not in PRD-γ scope.

### D7: Deferred — post-PRD cadence + boy-scout reviewer rule

Per Q3=3B, backlog [#47](https://github.com/vojtech-stas/project-claude/issues/47) (post-PRD audit stage + per-PR boy-scout-rule) is **explicitly NOT included** in this PRD. Two separable follow-up PRDs:
- **Cadence PRD**: when does /audit-meta auto-fire? (post-PRD-merge via hook? scheduled? manual-only?)
- **Boy-scout PRD**: reviewer-side convention "when touching X, look around and fix what's broken" — a reviewer rule extension, not an audit skill change

ADR-0017 deliberately defers both to keep PRD-γ walking-skeleton.

## Consequences

### Positive

- **Closes 2/3 of the meta-quality cluster** (#129 + #130 land in one PRD; #47 deferred but tracked)
- **Subcommand architecture is reusable**: future skills with multiple modes can follow this pattern
- **Mechanical drift detection**: DOCS-5 (no `N=3` references) and DOCS-10 (no `backlog`-label surfacing) are concrete codifications of recent failure modes (2026-05-20/21 sessions)
- **No critic-count expansion**: honors ADR-0008 D7 cleanly

### Negative / Accepted

- **Subcommand parsing complexity**: ~15-20 LoC of shell-style arg handling in the skill body. If argument combinations grow (e.g., `--structure --skip-naming`), the parsing layer bloats. Mitigation: keep argument set minimal; refactor to dedicated parsing skill only if pain emerges.
- **Two rubrics in one skill body**: SKILL.md grows larger (~200 LoC vs ADR-0011's /audit-subagents at ~165 LoC). Acceptable for walking-skeleton; if the file exceeds ~300 LoC, future PRD may split into sub-files.
- **Doesn't close #47**: cadence + boy-scout deferred. Cluster A is not "done" until #47 ships in follow-up PRDs.
- **Threshold values are guesses**: STRUCT-1 (`.claude/agents/` ≤ 12) and DOCS-9 (~35 entry cap) are educated guesses; may need tuning per post-merge observation.
- **No auto-fix**: strictly advisory per ADR-0011 D5 precedent. User must manually act on findings.

## Alternatives considered

- **Alt-A: Three separate sibling skills** (`/audit-structure`, `/audit-docs`, `/audit-post-prd`). Rejected per Q2 — DRY violation (rubric/report infra repeated); 3 invocations to get full audit; skill-count creep.
- **Alt-B: Extend /audit-subagents with structure + docs modes.** Rejected per Q2 — inflates a single-purpose skill into a kitchen-sink; violates ADR-0011's single-responsibility shape; rubric bloats to ~30 checks across 3 domains.
- **Alt-C: One /audit-meta skill that ALSO absorbs /audit-subagents** (full unification). Rejected per Q2 — deprecates a recently-shipped skill (ADR-0011 supersession); breaking change for existing invocations.
- **Alt-D: Include post-PRD cadence + boy-scout rule (full #47).** Rejected per Q3=3B — separable concerns; cadence needs its own design (hook? scheduled? manual?); boy-scout is a reviewer rule extension.
- **Alt-E: LLM-semantic checks.** Rejected — non-deterministic; expensive; loses mechanical concreteness per ADR-0011 D2 precedent.
- **Alt-F: Auto-fix mode.** Rejected — strictly advisory per ADR-0011 D5 precedent; safer to surface + user-triage.
- **Alt-G: Auto-capture findings as captured-issues.** Rejected — user-driven follow-up per rule #11 + ADR-0011 D5 precedent.
- **Alt-H: Read PRD-β workflow event log to enrich audits** (e.g., "this skill hasn't fired in N sessions"). Rejected for slice 1 — defer to future PRD; walking-skeleton.

## Open questions deferred

- **Threshold values**: STRUCT-1, STRUCT-3, STRUCT-4, STRUCT-5, DOCS-9 — all guesses; revisit post-merge if false positives accumulate
- **Subcommand parsing robustness**: revisit if argument combinations grow
- **DRY refactor**: share infrastructure with /audit-subagents — future concern
- **Workflow-event-log integration**: enrich audits with /audit-meta reading PRD-β substrate — future concern
- **Cadence mechanism**: when does /audit-meta auto-fire? — future PRD per Q3=3B
- **Boy-scout reviewer rule**: R-BOY-SCOUT extension — future PRD per Q3=3B

## Future direction

- **Cadence PRD (from #47 first half)**: hook-fired post-PRD-merge OR scheduled-by-cron OR manual-only
- **Boy-scout PRD (from #47 second half)**: reviewer rule R-BOY-SCOUT
- **DRY refactor**: factor shared report-rendering / scope-tag handling between /audit-meta and /audit-subagents
- **Threshold tuning**: post-observation calibration
- **Event-log integration**: /audit-meta reads PRD-β substrate for cadence-aware checks

## References

- [ADR-0011](0011-subagent-quality-framework.md) — D1, D2, D3, D5, D6, D7 (the precedent pattern this ADR extends)
- [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 (6-critic-cap; unaffected)
- [ADR-0004](0004-bypass-prevention.md) D2 — bootstrap-mode policy cited in D5
- [ADR-0012](0012-glossary-consolidation-single-tier.md) D5 — ~35-entry glossary cap (DOCS-9 enforces)
- [ADR-0013](0013-slicer-n3-contract-refined.md) — the convention DOCS-5 enforces (no stale N=3)
- [ADR-0015](0015-claude-code-hooks-adoption.md) — sibling Cluster A PRD; ADR-0016 (PRD-β workflow event log) is in flight and not yet on `main` — textual reference only to avoid dangling link
- Backlog [#129](https://github.com/vojtech-stas/project-claude/issues/129) — structure auditor (consolidated as `--structure`)
- Backlog [#130](https://github.com/vojtech-stas/project-claude/issues/130) — doc-currency auditor (consolidated as `--docs`)
- Backlog [#47](https://github.com/vojtech-stas/project-claude/issues/47) — post-PRD audit + boy-scout (deferred per D7)
- `.claude/skills/audit-meta/SKILL.md` — the new skill (created in slice 1)
- `.claude/skills/audit-subagents/SKILL.md` — the sibling skill (preserved unchanged)
