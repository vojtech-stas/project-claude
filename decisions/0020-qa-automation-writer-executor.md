# ADR-0020: QA automation — writer/executor split (Tier 1 of backlog #57)

- **Status:** Accepted
- **Date:** 2026-05-22
- **Supersedes:** none
- **Extends:** [ADR-0003](0003-autonomous-pipeline-with-critics.md) D4 (refines terminal human checkpoint — mechanical work automated, judgment work preserved); [ADR-0005](0005-output-shape-and-slicing-methodology.md) D1c (GENERATOR trailer schema reused for qa-tester output); [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 (6-critic-cap meta-rule honored, no new critic added).

## Context

PRD-13 (the PRD this ADR ships alongside) implements Tier 1 of backlog [#57](https://github.com/vojtech-stas/project-claude/issues/57): mechanical QA-automation via a writer/executor split. The current `/qa-plan` skill (166 LoC) generates a 16-test flat checklist for human execution. On 2026-05-22 the user explicitly rejected this format: *"I really don't want to be doing QAs (there are 16 tests it would take me two hours) we need to change the logic"*. The 80-minute human-effort cost was wrong shape — ~12 of 16 tests are mechanically verifiable (already covered by the reviewer subagent per-PR) and only 3-4 are genuine judgment calls.

A replacement pattern was dogfooded on closed PRD #147 the same day: main-agent ran the 13 mechanical checks directly (~2 min) + asked 3 judgment Qs via AskUserQuestion (~3 min user effort) — total 5 min vs projected 80 min, with the same all-PASS verdict. This ADR locks that pattern into a reusable writer/executor split. Tiers 2 (agentic semantic QA) and 3 (UI/browser QA) per #57 are deferred to future PRDs per D6/D7.

## Decisions

### D1: Writer/executor separation pattern

`/qa-plan` skill (writer) produces a structured QA-plan from PRD §2 prose; `qa-tester` subagent (executor) runs the plan one-by-one. Two-component design mirrors slicer + slicer-critic shape (one generates, one judges) but adapted for execution (one plans, one executes). The writer runs in main-agent context (so it can call AskUserQuestion for judgment rendering); the executor runs in isolated subagent context (so deterministic mechanical work doesn't bloat main-agent).

### D2: LLM-extract at runtime from PRD §2 prose

The writer skill LLM-extracts each PRD §2 acceptance criterion at runtime into either a bash check (mechanical) or a JUDGMENT flag (subjective). No structured-schema burden on PRD authors; existing PRDs work as-is. Failed extractions return `EXTRACT_FAILED` and are surfaced as judgment Qs (same handling as JUDGMENT rows). Trade-off: non-determinism at the margins (LLM might extract slightly different bash across runs) accepted in exchange for zero template burden.

### D3: qa-tester subagent walks criteria sequentially

The executor walks the structured plan one row at a time per-criterion. Per-criterion attribution makes failure debugging cleaner than batched bash. Tool boundaries: Read (read files for inspection), Bash (run grep/ls/exit-code checks), Grep (pattern matching). NO Agent (no nested dispatch). NO AskUserQuestion (not available to subagents per tool-boundary architecture). NO Write/Edit (executor only reads + checks, never modifies).

### D4: Plan persisted as PRD comment

The writer posts the structured QA-plan as a comment on the PRD issue before dispatching the executor. Audit trail + re-runnability: re-runs reference the same plan; if PRD §2 has changed since plan generation, the writer regenerates. Plan structure: Markdown table — `criterion # | extracted bash check or "JUDGMENT" | expected result`.

### D5: Auto-close PRD on all-PASS + all-judgment-ACCEPT

The writer auto-closes the PRD when all mechanical checks PASS and the user accepts all judgment Qs via AskUserQuestion. Preserves [ADR-0003](0003-autonomous-pipeline-with-critics.md) D4 (terminal human checkpoint) at the JUDGMENT layer ONLY; mechanical layer is automated. Human role refined: judge subjective outcomes, not execute grep commands. On any FAIL, the writer surfaces verdict via AskUserQuestion with options accept-FAIL / reopen-for-fix / cull-as-won't-fix.

### D6: Tier 2 (agentic semantic QA per #57) deferred to future PRD

Tier 2 ships a content-quality-critic-style subagent that reads shipped artifacts and produces semantic verdicts (e.g., "is the distilled .md content actually useful?"). Distinct concern from Tier 1's mechanical execution. Future PRD will scope; this ADR explicitly excludes.

### D7: Tier 3 (UI/browser QA per #57) deferred — no UI yet

Project has no UI surface; Tier 3 (browser/computer-use UI testing) becomes relevant when a UI is added. Future PRD will scope when applicable.

### D8 (bootstrap-mode per [ADR-0004](0004-bypass-prevention.md) D2)

The new `/qa-plan` + `qa-tester` pattern binds **FORWARD from slice-1 merge**. No retroactive re-QA of closed PRDs (1-13 + 147 closed before this ADR ships). Closed PRD #147 used as slice-1 dogfood ONLY (verification artifact, not enforcement). Future PRDs ship → new pattern applies. Future blocking variants (e.g., a reviewer rule requiring qa-tester PASS before merge) would require their own bootstrap-mode policy in the introducing ADR; this ADR does NOT pre-emptively gate any merges.

### D9: ADR-0008 D7 6-critic-cap honored

`qa-tester` is a GENERATOR role (deterministic test runner — runs bash checks against a structured plan), NOT an adversarial critic. The 6-critic-cap meta-rule from [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 is unaffected. Project subagent count moves from 8 (6 critics + 2 generators: slicer + implementer) to 9 (6 critics + 3 generators: slicer + implementer + qa-tester). Critic count stays at 6.

### D10: Relationship to [ADR-0003](0003-autonomous-pipeline-with-critics.md) D4 (terminal human checkpoint)

The human checkpoint is REFINED, not removed: mechanical work automated; judgment work preserved via AskUserQuestion in main-agent context. The "5 min user effort" dogfood metric on PRD #147 (vs projected 80 min for the old 16-test flat checklist) is the design intent operationalized — humans judge subjective outcomes, agents handle deterministic verification.

## Consequences

### Positive

- **PRD-close cycle time reduced ~16x** — from ~80 min (16-test manual) to ~5 min (mechanical-auto + judgment) per the PRD #147 dogfood.
- **Human role sharpened** — humans judge subjective quality only; never execute grep commands they could automate.
- **Zero template burden** — existing PRD-template prose works as-is; D2 LLM-extract handles it.
- **Honors 6-critic-cap (ADR-0008 D7)** — qa-tester is generator-role, not critic.
- **Re-runnable** — D4 plan persisted as PRD comment means re-runs use the same deterministic plan.
- **Preserves /qa-plan invocation surface** — backward-compat with /ship + user habits; only the skill body changes.
- **Sets foundation for Tier 2 + 3** — D6/D7 carve out clean future-PRD scoping.

### Negative / Accepted

- **LLM-extract non-determinism at the margins** — accepted per D2 trade-off; EXTRACT_FAILED rows surface as judgment Qs cleanly.
- **9th subagent** — qa-tester adds to file count; mitigated by generator role + clear specialization.
- **JUDGMENT-row rendering format is implementer judgment in slice 1** — open question deferred to slice-1 acceptance per PRD #6 OQ.
- **Auto-close on all-PASS may surprise users who expect always-explicit-close** — accepted; future config option if needed.
- **No retroactive coverage of closed PRDs (1-13 + 147)** — accepted per D8 bootstrap-mode; closed PRDs stay closed.

## Alternatives considered

- **Alt-A: Single qa-runner subagent doing both planning + execution** — rejected; conflates concerns; subagents can't call AskUserQuestion so judgment-rendering would still need main-agent involvement; the writer/executor split mirrors the cleaner planner/runner separation the user articulated ("one should write the QA steps and other should execute").
- **Alt-B: Replace `/qa-plan` with a new `/qa-run` skill; deprecate the old name** — rejected; breaking change for `/ship` + user habits; backward-compat preserved per D1.
- **Alt-C: Structured schema in PRD §2 (each criterion has `check: bash ...`)** — rejected per Q3; migration burden on 12 closed PRDs + authoring burden on every future PRD + prose readability suffers + judgment criteria don't fit schema cleanly.
- **Alt-D: prd-critic enforces new schema rule going forward (bootstrap-mode)** — rejected; bigger scope than tier-1 walking-skeleton; LLM-extract works per PRD #147 dogfood evidence; authoring burden upfront.
- **Alt-E: Extend `/ship` step 8 to absorb qa-automation as terminal stage; eliminate `/qa-plan` skill** — rejected; couples qa-automation to `/ship` (orphans for re-QA of failed-and-fixed PRDs); skill surface preserves invocation flexibility.
- **Alt-F: Bundle Tier 1 + Tier 2 (semantic critic) in one PRD** — rejected; tier 1 mechanical-first walking-skeleton respects [ADR-0011](0011-subagent-quality-framework.md) D2 (mechanical-only first; semantic deferred); tier 2 is a distinct concern.
- **Alt-G: Auto-rerun /qa-plan on every PRD §2 edit** — rejected per §3 non-goal; invocation-driven only for tier 1; YAGNI for solo project.
- **Alt-H: Browser/computer-use UI tier 3 in same PRD** — rejected; no UI surface in project; Tier 3 is YAGNI.
- **Alt-I: Promote qa-tester to a critic with adversarial verdict shape** — rejected per D9; qa-tester is deterministic test runner, no adversarial role; would breach ADR-0008 D7 6-critic-cap without justification.
- **Alt-J: Subagent calls AskUserQuestion directly** — rejected; not technically feasible (subagents lack AskUserQuestion in their tool boundary per main-agent-only architecture); writer skill in main-agent renders.

## Open questions deferred

- **JUDGMENT-row rendering format** — slice-1 implementer judgment; slicer-critic should surface in slice-1 acceptance.
- **Auto-close vs always-confirm config option** — future PRD if dogfood shows users want always-explicit-close.
- **Phase 1.5 synthesis integration** — when #153 (Phase 1.5) ships, qa-tester may extend to verify synthesized .md; #153's grill should consider.
- **CI #63 integration** — when CI lands, qa-tester may auto-fire post-merge; deferred to CI PRD.

## Future direction

- **Tier 2 (agentic semantic QA per #57)** — extends this ADR's writer/executor split with a semantic-critic subagent invoked by the writer for JUDGMENT-tagged rows.
- **Tier 3 (UI/browser QA per #57)** — when project grows a UI; ships browser-control MCP integration.
- **CI integration (post-#63)** — qa-tester auto-fires on PR merge → PRD close.
- **Cross-PRD audit** — future PRD; "are all closed PRDs still passing mechanical?" as a periodic sweep.
- **prd-critic schema rule (post-tier-1)** — if LLM-extract proves too non-deterministic in practice, future PRD adds structured-schema option (hybrid mode).

## References

- [ADR-0003](0003-autonomous-pipeline-with-critics.md) D4 (terminal human checkpoint — refined)
- [ADR-0004](0004-bypass-prevention.md) D1 (joint critic gate), D2 (bootstrap-mode policy cited in D8)
- [ADR-0005](0005-output-shape-and-slicing-methodology.md) D1c (GENERATOR trailer reused), D3 (cascade-doc check)
- [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 (6-critic-cap honored per D9)
- [ADR-0011](0011-subagent-quality-framework.md) (audit-subagents rubric the qa-tester.md must pass)
- Backlog [#57](https://github.com/vojtech-stas/project-claude/issues/57) — parent (tiers 2 + 3 future PRDs)
- Closed PRD [#147](https://github.com/vojtech-stas/project-claude/issues/147) — slice-1 dogfood target
