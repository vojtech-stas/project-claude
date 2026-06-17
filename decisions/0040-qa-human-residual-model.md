---
id: ADR-0040
status: accepted
supersedes:
  - ADR-0020
superseded_by: []
scope: verification
rule_ids:
  - VER-004
  - VER-005
  - VER-006
---
# ADR-0040: QA human-residual model — machine maxes coverage, one async human-check

- **Status:** Accepted
- **Date:** 2026-06-01
- **Supersedes:** [ADR-0020](0020-qa-automation-writer-executor.md) D10 (the ADR-0003 D4 terminal-checkpoint refinement — "the human checkpoint is REFINED, not removed: judgment work preserved via AskUserQuestion in main-agent context"; this ADR further refines that framing — the judgment checkpoint moves from synchronous plan-time `AskUserQuestion` to the async `/qa-review` skill, still main-agent, still refined-not-removed) and the all-judgment-ACCEPT clause of [ADR-0020](0020-qa-automation-writer-executor.md) D5 (PRD auto-close no longer waits on synchronous human judgment).
- **Extends:** [ADR-0025](0025-qa-tester-ui-mode-playwright.md) D3 (LLM-judge verdict shape — PROVISIONAL_PASS becomes the residual signal) + [ADR-0037](0037-production-verification-gate.md) D2/D3 (the browser route + generator/orchestrator split — the machine gate stays mandatory+blocking; the human residual is additive and non-blocking). Honors [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 (no new critic — `/qa-review` is a skill; `qa-tester` stays a generator).

## Context

The QA pipeline today (ADR-0020) has the writer (`/qa-plan`) render **every** subjective `JUDGMENT` criterion back to the human via `AskUserQuestion` at plan time, and auto-closes the PRD only on all-PASS **and** all-judgment-ACCEPT. In practice this means the human is prompted to confirm many things every time a feature is QA'd — exactly the "I don't have time to go through the QA plan every PR, I'd be testing the whole time" pain the user reported (2026-06-01).

Two asks emerged:
1. **A QA environment as close as possible to a human actually clicking through the app** — verifying the feature *really* works, not just that internal state looks right. The `qa-tester` already has a Playwright browser route (ADR-0025/0037), but in practice it (and the main agent dogfooding it) shortcut to `browser_evaluate`-ing internal JS state instead of driving real clicks and observing the rendered result. The gap is **fidelity + discipline**, not a missing tool.
2. **Exactly ONE distilled "now check this" human step** per feature — instead of the whole plan — surfaced in the rich `AskUserQuestion` card format (recommendation + PRO/CON), cleared on the human's own cadence.

Grill (2026-06-01, Q1–Q8) resolved the model: **the machine attempts to verify everything it honestly can at maximum fidelity; whatever it cannot faithfully judge becomes an asynchronously-queued human residual; the single highest-value residual is surfaced as one "now check this" headline, cleared via a new `/qa-review` skill.**

## Decisions

### D1: The irreducibly-human residual model (supersedes ADR-0020 D10)

The QA executor (`qa-tester`) **attempts every §2 criterion** at maximum fidelity (D5). A criterion the executor **cannot faithfully verify** — it returns `PROVISIONAL` / "uncertain — needs a human eye" (the ADR-0025 D3 verdict, reused as the residual signal) — becomes a **human residual**. The residual is therefore *discovered empirically by attempting*, not *predicted* before the run. The machine cannot over-claim coverage, because it must actually try first. This further refines ADR-0020 D10 (the terminal-checkpoint "refined, not removed" framing) together with D4 below: the human is now asked about a criterion only when the machine genuinely could not settle it — and asynchronously, not at plan time.

### D2: Async, non-blocking human-check queue (supersedes the ADR-0020 D5 all-judgment-ACCEPT clause)

The machine production-verify gate (ADR-0037 D1) stays **mandatory and blocking** — a feature is not "done" without machine `PRODUCTION_VERIFY: PASS` (where PASS = every criterion is machine-PASS or a queued residual; any machine-confident FAIL still blocks per ADR-0037 D5). The **human residual does NOT block** PRD closure or "done". Each residual is posted as a GitHub issue labeled **`needs-human-check`** (linking the PRD + the exact thing to eyeball) — the durable source of truth, mirroring the I5 `needs-human` precedent. The PRD auto-closes on machine-PASS alone; the residual lives on independently for the human to clear when they have time. This honors "no time every PR": work never stalls waiting on the human.

### D3: One headline per feature (zero → silent; many → top-one + de-emphasized extras)

`/qa-plan` ranks the run's residuals and surfaces the **single highest-value** one as the "now check this" headline.
- **Zero residuals** → no human-check at all; clean machine-PASS (the human is not bothered).
- **One** → that one is the headline.
- **Several** → the top-ranked is the headline; the rest are still posted as `needs-human-check` issues but de-emphasized (the human culls them lazily, like the `captured` tier).

Nothing is silently dropped; the human's default load is exactly one item per feature.

### D4: The `/qa-review` clearing skill (no new critic)

A new main-agent skill `/qa-review` pulls open `needs-human-check` issues and presents each as an `AskUserQuestion` card (recommendation + PRO/CON option format, per the user's requested UX). The human's answer records the verdict and closes/relabels the issue (accept → close as verified; reject → relabel for fix / capture a defect). `/qa-review` is a **skill** (it runs in main-agent context because only the main agent has `AskUserQuestion`), not a critic — the [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 6-critic cap is untouched. The synchronous `AskUserQuestion` that ADR-0020 D10 fired at plan time **moves here**, to the human's own cadence.

### D5: qa-tester browser-route fidelity tightening (extends ADR-0025 D3 + ADR-0037 D2)

The `qa-tester` browser route MUST drive **real interaction** — `browser_click` / `browser_type` / `browser_navigate` — and assert on **what a human sees**: `browser_snapshot` (accessibility tree) plus a screenshot as the **primary** proof. `browser_evaluate` is demoted to a **last-resort disambiguator** only — never the primary evidence of a passing check. A check whose only available proof is `browser_evaluate` of internal JS state is reported `PROVISIONAL` (→ a D1 residual), not PASS. This is the "as close as possible to a human clicking through" guarantee, achieved by discipline on existing tools rather than new infrastructure.

### D6: Bootstrap-mode (per [ADR-0004](0004-bypass-prevention.md) D2)

Binds forward from merge. Existing closed PRDs are not retroactively re-QA'd; the new model applies to QA runs from the merge of this ADR's slices onward.

## Consequences

**Positive:**
- The human is asked about **at most one thing per feature**, and only when the machine genuinely couldn't verify it — directly fixing the "testing the whole time" pain.
- The automated environment is honestly faithful (real clicks + observed render), so "machine-PASS" means more.
- The residual is empirical, not predicted — the machine cannot quietly mark something "verified" it didn't really exercise (the eval-shortcut becomes a residual, not a false PASS).
- Durable GitHub-native queue; survives sessions; clears on the human's cadence.

**Negative:**
- The residual queue can accumulate on complex features (mitigated: de-emphasized, lazily culled like `captured`).
- Fidelity depends on the executor's calibration about its own uncertainty (tunable via the LLM-judge prompt; default-conservative → PROVISIONAL on doubt, which is safe — it surfaces to the human rather than false-PASSing).

**Neutral:**
- Net new artifacts: one skill (`/qa-review`), one label (`needs-human-check`). No new critic, no new dependency. Runtime changes: `qa-tester.md`, `qa-plan/SKILL.md`, the new `qa-review/SKILL.md`.

## Alternatives considered

- **Alt-A (chosen):** machine-maxes-coverage + empirical residual + one async headline + real-click fidelity.
- **Alt-B: declared `[human]` tags in the PRD.** Rejected (Q5): front-loads the judgment onto PRD authoring every time; a static guess made before the machine tries; can't adapt when a "machine" criterion turns out unverifiable.
- **Alt-C: keep blocking, just trim to one question.** Rejected (Q2): still prompts the human on every feature — the exact thing to avoid.
- **Alt-D: visual-regression baseline / record-replay harness.** Rejected (Q4): heavy, flaky across machines, YAGNI for a single-user dashboard tool; the residual the human eyeballs covers the nuance a baseline would chase.

## References

- Grill 2026-06-01, Q1–Q8 (irreducibly-human residual / async queue / `needs-human-check` + `/qa-review` / real-click fidelity / empirical classification / one headline / macro-ADR / 2 slices).
- [ADR-0020](0020-qa-automation-writer-executor.md) — D5 (auto-close; all-judgment-ACCEPT clause superseded by D2 here), D10 (terminal human checkpoint, superseded by D1+D4 here), D1/D2/D3/D4 (writer/executor split, preserved).
- [ADR-0025](0025-qa-tester-ui-mode-playwright.md) — D1 (Playwright browser driver), D3 (PASS/PROVISIONAL_PASS/FAIL verdict shape — PROVISIONAL is the residual signal), D4 (PROVISIONAL auto-capture pattern, mirrored by the `needs-human-check` post).
- [ADR-0037](0037-production-verification-gate.md) — D1 (mandatory blocking machine gate, preserved), D2 (browser route, tightened by D5), D3 (generator/orchestrator split, preserved), D5 (machine-FAIL loop, preserved).
- [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 (6-critic cap — honored, no new critic), I5 `needs-human` label precedent.
- `.claude/agents/qa-tester.md`, `.claude/skills/qa-plan/SKILL.md`, new `.claude/skills/qa-review/SKILL.md`, the `needs-human-check` label.
