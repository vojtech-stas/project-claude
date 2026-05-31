# ADR-0037: Mandatory production-verification gate after every feature build

- **Status:** Accepted
- **Date:** 2026-05-31
- **Extends:** [ADR-0034](0034-build-orchestrator-and-generated-docs.md) D1 (the `/build` conductor + its `/qa-plan` tail, upgraded here from optional to mandatory-blocking), [ADR-0003](0003-autonomous-pipeline-with-critics.md) D1 (the pipeline), [ADR-0020](0020-qa-automation-writer-executor.md) D9 + [ADR-0025](0025-qa-tester-ui-mode-playwright.md) D6 (the established `qa-tester`-is-a-generator classification this gate relies on). Honors [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 (no new critic) and [ADR-0036](0036-worktree-isolation-all-dispatches.md) (isolated dispatch).
- **Supersedes:** none.

## Context

The autonomous pipeline gates on **code review** (the reviewer's rubric) but never **runs the merged feature in its live environment to confirm it actually works**. A 2026-05-31 session repeatedly shipped work as "merged + reviewer-APPROVED" while the user, opening the running dashboard, found it broken or empty — a Live-tab refresh crash, an empty default session, a topology that was *declared* not *measured*. The `qa-tester` subagent + `/qa-plan` skill exist but sit as an **optional tail** of `/build` ([ADR-0034](0034-build-orchestrator-and-generated-docs.md) D1), so a feature reaches "done" without ever being demonstrably working.

**Root cause:** there is no enforced step between "code merged" and "feature done" that exercises the feature in production and proves it. The user's directive: *"add a loop that forces you to show it's working in production — a tester subagent that tests after any build."* Two design decisions were settled by grill: a **blocking** gate **per feature** (not per slice, not advisory); the **PRD declares** the production expectation and the tester **auto-routes by change type**.

Concretely, the gate needs a machine-readable production expectation in the PRD itself — a new required "Production check:" line in PRD §2 that the gate reads and verifies. Introducing that PRD-authoring convention (and `prd-critic` enforcing it) is part of THIS architectural move, not a separate concern: the gate has nothing to verify against without the declaration. Both travel with the gate; neither stands alone (hence D4 below).

## Decisions

### D1: A mandatory, blocking production-verification gate runs after every feature build

After a feature's slices all merge (the `/ship` loop completes), and as `/build`'s mandatory final stage, a production-verification gate runs before the feature is "done." The orchestrator dispatches `qa-tester` in production-verify mode; **PASS** → feature done + proof surfaced to the user; **FAIL** → the gate BLOCKS and the feature is NOT done. Per-feature granularity (not per-slice: individual slices — especially ADR/docs — are not independently runnable). The gate is additive to, not a replacement for, the reviewer's code review.

### D2: `qa-tester` gains a production-verify mode that auto-routes by change type

`qa-tester` (the existing dual-mode bash/ui executor) is upgraded: given the feature PRD's "Production check" line + the merged diff, it routes by changed-path glob and exercises the feature in its real running context:
- browser-reachable UI (`dashboard/*`) → drive the running app (harness preview / Playwright): perform the declared interaction, assert it renders + **zero console errors** + the declared behavior, capture a screenshot (or DOM/state extraction when the screenshot tool is unavailable);
- `.claude/hooks/*` / `.claude/settings.json` → fire the hook with a synthetic payload, assert the expected log line / exit code;
- skills / `tools/*` → run the command, assert the declared output;
- pure `decisions/*` / docs / README → static check (the declared grep/assertion); no runtime exercise.

It emits a PASS/FAIL verdict + a proof artifact in its GENERATOR trailer ([ADR-0005](0005-output-shape-and-slicing-methodology.md) D1c).

### D3: The gate is orchestrator-enforced — `qa-tester` stays a generator; no 7th critic

The blocking decision lives in the ORCHESTRATOR (`/build` and `/ship`), which reads `qa-tester`'s PASS/FAIL and enforces it. `qa-tester` remains a **generator** and this gate adds **no new critic** — the [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 6-critic cap is intact.

**Why this is not a 7th critic (explicit, because the cap demands the symmetric justification):** [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7's cap governs *adversarial reviewer agents that generate an APPROVE/BLOCK verdict against a rubric on ANOTHER AGENT'S ARTIFACT* — the six are `reviewer` (a PR), `prd-critic` (a PRD), `adr-critic` (an ADR), `slicer-critic` (a slice decomposition), `glossary-critic` (a glossary entry), `backlog-critic` (a backlog item). `qa-tester` in production-verify mode does not review an artifact — it **executes the merged feature in its live environment and reports whether it actually works**. It judges *the world*, not another agent's output. This is the exact generator/critic distinction already established for `qa-tester` by [ADR-0020](0020-qa-automation-writer-executor.md) D9 ("`qa-tester` is a GENERATOR role — a deterministic test runner — NOT an adversarial critic") and reaffirmed by [ADR-0025](0025-qa-tester-ui-mode-playwright.md) D6. The orchestrator's enforcement of the PASS/FAIL outcome makes the orchestrator an *enforcer*, structurally identical to how the `/build`/reviewer machinery enforces R-DOCS-CURRENT ([ADR-0034](0034-build-orchestrator-and-generated-docs.md) D8) — a RULE on existing machinery, not a new critic. A deterministic executor reporting a fact is categorically not an adversarial rubric-reviewer; the cap is therefore not engaged.

### D4: PRDs declare a "Production check"; `prd-critic` enforces it

Every PRD §2 gains a required **"Production check:"** line stating what to exercise + the expected result (for non-runnable features: the static check, or "N/A — docs-only, static: <assertion>"). `prd-critic` gains a rubric check (PC-PRODUCTION-CHECK) that BLOCKs a PRD whose production-check line is missing or non-actionable. The `/to-prd` PRD template includes the line.

### D5: Failure loops back to the implementer, bounded; then escalates

On `qa-tester` FAIL, the orchestrator loops: re-dispatch the implementer to fix the production failure (with the proof of what broke), re-run the gate — up to **3 rounds**, mirroring the critic-loop bound. On the 3rd FAIL, apply `needs-human` + post a summary on the parent PRD (mirrors the reviewer's I5 escalation). The gate must scope its console-error / behavior assertions to the FEATURE (not unrelated noise) so it does not false-FAIL.

### D6: Bootstrap-mode (per [ADR-0004](0004-bypass-prevention.md) D2)

Binds FORWARD from merge (mirrors [ADR-0036](0036-worktree-isolation-all-dispatches.md) D5, [ADR-0034](0034-build-orchestrator-and-generated-docs.md)): a `/build`/`/ship` body or PRD template loaded after this slice merges applies the gate + the required line; in-flight runs use their loaded body; no retroactive sweep of past PRDs. Gate dispatches of `qa-tester` are isolated per [ADR-0036](0036-worktree-isolation-all-dispatches.md).

## Consequences

**Positive:**
- Closes the "merged but doesn't actually work" gap with a hard, visible guarantee — the exact failure mode that frustrated the user.
- Reuses existing machinery (`qa-tester`, `/qa-plan`, `/build` tail) — no new agent, no new critic, no new dependency (Playwright already bootstrapped per [ADR-0030](0030-windows-gitbash-hardening.md)).
- Auto-routing handles the full change-type spectrum, so "test after ANY build" is real, not UI-only.

**Negative:**
- Every feature pays a production-test step (a smoke test, not exhaustive QA — bounded).
- Browser proof can be flaky (the preview screenshot tool timed out on gh-backed pages this session); D2 falls back to DOM/state + console-error assertions, with the screenshot best-effort. A poorly-scoped assertion risks a false-FAIL — D5 mandates feature-scoped assertions.

**Neutral:**
- No new critic (D3); no new dependency; the reviewer's code-review is unchanged. The change is confined to `qa-tester` + the orchestrator skills + `prd-critic` + the PRD template + this ADR + CLAUDE.md.

## Alternatives considered

- **Alt-A (chosen): orchestrator-enforced blocking gate per feature, reusing qa-tester with auto-routing.** Minimal new surface, honors the cap, covers all change types.
- **Alt-B: a new 7th "production-critic" agent.** Rejected: violates the ADR-0008 D7 cap without justification the existing qa-tester can't absorb — it can.
- **Alt-C: per-slice production gate.** Rejected (grill): individual slices (ADR/docs/refactor) aren't independently runnable; heavy overhead.
- **Alt-D: advisory (non-blocking) check.** Rejected (grill): doesn't FORCE proof — the failure mode (claims of "works" without enforced verification) recurs.
- **Alt-E: tester fully auto-infers the test (no PRD declaration).** Rejected (grill): brittle/guessy; may exercise the wrong thing. The PRD-declared "Production check" + auto-routing (D2/D4) is the chosen middle.

## References

- User directive 2026-05-31 (production-test loop + tester subagent); live evidence (Live-tab crash + empty-default-session shipped "merged").
- [ADR-0034](0034-build-orchestrator-and-generated-docs.md) D1 (/build + qa tail this upgrades), [ADR-0003](0003-autonomous-pipeline-with-critics.md) (pipeline), [ADR-0008](0008-workflow-autolog-bootstrap-and-naming.md) D7 (6-critic cap, honored — D3), [ADR-0036](0036-worktree-isolation-all-dispatches.md) (isolated dispatch), [ADR-0030](0030-windows-gitbash-hardening.md) (Playwright bootstrap), [ADR-0005](0005-output-shape-and-slicing-methodology.md) D1c (GENERATOR trailer), [ADR-0004](0004-bypass-prevention.md) D2 (bootstrap-mode).
- `.claude/agents/qa-tester.md`, `.claude/skills/{qa-plan,build,ship,to-prd}/SKILL.md`, `.claude/agents/prd-critic.md`, CLAUDE.md.
