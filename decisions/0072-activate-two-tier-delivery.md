# 0072 — Activate two-tier delivery: RELEASE-READY and BRANCH-TOPOLOGY lifted from dormant

- **Status:** Accepted
- **Date:** 2026-06-17
- **Supersedes:** ADR-0071 D4 (which marked two-tier DORMANT — that deferral is now ended; `develop` branch exists and the RELEASE-READY gate is wired per PRD #836 wave 5)
- **Extends:** ADR-0070 (the two-tier design, now partially activated); ADR-0067 D1 (the full test suite consumed by RELEASE-READY condition (b))

## Context

ADR-0071 D4 declared the two-tier delivery machinery DORMANT on 2026-06-16, recording that `origin/develop` did not exist and that `promote.sh`, RELEASE-READY, and BRANCH-TOPOLOGY were "inert scaffolding." It required the RELEASE-READY health check to include "dormant" in its detail string, enforced by `tests/test_make_real_pivot_856.py`.

PRD #836 wave 5 (slice #838) has now wired the RELEASE-READY gate: `origin/develop` exists and carries committed history; `dashboard/health.py` `check_release_ready()` evaluates the six conditions from ADR-0070 D2 — (a) CI green on develop HEAD via `ci-checks.sh`, (b) full test suite passes per ADR-0067 D1, (c) production-verify PASS via PROOF-INTEGRITY (slice #839), (d) green-develop streak via `check_green_main()` proxy, (e) zero open `needs-human` items, (f) guardrail-path batch check (stub until slice #840); `tools/promote.sh` gains a RELEASE-READY pre-flight guard that refuses to promote when `verdict != "true"`. The dormant period is over for RELEASE-READY.

BRANCH-TOPOLOGY remains dormant: the PR-merge gate moving from `main` to `develop` (ADR-0070 D1 full activation) and the full branch-protection wiring are not yet complete. This ADR lifts RELEASE-READY only; BRANCH-TOPOLOGY is handled by slice #843 and remains dormant until that slice merges.

ADR-0071 D4's dormant requirement was correct when written. It is now superseded for RELEASE-READY because the precondition it cited ("develop branch does not yet exist") is no longer true.

## Decisions

### D1 — RELEASE-READY lifted from dormant; BRANCH-TOPOLOGY remains dormant

`check_release_ready()` in `dashboard/health.py` is the live six-condition gate per ADR-0070 D2 from the merge of slice #838. The detail string no longer contains "dormant" — instead it reflects the actual evaluation result (all conditions met, first-fail reporting, etc.). `tests/test_make_real_pivot_856.py` `test_release_ready_detail_not_dormant` replaces the prior `assertIn("dormant")` assertion to `assertNotIn("dormant")`, with fast-path env-var injection for offline test runs.

BRANCH-TOPOLOGY remains dormant (the "dormant" detail string is preserved in `check_branch_topology()`); the BRANCH-TOPOLOGY dormant assertion in `test_make_real_pivot_856.py` is unchanged. Full BRANCH-TOPOLOGY activation (PR-merge gate moves to `develop`, branch-protection) completes in slice #843.

**Enforcement:** The RELEASE-READY health check itself (non-dormant verdict) plus `tests/test_make_real_pivot_856.py` `test_release_ready_detail_not_dormant` (which asserts "dormant" is absent from the detail string). BRANCH-TOPOLOGY was subsequently lifted from dormant by slice #843; the regression test `test_branch_topology_detail_not_dormant` now asserts the BRANCH-TOPOLOGY detail string no longer contains "dormant". Shadow: a wired RELEASE-READY gate that continues to self-report "dormant" — masking the real gate-open/held state and presenting a false operational picture to the operator and to promote.sh.

### D2 — Make-real reconciliations carried forward

All of ADR-0071's other decisions are preserved unchanged:

- **D1 make-real posture** — remains the program's operative disposition; RELEASE-READY now demonstrates it by observing something real rather than reporting a dormant stub.
- **D2 fleet economics retired** — the four removed check IDs remain absent from CHECK_REGISTRY; `tests/test_fleet_economics_removal_854.py` continues to enforce this.
- **D3 R-SENSITIVE advisory** — ADR-0071 D3 remains in force. R-SENSITIVE is advisory at PR-time; the human gate is the promotion-time meta-tripwire per ADR-0070 D4. No change from this ADR.
- **D5 measurement honesty** — STALE-SERVER, HOOK-LIVENESS, RULE-COVERAGE honest counting, UTC beacons all remain unchanged.

**Enforcement (advisory):** The continuity of ADR-0071 D1–D3 and D5 is verifiable by running the tests that enforce those decisions (already passing); no new check is needed beyond what those decisions introduced.

### D3 — Staged on `develop`: full two-tier activation completes in subsequent slices

This wave's slices build on `develop` so `main` is protected during the transition. Full two-tier activation requires:

- **slice #843** (BRANCH-TOPOLOGY) — PR-merge gate moves to `develop`, branch-protection wired, BRANCH-TOPOLOGY lifted from dormant.
- **future slices** — all slice PRDs default to `develop` as base; `origin/main` references in guards/CI/dashboard/skills migrate to `origin/develop` (the propagation items from ADR-0070's Propagation section).

This ADR records that RELEASE-READY is the first of those items to go live. The full topology described in ADR-0070 D1 is real when BRANCH-TOPOLOGY is also activated.

**Enforcement:** BRANCH-TOPOLOGY health check (lifted from dormant per slice #843; the check now reports live topology) + `promotion` events in the workflow event log once the promotion gate fires. The regression test `test_branch_topology_detail_not_dormant` in `tests/test_make_real_pivot_856.py` asserts that BRANCH-TOPOLOGY's detail string no longer contains "dormant" (activated in slice #843).

## Consequences

- `check_release_ready()` now evaluates six real conditions. A `verdict="true"` from it is an honest signal that all conditions hold, not a dormant pass-through.
- `tools/promote.sh` will refuse to promote when RELEASE-READY returns `verdict != "true"`, making the promotion gate live.
- `tests/test_make_real_pivot_856.py` lifts both the RELEASE-READY and BRANCH-TOPOLOGY dormant assertions; `test_branch_topology_detail_not_dormant` confirms BRANCH-TOPOLOGY now reports live topology (slice #843).
- ADR-0071 D4 is fully superseded: the "develop branch does not exist" clause is resolved; BRANCH-TOPOLOGY was activated by slice #843, completing the two-tier transition.
- The dashboard now shows an honest RELEASE-READY verdict based on actual condition evaluation, not a dormant stub.

### Enforcement (rule #23)

Per decision: D1 — the RELEASE-READY health check (live gate, non-dormant detail string) enforced by `tests/test_make_real_pivot_856.py` `test_release_ready_detail_not_dormant`; D2 — inherited from ADR-0071 D1–D3/D5 enforcement (advisory; tests for each existing decision remain passing); D3 — `test_branch_topology_detail_not_dormant` (BRANCH-TOPOLOGY lifted from dormant per slice #843) + `promotion` events in the workflow event log. No new rules are introduced by this ADR, so rule #23 requires no new mechanism beyond the cited existing checks.

## Alternatives considered

- **Supersede ADR-0071 in full:** rejected — ADR-0071 D1/D2/D3/D5 remain valid and in force; BRANCH-TOPOLOGY remains dormant; a full supersession would incorrectly imply all of ADR-0071 is overturned. Granular D4-only supersession is the right scope.
- **Add a new dormant-lifted check pattern:** rejected — YAGNI; the RELEASE-READY check's own verdict change is the enforcement; a meta-check over dormant-lifted checks adds a layer without adding signal.
- **Ship BRANCH-TOPOLOGY activation in the same PR:** rejected — BRANCH-TOPOLOGY wiring (PR-merge gate moves from main to develop, branch-protection config) is a separate scope handled by slice #843; conflating it here would exceed the slice's scope and R-LOC cap.
- **Keep RELEASE-READY dormant until full two-tier is wired:** rejected — the `develop` branch exists, the six conditions are implemented, and `promote.sh` is guarded; honest reporting means the check should reflect the real state, not preserve a dormant label for a condition that is no longer true.

## References

- ADR-0071 D4 (superseded for RELEASE-READY), ADR-0070 D1/D2 (two-tier design being activated), ADR-0070 D4 (meta-tripwire, unchanged), ADR-0067 D1 (full test suite in RELEASE-READY condition b), ADR-0001 D8 (immutability + supersession-based ADRs), ADR-0004 D2 (bootstrap-mode), PRD #836 (make-the-core-real program), slice #838 (this slice), slice #843 (BRANCH-TOPOLOGY activation).

## Propagation

- `decisions/README.md` — **update-in-this-PR**: ADR-0071 status annotated "D4 superseded by ADR-0072 (RELEASE-READY activated)"; ADR-0070 status annotation updated to reflect partial activation (RELEASE-READY live, BRANCH-TOPOLOGY still dormant per ADR-0071 D4 until slice #843); new ADR-0072 row added.
- `tests/test_make_real_pivot_856.py` — **updated-in-slice-#838**: `test_release_ready_detail_not_dormant` lifts the dormant assertion; `test_branch_topology_detail_contains_dormant` preserved; `test_release_ready_id_correct` updated with fast-path injection. These are the mechanization of D1.
- `dashboard/health.py` — **updated-in-slice-#838**: `check_release_ready()` is the live six-condition gate; dormant detail string removed.
- `tools/promote.sh` — **updated-in-slice-#838**: RELEASE-READY pre-flight guard added.
- All other ADR-0071 Propagation items — **grandfather**: the ADR-0071 D1–D3/D5 propagation items are unchanged; no edits needed.
