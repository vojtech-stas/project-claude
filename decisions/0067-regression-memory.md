---
id: "ADR-0067"
status: "accepted"
supersedes: []
superseded_by: []
scope: "regression"
rule_ids:
  - "REG-001"
  - "REG-002"
  - "REG-003"
---
# 0067 — Regression memory: tests in CI, test-before-fix, capture riders, quarantine, golden critic evals

- **Status:** Accepted
- **Date:** 2026-06-12
- **Extends:** ADR-0042 D1 (the mechanical-CI gate — its check script gains a test-suite stage); ADR-0024 D3 (the 3-section capture body — code-defect captures gain a regression-test rider on the FIXING side); ADR-0063 D3 (the capture-time evidence-first ordering rider, STOP→PRESERVE→DIAGNOSE→FIX→GUARD→RESUME — this ADR adds the analogous proof obligation at the FIX stage of that sequence: the failing test is preserved before the fix is written)

## Context

The fleet has no regression memory. Measured: 24–34% of merged PRs are fix-type churn; documented defects get re-implemented (the events.py interleave bug shipped twice — its second author wrote a docstring rationalizing the re-introduction); agents under PASS pressure have "fixed" CI by weakening assertions. There is no tests/ suite, so nothing accumulates: every fix is prose in a closed issue, invisible to the next implementer in a cold worktree. The judgment layer has the same hole twice over: critic prompts changed 14 times this month with zero before/after evaluation, so a prompt regression (a rubric rule accidentally weakened in a sweep) is undetectable until it ships a bad merge — #618's verdict nondeterminism was caught by accident, not instrumentation. Forensic artifacts the decisions layer already cites (`qa-proof/forensics/`, `qa-proof/design/` in ADR-0053) are untracked, so implementers cannot read them. The two memory systems — code-side regression tests, judgment-side golden evals — ship together because the second is the stated precondition for model tiering (co-submitted fleet-economics ADR) and both are consumed by the same CI/registry plumbing.

## Decisions

### D1 — tests/ suite wired into CI

A `tests/` directory (pytest) becomes a tracked, CI-executed surface: `tools/ci-checks.sh` gains a test-suite check (runs pytest when tests/ exists; FAIL on test failure; reports collected count), seeded with a regression test for the events.py interleave defect (the twice-shipped bug becomes the founding memory). `qa-proof/forensics/` and `qa-proof/design/` become tracked (ADR-0053 cites them as evidence; untracked evidence is invisible to implementers). A tests-collected registry row (per ADR-0064 D3 the implementation lives in dashboard/health.py) reports count > 0. Per ADR-0004 D2 (bootstrap-mode), binds forward from the suite's merge; no retroactive test-writing sweep for old fixes.

### D2 — R-PROVE: test-commit-precedes-fix-commit for fix-type slices

For fix-type slices (branch `fix/*` or slice issue labeled `root-cause`-derived), /ship first dispatches a blind test-author whose only deliverable is the failing reproduction test committed to the PR branch; the implementer then makes it pass. The reviewer gains R-PROVE: on fix-type PRs, the test-touching commit MUST precede the fix commit in branch history (bias isolation as git-history sequencing — mechanically checkable), and the PR body must show the fails-before output. Non-code fixes (docs, prompt wording) are exempt and say so in the PR body. Per ADR-0004 D2, binds forward from the single PR that lands R-PROVE in `.claude/agents/reviewer.md` (the ship-template change rides in the same PR — one unambiguous activation point).

### D3 — Rule-#13 regression rider

CLAUDE.md rule #13 gains one rider sentence: when a root-cause capture documents a CODE defect, the fixing PR MUST include a regression test that fails before and passes after the fix. The measurement (registry row): % of closed `root-cause`-labeled code-defect captures whose closing PR touches `tests/` — honest grandfathered bucket for captures closed before this merge. Per ADR-0004 D2, binds forward; the rider ships in the same PR as its check (rule #23).

### D4 — Flaky quarantine with SLA

