# ADR-0046: Post-PRD codebase-critic + critic-parsimony reframe (retire R-BOY-SCOUT)

- **Status:** Accepted
- **Date:** 2026-06-03
- **Supersedes:** [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 (the "Meta-rule on critic count" — reframed from a critic-*count* cap ["6 critics; a 7th requires an ADR"] to a number-agnostic *parsimony principle*; the justification requirement is preserved and D2 below provides it) + [ADR-0018](0018-boy-scout-reviewer-rule.md) D1–D7 (the R-BOY-SCOUT per-PR discretionary reviewer rule in full — its drift-detection role is replaced by the per-PRD `codebase-critic`; the deterministic rubric content it applied stays available via audit-meta + CI).
- **Extends / honors:** [ADR-0003](0003-autonomous-pipeline-with-critics.md) D1 (the PRD→Slice→PR hierarchy that defines "the last slice") + D2 (the critic-per-stage pattern — extended here to the per-PRD cumulative reflection stage), [ADR-0002](0002-autonomous-merge-policy.md) (the reviewer remains the sole *merge* gate — `codebase-critic` is a pre-review critic, not a second merge gate), [ADR-0004](0004-bypass-prevention.md) D1 (a critic's verdict gating a stage) + D2 (bootstrap-mode), [ADR-0005](0005-output-shape-and-slicing-methodology.md) D1 (the critic verdict template + CRITIC trailer the new critic emits), [ADR-0009](0009-discipline-tightening.md) D3 (asymmetric default-BLOCK disposition), [ADR-0010](0010-implementer-subagent-auto-pipeline.md) D2 (the `/ship` orchestration the last-slice trigger hooks into), [ADR-0011](0011-subagent-quality-framework.md) (the subagent-quality framework the new critic's rubric lives in), [ADR-0017](0017-audit-meta-consolidation.md) + [ADR-0042](0042-github-actions-ci-gate-r4.md) D1 (the *deterministic* drift detectors that remain — `codebase-critic` owns only the judgment layer).

## Context

The user, reviewing the pipeline (2026-06-03 grill, walking up from backlog [#70](https://github.com/vojtech-stas/issues/70)), identified a genuinely uncovered capability. Mapping the existing reflection surface:

- **Detection (mechanical):** `audit-meta` (STRUCT-*/DOCS-*), `audit-subagents` (prompt rubric), `tools/ci-checks.sh` (CHECK 1–6) — deterministic greps/counts.
- **Gating (per-artifact):** the 6 critics (`reviewer`, `prd-critic`, `adr-critic`, `slicer-critic`, `glossary-critic`, `backlog-critic`).
- **Opportunistic capture:** rule #11/#13 — agents capture improvements they trip over while doing their assigned task.

The **uncovered cell** is *systematic, generative, judgment-based macro review*: nobody's job is to look at the **cumulative effect of a whole PRD** on the codebase and ask "are the README/CLAUDE.md references still *semantically* current, has the architecture drifted, what should be refactored?" The `reviewer` judges a single **diff** (micro); the mechanical detectors only catch **deterministic** drift; opportunistic capture is by accident, not by design. [ADR-0018](0018-boy-scout-reviewer-rule.md)'s R-BOY-SCOUT is the closest thing — but it is a *per-PR*, *mechanical*, *touched-files-only* discretionary reviewer rule, and D7 of that ADR explicitly *reserved* a per-PRD cadence relationship for later.

Two grill corrections shaped the design. First, the user reframed the **critic-count cap** ([ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7): its real intent was never the number "6" — it was *parsimony* ("keep critics few; don't spawn random ones"). A critic that earns its place against a distinct concern was always allowed; the rule front-loaded a number instead of the principle. Second, the user rejected the "force it to be a non-blocking generator to dodge the cap" contortion — once parsimony (not a number) is the gate, the new agent should simply **be a critic** (it can gate). And per-*slice* macro review is wrong: it should fire once per PRD, **at the last slice, before that PR's review**, judging the cumulative change.

## Decisions

### D1: Reframe the critic meta-rule from a count-cap to a parsimony principle (supersedes [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7)

[ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7's "Meta-rule on critic count" is reframed: the gate on adding a critic is **not a number** ("6 critics; a 7th requires an ADR") but a **parsimony principle** — *minimize critics; each must earn its place against a distinct concern that no existing critic's rubric absorbs; adding one requires an ADR that makes that justification explicitly.* The justification requirement (the load-bearing half of D7) is preserved verbatim in spirit; only the count-anchoring is dropped. D2 provides exactly that justification for the `codebase-critic`.

### D2: Introduce the `codebase-critic` (a justified new critic)

A new critic `.claude/agents/codebase-critic.md` is added. **Justification (per D1):** its concern — *macro, codebase-level coherence judged over the cumulative change of an entire PRD* — is absorbed by no existing critic: the `reviewer` judges one slice's diff (micro, per-PR); `prd-/adr-/slicer-/glossary-/backlog-critic` each gate a different artifact; the mechanical detectors only catch deterministic drift. Its rubric (embedded in its body per [ADR-0011](0011-subagent-quality-framework.md)) covers three concerns: (1) **semantic reference/doc currency** — README/CLAUDE.md/ADR references the PRD made stale that a grep cannot detect; (2) **architectural / structural drift** — has the cumulative change diverged from the patterns the relevant ADRs establish; (3) **refactoring opportunities** — concrete dedup/extraction/folder-schema improvements the merged work now reveals.

### D3: Cadence — once per PRD, at the last slice, before that slice's reviewer pass (supersedes [ADR-0018](0018-boy-scout-reviewer-rule.md)'s per-PR cadence)

The `codebase-critic` fires **once per PRD**, when `/ship` ([ADR-0010](0010-implementer-subagent-auto-pipeline.md) D2) detects the **last open slice** of a PRD ([ADR-0003](0003-autonomous-pipeline-with-critics.md) D1 defines the slice set). It reviews the **cumulative PRD change** (the PRD's base..last-slice-HEAD delta) plus the affected docs/ADRs — not one diff. Sequence at the closing slice: implement → **`codebase-critic`** → `reviewer` → merge. The `reviewer` **remains the sole merge gate** ([ADR-0002](0002-autonomous-merge-policy.md) preserved); `codebase-critic` is a pre-review critic that gates PRD-completion, mirroring how `prd-critic`/`slicer-critic` gate their stages — it does not merge.

### D4: Gate semantics — BLOCK on drift, RECOMMEND on refactors

The `codebase-critic` emits two finding severities (mirroring the BLOCK/REC split [ADR-0018](0018-boy-scout-reviewer-rule.md) D4 pioneered, now intelligent rather than mechanical):
- **BLOCK** (must-fix before the PRD closes, standard ≤3-round iterate per [ADR-0004](0004-bypass-prevention.md) D1 / [ADR-0005](0005-output-shape-and-slicing-methodology.md) D1): the PRD *introduced* real drift — a now-false README/CLAUDE.md reference, a broken architectural invariant, an inconsistency the cumulative change created.
- **RECOMMEND** (non-blocking → `captured` issues per rule #11): refactoring / improvement opportunities. These never block a good PRD; the user/`backlog-critic` decide downstream.

Default-conservative per [ADR-0009](0009-discipline-tightening.md) D3: BLOCK only PRD-*introduced* regressions; optional cleanups always RECOMMEND. Round-3 BLOCK escalates via `needs-human` like every other critic.

### D5: Retire R-BOY-SCOUT; deterministic drift stays mechanical (supersedes [ADR-0018](0018-boy-scout-reviewer-rule.md) D1–D7)

R-BOY-SCOUT is removed from `.claude/agents/reviewer.md`; the `codebase-critic` is its intelligent, per-PRD successor (fulfilling the per-PRD cadence relationship [ADR-0018](0018-boy-scout-reviewer-rule.md) D7 reserved). The **deterministic** rubric content R-BOY-SCOUT applied at PR time stays caught by `audit-meta` + `tools/ci-checks.sh` ([ADR-0017](0017-audit-meta-consolidation.md) + [ADR-0042](0042-github-actions-ci-gate-r4.md) D1) — only the *judgment* layer moves to the new critic. This also **collapses backlog [#70](https://github.com/vojtech-stas/issues/70)** ("code-improver + improver-critic pair"): its generative refactoring-proposal concern is D4's RECOMMEND output, so #70 needs no separate generator/critic pair.

### D6: Bootstrap-mode (per [ADR-0004](0004-bypass-prevention.md) D2)

Binds forward from merge. PRDs already in flight (sliced before this ADR's ship slice merges) are not retroactively macro-reviewed; the `codebase-critic` applies to PRDs whose last slice closes from this ADR's merge onward.

## Consequences

**Positive:**
- Fills the one genuinely-uncovered reflection cell (systematic, judgment-based, per-PRD macro review) with a single coherent critic.
- One home for "is the codebase still coherent after this work," fired once per feature with judgment — instead of a mechanical rule bolted onto every slice's reviewer.
- The critic meta-rule now states its real intent (parsimony), so future critic decisions argue the principle, not a number.
- Collapses #70 (no separate improver pair) and absorbs R-BOY-SCOUT's intent (no per-PR mechanical drift-rec), net-simplifying the rule surface even while adding a critic.

**Negative:**
- A 7th critic to maintain. Mitigated: it earns its place (D2) and replaces R-BOY-SCOUT + #70's proposed pair, so the *net* agent/rule count barely moves.
- The `codebase-critic`'s remit is broad (3 concerns); its rubric must be scoped tightly to avoid sprawl. Mitigated: the rubric is concrete and the BLOCK bar is narrow (PRD-introduced drift only).
- Per-PRD macro review adds one critic pass at the closing slice. Mitigated: once per PRD, not per slice.

**Neutral:**
- Runtime touch: new `.claude/agents/codebase-critic.md`; `.claude/agents/reviewer.md` (drop R-BOY-SCOUT); `.claude/skills/ship/SKILL.md` (last-slice trigger); `CLAUDE.md` (parsimony meta-rule + I6 + critic list + Map). `decisions/0046-*.md` + `decisions/README.md` (ADR + index + Status flips on ADR-0008/ADR-0018). Mechanical detectors (audit-meta, ci-checks.sh) unchanged.

## Alternatives considered

- **Alt-A (chosen): one per-PRD `codebase-critic` (gates drift, recommends refactors), reframe the parsimony rule, retire R-BOY-SCOUT.**
- **Alt-B: keep the agent a non-blocking generator to preserve the "6-critic cap."** Rejected (grill): the cap's real intent is parsimony, not the number 6; contorting the design to dodge a misread number is worse than reframing the rule and letting a justified critic gate.
- **Alt-C: bake macro review into the existing `reviewer`.** Rejected (grill): cadence mismatch (reviewer is per-PR/per-slice; macro wants per-PRD) and blocking-semantics mismatch (would block a good slice for unrelated codebase drift); overloads the reviewer's single responsibility.
- **Alt-D: two new agents firing per-PR (micro + macro in parallel).** Rejected (grill): the micro one already exists (the reviewer); running full macro analysis every slice is expensive + repetitive and re-scans the whole codebase per PR.
- **Alt-E: keep R-BOY-SCOUT and add the macro-critic alongside (coexist).** Rejected (grill): two overlapping drift mechanisms; R-BOY-SCOUT's per-PR mechanical recs are precisely the thing the user wanted replaced by judgment.
- **Alt-F: build #70 as a separate code-improver + improver-critic pair.** Rejected: 3 of its 4 candidate rubric criteria are already covered downstream + the proposal flows through the existing PRD→slice→PR gauntlet anyway; the generative half folds cleanly into D4's RECOMMEND output of one critic.

## References

- Grill 2026-06-03 (walking up from backlog [#70](https://github.com/vojtech-stas/issues/70)). Closes [#70](https://github.com/vojtech-stas/issues/70) (collapsed into this critic). Backlog [#47](https://github.com/vojtech-stas/issues/47) (R-BOY-SCOUT's origin; its reserved per-PRD cadence half is fulfilled here). Backlog [#142](https://github.com/vojtech-stas/issues/142) (R-BOY-SCOUT-era audit-rule calibration — already CLOSED; the DOCS-5/6/7 rules it tracked live in audit-meta independently and are unaffected by R-BOY-SCOUT's retirement).
- [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 (superseded — meta-rule reframed). [ADR-0018](0018-boy-scout-reviewer-rule.md) D1–D7 (superseded — R-BOY-SCOUT retired). [ADR-0003](0003-autonomous-pipeline-with-critics.md) D1 + D2. [ADR-0002](0002-autonomous-merge-policy.md) (reviewer sole merge gate — preserved). [ADR-0004](0004-bypass-prevention.md) D1 + D2. [ADR-0005](0005-output-shape-and-slicing-methodology.md) D1. [ADR-0009](0009-discipline-tightening.md) D3. [ADR-0010](0010-implementer-subagent-auto-pipeline.md) D2. [ADR-0011](0011-subagent-quality-framework.md). [ADR-0017](0017-audit-meta-consolidation.md) + [ADR-0042](0042-github-actions-ci-gate-r4.md) D1 (deterministic detectors retained).
- `.claude/agents/codebase-critic.md` (new), `.claude/agents/reviewer.md`, `.claude/skills/ship/SKILL.md`, `CLAUDE.md`.
