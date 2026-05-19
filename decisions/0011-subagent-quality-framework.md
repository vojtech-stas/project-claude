# ADR-0011: Subagent-quality framework — `/audit-subagents` skill + mechanical/grep rubric

- **Status:** Accepted
- **Date:** 2026-05-19
- **Extends:** [ADR-0001](0001-foundational-design.md) D6 (subagent definition — rubric checks tool boundaries); [ADR-0005](0005-output-shape-and-slicing-methodology.md) D1 (canonical output shapes — rubric checks for trailers + verdict templates); [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 (6-critic-cap meta-rule — honored by skill-ownership choice, no new critic added); [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D8 (captured-tier surfacing — rubric ALL-4 mechanizes the drift detector); [ADR-0009](0009-discipline-tightening.md) D3 (default-BLOCK — rubric CRIT-1 mechanizes the compliance check); [ADR-0009](0009-discipline-tightening.md) D4 (adversarial mindsets — rubric CRIT-2 mechanizes the compliance check)
- **Supersedes:** none

## Context

The project has 8 subagents on `main` (6 critics: `reviewer`, `prd-critic`, `adr-critic`, `slicer-critic`, `glossary-critic`, `backlog-critic`; 2 generators: `slicer`, `implementer`) authored incrementally across PRDs #3, #15, #28, #41, #53, #58, #75, #80. Each was reviewed by humans and shipped through the autonomous pipeline. Conventions accumulated across ADRs over time:

- ADR-0001 D6 — subagent definition (frontmatter, tool restrictions, isolated context).
- ADR-0005 D1 — canonical output shapes: 5-section verdict + CRITIC trailer for the 4 hard-gating critics; GENERATOR trailer + domain-shaped body for generators.
- ADR-0008 D7 — 6-critic-cap meta-rule (7th critic requires explicit ADR justification).
- ADR-0008 D8 — captured-tier surfacing convention (agents capture as `captured`-labeled, autopilot promotes to `backlog`).
- ADR-0009 D3 — asymmetric-default-BLOCK clause across all critics.
- ADR-0009 D4 — distinct adversarial mindset framing per critic.

There is currently no mechanical verification that any individual subagent file applies the current conventions. The 2026-05-19 stale-worktree audit demonstrated the failure mode end-to-end: a context-completeness audit was launched, surfaced ~17 alarming "findings" that were mostly false alarms (the audit ran against a worktree pre-dating shipped slices), and only after manual re-verification against `origin/main` did one real systemic drift surface — five subagent files still instruct agents to capture follow-ups as `backlog`-labeled issues, silently bypassing the `backlog-critic` autopilot established by ADR-0008 D2 and made mandatory by ADR-0009 D2 (captured as backlog [#93](https://github.com/vojtech-stas/project-claude/issues/93)).

The grill session (Q1–Q10) walked the absorption-mechanism question (A skill vs B reviewer rule vs C 7th critic vs D hybrid), the scope question (validation-only walking-skeleton vs writing-tools bundle), the rubric-shape question (mechanical/grep vs LLM-semantic), the architecture (one rubric scope-tagged vs two-track), the depth (10 high-confidence checks vs 14 with medium-confidence), the output (single report vs auto-capture), the rubric location (embedded in SKILL.md vs separate file), the invocation (no-args vs targeted), and the slice plan (single walking-skeleton bundle).

## Decisions

### D1: Skill ownership of subagent-quality

`/audit-subagents` is a skill under `.claude/skills/audit-subagents/SKILL.md`. It is NOT a 7th critic and NOT a reviewer rule extension.

**Why a skill, not a critic.** The 6-critic-cap meta-rule (ADR-0008 D7) requires explicit justification for a 7th critic — and the justification fails here: subagent-quality is a periodic-audit cadence, not a synchronous gate. A critic is the wrong shape because it would only fire when a subagent file changes, missing drift that accumulates in unchanged files (the exact failure mode that motivated this PRD). A skill is user-invocable, schedulable, and composable into a future post-PRD audit pipeline (per backlog [#47](https://github.com/vojtech-stas/project-claude/issues/47)) without re-deciding ownership.

**Why a skill, not a reviewer rule.** A `R-SUBAGENT-QUALITY` rule would couple quality verification to PR-time only — exactly the gap that produced the captured-vs-backlog drift across 5 files unchanged for multiple PRDs. PR-time is the wrong cadence for drift detection.

### D2: Mechanical/grep-only rubric, pattern-derived

The rubric codifies patterns the 8 existing subagents have already converged on. Sources of the patterns: ADR-0005 D1 (canonical output shapes), ADR-0009 D3 (default-BLOCK clause), ADR-0009 D4 (adversarial mindset), ADR-0001 D6 (subagent definition + tool boundaries), ADR-0008 D8 (captured-tier surfacing convention).

Every check is a literal `grep` pattern producing a deterministic PASS or FAIL. No LLM judgment, no model calls, no per-check API cost. Two consequences: (a) the audit is reproducible — same input always yields same output; (b) the slice-1 dogfood produces a stable expected-output baseline that the implementer can paste verbatim into the PR comment.

LLM-semantic checks (e.g., "is this rubric item mechanically actionable?", "is this mindset block tight, not personality?") are deferred to a future PRD if the mechanical rubric proves insufficient.

### D3: One rubric file, scope-tagged checks

The rubric is a single embedded section in `SKILL.md`. Each check declares a `scope:` tag selecting from `all | critic | generator`. The skill iterates subagent files and applies only the applicable checks per file.

**Classifier rule (locked):** filename ends `-critic.md` OR is `reviewer.md` → critic; else generator.

Verified against current main: `reviewer.md`, `prd-critic.md`, `adr-critic.md`, `slicer-critic.md`, `glossary-critic.md`, `backlog-critic.md` → critic (6); `slicer.md`, `implementer.md` → generator (2). Total 8.

**Why not two-track.** Two rubric files (one per type) duplicate the ~5 shared checks (frontmatter, tool boundaries, references, surfacing convention, mandatory reading order) and create drift risk — the exact failure mode this ADR exists to prevent.

### D4: 10 high-confidence checks in slice 1

Each check is a literal grep pattern. Scope tag indicates which subagent types it applies to.

| ID | Scope | Check | Source convention |
|---|---|---|---|
| ALL-1 | all | Frontmatter present (`name`, `description`, `tools`, `model` fields in the leading YAML block) | ADR-0001 D6 |
| ALL-2 | all | "Tool boundaries" section heading present | ADR-0001 D6 |
| ALL-3 | all | "References" section heading present | Convention across 8 subagents |
| ALL-4 | all | Surfacing-convention prose uses `captured`-label, NOT `backlog`-label (the #93 drift detector) | ADR-0008 D8 + ADR-0009 D2 |
| ALL-5 | all | "Mandatory reading order" OR "When invoked" section heading present | Convention across 8 subagents |
| CRIT-1 | critic | Default-BLOCK clause present (literal "Default conservative" string) | ADR-0009 D3 |
| CRIT-2 | critic | Adversarial mindset block present ("paranoid" OR "Adversarial mindset" string) | ADR-0009 D4 |
| CRIT-3 | critic | CRITIC trailer spec present (`VERDICT:`, `REASON:`, `ROUND:` fields in a fenced block) | ADR-0005 D1b |
| CRIT-4 | critic | 5-section verdict template present (Header → Subject of review → Rubric → Findings → Summary headings) | ADR-0005 D1a |
| GEN-1 | generator | GENERATOR trailer spec present (`RESULT:`, `REASON:`, `ARTIFACTS:` fields in a fenced block) | ADR-0005 D1c |

Total: 5 scope-`all` × 8 subagents + 4 scope-`critic` × 6 critics + 1 scope-`generator` × 2 generators = 40 + 24 + 2 = 66 check evaluations per audit run.

Medium-confidence checks (bootstrap-mode ack, round-limit declaration, escalation behavior, failure-modes enumeration) are explicitly deferred — fuzzier patterns risk false positives that would erode trust before the rubric is established. Low-confidence/semantic checks (rubric items mechanically actionable, body-shape declaration explicit) are also deferred.

### D5: Single Markdown report to stdout, no auto-capture

`/audit-subagents` emits a single Markdown report grouping findings by subagent (table format: subagent × applicable checks → PASS/FAIL). The skill does NOT call `gh issue create`. The user reviews the report and captures real follow-ups per rule #11 manually.

**Why not auto-capture.** Slice-1 dogfood is expected to surface ~5 ALL-4 FAILs (the captured-vs-backlog drift across 5 files), all of which are already captured under backlog #93. Auto-capturing 5 duplicate-of-#93 issues would force `backlog-critic` to BLOCK them as duplicates (correct, but noisy) and would obscure any genuine non-#93 finding. Revisit auto-capture in a future PRD if the report-only flow proves friction-heavy.

### D6: Rubric embedded in `SKILL.md`

The rubric is part of `SKILL.md`'s body, not a separate file. Walking-skeleton single-file pattern. Future extraction to a separate `rubric.md` (or to this ADR's body) is a deferred refactor if cross-skill references emerge (e.g., a future `/subagent-new` scaffold skill would benefit from referencing the rubric without depending on the audit skill).

### D7: No-args invocation, scans all subagents under `.claude/agents/*.md`

`/audit-subagents` takes no arguments. It globs `.claude/agents/*.md`, classifies each per D3, applies the rubric per D4, and emits the report per D5.

**Why not optional `<name>` argument.** Two code paths in slice 1 inflate the implementation; the bulk-audit case IS the primary use case (drift detection across all subagents); targeted single-subagent audit is a future-PRD convenience.

### D8: Bootstrap-mode acknowledgment

The rubric applies forward from the slice-1 merge. From that point onward, any new subagent or subagent-file edit may be audited via `/audit-subagents`; findings are advisory (not blocking; not reviewer-gated; not auto-captured).

The existing 8 subagents are audited as the slice-1 dogfood. Findings from the dogfood are advisory only — they do NOT make the slice-1 PR fail (per D5 the report is informational), and they do NOT retroactively mark any existing subagent as "violating ADR-0011" since the rubric did not exist when those subagents were authored. Real findings (e.g., the ~5 ALL-4 FAILs that duplicate #93) are routed to existing or new captured-tier issues per rule #11.

**Future blocking variant.** A subsequent PRD that introduces a blocking enforcement mechanism (e.g., a reviewer `R-SUBAGENT-QUALITY` rule that hard-blocks PRs touching `.claude/agents/*.md` if any audit check FAILs against the touched files) MUST acknowledge its own bootstrap-mode policy under ADR-0004 D2 — naming which slice the blocking rule binds to and how pre-existing FAILs are handled (typically: grandfathered until next touch, then blocking).

**Non-recursive audit pattern.** The `/audit-subagents` skill ships under `.claude/skills/`, not `.claude/agents/`. The skill audits OTHER subagents, not itself. No critic-of-critic infinite regress; no audit-of-auditor recursion. This is enforced mechanically by the no-args glob pattern (D7): `.claude/agents/*.md` does not match `.claude/skills/audit-subagents/SKILL.md`.

### D9: Sibling backlog-item relationships (future-direction posture)

- **Backlog [#47](https://github.com/vojtech-stas/project-claude/issues/47) (post-PRD audit + boy-scout rule):** `/audit-subagents` is a natural auditor for #47's pipeline when that PRD is grilled and shipped. This ADR does NOT pre-decide #47's design — it merely notes the composition surface (#47 calls `/audit-subagents`; `/audit-subagents` returns its report; #47 decides what to do with it).
- **Backlog [#70](https://github.com/vojtech-stas/project-claude/issues/70) (improver-critic pair):** different domain — improver targets source code; `/audit-subagents` targets subagent prompts. Independent; no composition pre-decided.
- **Backlog [#93](https://github.com/vojtech-stas/project-claude/issues/93) (surfacing-convention drift fix):** independent ship. This ADR's ALL-4 check IS the mechanized detector for #93's drift pattern. The two PRDs interlock: this PRD detects, #93 fixes. Either can ship first.

## Consequences

### Positive

- Drift detection becomes mechanical and reproducible. The 2026-05-19 stale-worktree audit failure mode (humans reading subagent files one by one, anchoring against the wrong base, surfacing false alarms) is eliminated by the deterministic grep pattern.
- The rubric codifies conventions already established across ADR-0001/0005/0008/0009 — it is descriptive of the system, not prescriptive of a new ideology. Future subagent authors can read the rubric to learn the conventions; this absorbs ~80% of what a separate style-guide doc would deliver.
- Honors the 6-critic-cap meta-rule (ADR-0008 D7) cleanly — zero new critics added; the absorption decision is in this ADR's D1.
- Slice-1 dogfood produces an immediate, observable signal: the audit catches the #93 drift across 5 files. The implementer pastes the audit output into the PR comment; the reviewer can verify the audit works without re-running it.

### Negative / Accepted

- The rubric is rule-based, not principle-based. New conventions adopted in future ADRs are not automatically reflected — each new convention needs a new check added to the rubric. Mitigation: the additive-check-per-convention pattern is mechanical; ADRs introducing new conventions can include a corresponding new rubric check in the same PRD as a cascade-doc edit. Tracked at the ADR-review level by `adr-critic`.
- Mechanical/grep checks cannot catch semantic drift (e.g., a mindset block exists but is actually a personality novel). LLM-semantic checks are explicitly deferred per D2.
- Slice-1 dogfood surfaces ~5 FAILs that mostly duplicate backlog #93. Mitigation per D5: no auto-capture; user reads report and decides.
- The skill itself is a subagent-shaped artifact (prompt + rubric + behavior) but is NOT audited by itself (per D8 non-recursive). A future PRD could extend the audit to `.claude/skills/*.md` if a skill-quality rubric is warranted; that's a separate decision.

## Alternatives considered

- **Alt-A: 7th critic (`subagent-critic`).** Rejected per Q1=1A. Breaches ADR-0008 D7 6-critic-cap; synchronous gate is the wrong shape for drift detection; only fires on subagent-file PRs, misses drift in unchanged files.
- **Alt-B: Extend `reviewer.md` with `R-SUBAGENT-QUALITY` rule.** Rejected per Q1=1A. Couples quality to PR-time only — misses drift in unchanged files (the exact failure mode that produced the captured-vs-backlog drift); mixes meta-quality with R-LOC/R-CLOSES PR-mechanics; reviewer rubric already at 11 rules.
- **Alt-C: Hybrid (skill + thin reviewer rule).** Rejected per Q1=1A. Over-engineered for walking-skeleton; the rubric must split cleanly into PR-time-mechanical vs periodic-strategic which has no clean split surface; revisit only if D8's future-blocking-variant path becomes warranted.
- **Alt-D: LLM-semantic rubric.** Rejected per Q3=3A. Non-deterministic + expensive; loses mechanical concreteness ("fix line 244 from `backlog` to `captured`" beats "reviewer feels off"); fragile dogfood basis.
- **Alt-E: Greenfield first-principles rubric.** Rejected per Q3=3A. Rejects working conventions across 8 subagents (Not-Invented-Here); the patterns ARE the right defaults.
- **Alt-F: Two-track rubric (critic-rubric + generator-rubric files).** Rejected per Q4=4B. Shared checks duplicated across two files; drift risk (the same failure mode this PRD exists to prevent).
- **Alt-G: Universal rubric with N/A handling.** Rejected per Q4=4B. Noisy reports (every generator audit shows N/A for 5 critic checks); 'N/A' is just scope-as-runtime-classification, worse than declarative scope tags.
- **Alt-H: No typology, check everything against everything.** Rejected per Q4=4B. False positives on every generator; audit signal-to-noise collapses.
- **Alt-I: Auto-capture per FAIL with `/promote-to-backlog` autopilot.** Rejected per Q6=6B. 5–7 simultaneous captures from slice-1 dogfood; most are #93 variants — `backlog-critic` BLOCKs them as duplicates (correct, but noisy); skill complexity grows; coupling to autopilot makes the audit skill non-portable.
- **Alt-J: Aggregating single capture issue (one issue, N findings inside).** Rejected per Q6=6B. Loses per-item actionability; aggregating violates the captured-tier's per-item granularity per ADR-0008 D1.
- **Alt-K: Perpetual "subagent quality status" tracking issue.** Rejected per Q6=6B. Anti-pattern per CLAUDE.md (per-item issues preferred over rolling logs); easy to ignore; harder to gh-query.
- **Alt-L: Separate `rubric.md` file in skill folder.** Rejected per Q7=7A. Heavier than walking-skeleton; deferring the extract is cheap if it turns out needed.
- **Alt-M: ADR is canonical, SKILL.md duplicates briefly.** Rejected per Q7=7A. Duplication = drift risk (same failure mode this PRD exists to prevent).
- **Alt-N: Required `<name>` argument (must pick subagent to audit).** Rejected per Q8=8A. Hostile to the primary bulk-audit use case; user would have to run 8 times to audit everything.
- **Alt-O: Multi-slice split (e.g., skill+ADR slice 1, README cascade slice 2).** Rejected per Q9=9A. Slice 2 would be ~10 LoC — below trivial-lane threshold (I3 says ≤10 LoC → hotfix); arbitrary split that doesn't make the work clearer; cascade-doc check (slicer-critic criterion 9) is best satisfied in-slice.

## Open questions deferred

- **Cadence of `/audit-subagents` invocation in normal operation.** Deferred to backlog #47 (post-PRD audit + boy-scout rule) — that PRD owns the cadence question. Until #47 lands, invocation is manual on user demand.
- **Whether the rubric eventually warrants a blocking variant** (e.g., reviewer `R-SUBAGENT-QUALITY` rule). Open; revisit after observing the signal/noise ratio over multiple `/audit-subagents` invocations.
- **Whether `.claude/skills/*.md` deserves its own audit rubric** (separate from this subagent rubric). Open; out of scope here.

## Future direction

- **Medium-confidence checks** (bootstrap-mode ack, round-limit declaration, escalation behavior, failure-modes enumeration) added in a follow-up PRD once HC-only signal/noise is observed.
- **LLM-semantic checks** added in a follow-up PRD if mechanical-only proves insufficient (e.g., catching mindset blocks that are personality novels rather than scrutiny lenses).
- **Style-guide doc + `/subagent-new` scaffold** — separable per Q2=2A; a future PRD if subagent-author friction is observed.
- **Reviewer integration (`R-SUBAGENT-QUALITY`)** — separable per Q1=1A; a future PRD with its own bootstrap-mode policy (per D8).
- **Auto-capture mode** — separable per Q6=6B; a future PRD if report-only proves friction-heavy.
- **Composition with backlog #47's post-PRD audit pipeline** — per D9; #47's grill will decide the composition surface.

## References

- [ADR-0001](0001-foundational-design.md) D6 — subagent definition; the rubric ALL-1 (frontmatter) and ALL-2 (Tool boundaries section) checks codify this.
- [ADR-0003](0003-autonomous-pipeline-with-critics.md) D8 — macro-ADR placement at grill→PRD boundary (why this ADR ships alongside the PRD).
- [ADR-0004](0004-bypass-prevention.md) D2 — bootstrap-mode policy this ADR's D8 cites.
- [ADR-0005](0005-output-shape-and-slicing-methodology.md) D1a — 5-section verdict template (rubric CRIT-4 codifies); D1b — CRITIC trailer (rubric CRIT-3 codifies); D1c — GENERATOR trailer (rubric GEN-1 codifies); D2 — slicing methodology depth (walking-skeleton anti-horizontal-layering rule applied to slice 1); D3 — cascade-doc check (slicer-critic criterion 9 applied to this PRD's README + CLAUDE.md edits).
- [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D2 — autopilot semantics; D7 — 6-critic-cap meta-rule (honored by D1's skill-ownership choice); D8 — captured-tier surfacing (rubric ALL-4 codifies).
- [ADR-0009](0009-discipline-tightening.md) D2 — mandatory rule #11 capture (cited in D8 as why future audit findings route to captured); D3 — default-BLOCK clause (rubric CRIT-1 codifies); D4 — adversarial mindsets (rubric CRIT-2 codifies).
- [`.claude/skills/audit-subagents/SKILL.md`](../.claude/skills/audit-subagents/SKILL.md) — the skill this ADR specifies (to be created in slice 1).
- Backlog [#92](https://github.com/vojtech-stas/project-claude/issues/92) — origin captured item.
- Backlog [#93](https://github.com/vojtech-stas/project-claude/issues/93) — the surfacing-convention drift fix (rubric ALL-4 is the mechanized detector for this drift).
- Backlog [#47](https://github.com/vojtech-stas/project-claude/issues/47) — post-PRD audit pipeline (composition surface per D9).