A tracked `tests/quarantine.txt` lists quarantined test ids: quarantined tests run-and-log but never gate; every entry REQUIRES a companion `captured` issue reference on its line; entries older than 30 days are SLA breaches. Deleting a failing test without quarantine+capture is the named anti-pattern (that is how agents "fix" CI). Registry row: quarantine size + oldest-entry age (red on SLA breach). Per ADR-0004 D2, binds forward from the suite's merge.

### D5 — Golden-set critic evals (scheduled, headless)

`tests/evals/` holds per-critic fixture cases (must-BLOCK and must-APPROVE artifacts + expected VERDICT; fixtures live outside production data stores per rule #21), starting with the highest-traffic critics (reviewer, prd-critic, slicer-critic) at ~6–10 cases each and growing by accretion; ~30% of cases are held out and scored only when that critic's prompt changes. A `tools/` runner invokes `claude -p` per case, parses the fenced CRITIC trailer, and emits a per-critic pass rate. Cadence: on-demand before/after any critic-prompt change and at wave boundaries — NOT per-PR (cost). Registry row per evaluated critic: last-run timestamp + pass rate (stale > 14 days or rate drop → WARN/FAIL). Per ADR-0004 D2, binds forward; unevaluated critics report an honest no-baseline bucket, not a fake rate.

## Consequences

- Fixed defects stay fixed (or their regression is one CI run away from detection); fix-type PRs carry bias-isolated proof; flaky tests get a governed lane instead of deletion; critic-prompt changes get a before/after instrument — and model tiering gains its evidence precondition.
- CI gets slower (one pytest stage) and fix-type slices gain one dispatch (the blind test-author); eval runs cost real `claude -p` tokens, which is why cadence is on-change, not per-PR.

### Enforcement (rule #23)

Deterministic, per decision: D1 — the ci-checks test stage + the tests-collected registry row; D2 — R-PROVE (reviewer rubric; commit-order mechanically checkable) + the test-ordering registry row (% fix-type PRs with test-first ordering); D3 — the rider's registry row (% code-defect captures with test-touching fix PRs); D4 — the quarantine SLA registry row; D5 — the per-critic eval rows. Parsimony — mechanisms considered: R-TESTS already requires tests on PRs but judges presence, not ordering or regression linkage (verified against the reviewer rubric); CHECK 9 exercises registry checks, not arbitrary code paths; the wave-2 critic-health row measures live first-pass APPROVE rates but cannot distinguish prompt regression from artifact quality (evals isolate the prompt variable with fixed artifacts); all five land in existing surfaces (ci-checks stage, reviewer rubric, CLAUDE.md rider, registry rows, tools/ runner) — no new agent. Shadow: re-implemented defects, biased after-the-fact tests, deleted-not-quarantined flakes, silent critic-prompt rot.

## Alternatives considered

- **Per-PR eval runs:** rejected — token cost scales with merge rate; the failure mode evals catch (prompt regression) only occurs when prompts change, so on-change cadence covers it.
- **Hard CI gate on eval pass rates:** rejected — eval fixtures are imperfect proxies; a WARN/FAIL health row + before/after discipline informs humans without deadlocking the autonomous lane on a fixture artifact.
- **Mutation testing now:** rejected (deferred) — nothing to mutate until the suite matures; recorded in the synthesis as a revisit-in-one-quarter item.
- **Retroactive test sweep over closed fixes:** rejected — bootstrap-mode (ADR-0004 D2); the founding seed is the one defect with proven recurrence.

## References

- ADR-0042 D1 (CI gate), ADR-0024 D3 (capture body), ADR-0063 D3 (evidence-first), ADR-0053 (forensics/design artifacts cited as evidence), ADR-0064 D3 (single-source registry hosts the new rows), ADR-0004 D2 (bootstrap-mode), issues #730 #618, workflow-v2 synthesis §B16/§B17 (2026-06-12).
- Numbering note: co-submitted with the hygiene/session-start ADR and the fleet-economics ADR (the two numbers above it) in this wave's joint gate; all three ship together in slice 1 per ADR-0003 D8, keeping the sequence contiguous at merge.
