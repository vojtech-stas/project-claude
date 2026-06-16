# 0071 — Make-real pivot: operational honesty, fleet economics retired, two-tier dormant

- **Status:** Accepted
- **Date:** 2026-06-16
- **Supersedes:** ADR-0069 D1 (effort classes in dispatch templates), ADR-0069 D2 (reassurance-rerun detector), ADR-0069 D3 (evidence-gated model tiering — the change-gate discipline for tier changes), ADR-0069 D4 (DORA-style instability panel) — collectively the fleet-economics machinery, removed as team-scale premature
- **Extends:** ADR-0070 (marks its two-tier delivery DORMANT, not operational — the decisions stand, the implementation is deferred); ADR-0064 D4 (R-SENSITIVE per-PR ack: now explicitly advisory during the single-branch interim; the promotion-time tripwire per ADR-0070 D4 restores the structural human gate when two-tier is wired); ADR-0027 D1 (mandatory explicit `model:` frontmatter invariant — RETAINED); ADR-0067 D5 (critic golden-set evals — RETAINED)

## Context

The make-the-core-real program (PRD #836) was launched after the wave-4 post-mortem identified a gap between ceremony and execution: this fleet had authored 70 ADRs, 5 waves of CI/health machinery, and an explicit "two-tier autonomous delivery" strategy (ADR-0070) — while merging every PR straight to `main` from a single-branch workflow. The ceremony had outpaced the execution. The reset: make EXISTING mechanisms operational and HONEST before adding new ones.

Three specific failures were corrected in this program:

**Fleet economics (ADR-0069):** The EFFORT-BUDGET, REASSURANCE-RERUN, DECLARED-PARITY, and DORA-PANEL health rows were authored and registered but never had real data. They measured fleet-wide dispatch patterns appropriate for a multi-human team operating many autonomous pipelines simultaneously — this project has one operator and one pipeline. Shipped: the `model:` frontmatter invariant (ADR-0027 D1) and the critic evals (ADR-0067 D5) are the actual useful residue; the dispatch-economics layer was cargo cult.

**Two-tier delivery (ADR-0070):** The ADR was accepted (2026-06-16). The implementation (develop branch, promote.sh, RELEASE-READY gate, BRANCH-TOPOLOGY enforcement) was partially stubbed in the topology/release-ready slice (#845) but was never fully wired. The health checks say "full implementation in slice 2 / slice 7" which never landed. The checks and promote.sh are inert scaffolding.

**Measurement honesty (multiple slices #846/#849/#851):** The stale-server auto-restart, UTC beacon timestamps, the ok-beacon fix, HOOK-LIVENESS detection, and RULE-COVERAGE honest counting were the actual operational wins of this wave — each a standing registered check. The dashboard now tells the truth about the fleet's state; the fleet-economics and two-tier machinery should tell the truth about theirs (dormant/deferred).

This ADR records the 2026-06-16 strategic reset: tighten what exists; defer what isn't ready to be real.

## Decisions

### D1 — make-real posture

The program's disposition is to make existing mechanisms genuinely operational and honest before adding new ones. Ceremony scales to change risk. A new check, rule, or mechanism earns its place by observing something real; if it cannot yet observe anything real, its registered check must say so honestly (WARN with a dormant/deferred label) — not imply readiness via a detail string that presupposes a shipped implementation.

**Enforcement (advisory):** The measurement-honesty health rows that ship in this wave (RELEASE-READY and BRANCH-TOPOLOGY with explicit dormant detail strings, HOOK-LIVENESS, RULE-COVERAGE honest counting) are the direct mechanization of this posture. This decision is tagged `(advisory)` per CLAUDE.md rule #23 — the make-real posture is a meta-principle with no single deterministic check; the wave's health rows and tests are evidence, but the posture itself is not backed by a dedicated adr-critic rule.

### D2 — fleet economics retired

The EFFORT-BUDGET, REASSURANCE-RERUN, DECLARED-PARITY, and DORA-PANEL machinery introduced by ADR-0069 is removed. These four decisions (ADR-0069 D1–D4) are superseded:

- ADR-0069 D1 (effort classes in dispatch templates): removed. The advisory budget and effort_class event field are not providing signal for a single-operator repo.
- ADR-0069 D2 (reassurance-rerun detector): the detector row is removed. The no-reassurance-rerun prompt line is retained in implementer.md (it costs nothing to leave; the operationally useful version of the rule is already there as a CLAUDE.md constraint via ADR-0069 D2's prompt lines). The registered health check row is removed.
- ADR-0069 D3 (evidence-gated model tiering — the tier-change gate and parity row): removed. The FRONTMATTER-COVERAGE row (the ADR-0027 D1 invariant — mandatory explicit `model:` frontmatter) is RETAINED. The tier-change PR gate and DECLARED-PARITY check are removed as the eval infrastructure is too immature to gate on meaningfully.
- ADR-0069 D4 (DORA instability panel): removed entirely. No deploy target; the repo-local proxies added noise without signal.

Retained from the ADR-0069 wave: the `model:` frontmatter invariant (ADR-0027 D1) which has real enforcement via FRONTMATTER-COVERAGE; the critic golden-set evals (ADR-0067 D5) which have a working runner and fixture set.

**Enforcement:** The four removed check IDs must be absent from CHECK_REGISTRY in dashboard/health.py. Mechanized by `tests/test_fleet_economics_removal_854.py` (committed in slice #854, passes on the current codebase).

### D3 — R-SENSITIVE advisory in the single-branch interim

ADR-0064 D4 introduced R-SENSITIVE as a per-PR human-ack gate on enforcement-path PRs, with deferred activation. ADR-0070 D4 then superseded it, moving the human gate to the promotion-time meta-tripwire. However, ADR-0070's promotion mechanism is DORMANT (D4 below). This creates a gap: the per-PR blocking gate was retired but its replacement is not yet operational.

Resolution (#848): during the dormant interim, R-SENSITIVE is ADVISORY — it reports enforcement-path PRs but does not block. When ADR-0070's two-tier delivery is fully wired (develop branch + promote.sh operational), the promotion-time meta-tripwire automatically becomes the active human gate, and R-SENSITIVE remains advisory permanently (the promotion tripwire is the structural replacement, covering a strictly larger surface per ADR-0070 D4).

**Enforcement (advisory):** The R-SENSITIVE reviewer rule in `.claude/agents/reviewer.md` is annotated advisory (not BLOCK). The detector row reports advisory counts. The promotion-time meta-tripwire (ADR-0070 D4) becomes the enforcing mechanism when two-tier is wired. This decision is tagged `(advisory)` per CLAUDE.md rule #23 because full enforcement requires the dormant ADR-0070 machinery.

### D4 — two-tier is DORMANT

ADR-0070's `develop` branch, `tools/promote.sh`, RELEASE-READY gate conditions, and BRANCH-TOPOLOGY enforcement are retained as inert scaffolding and are NOT operational. They must not imply readiness:

- `dashboard/health.py` RELEASE-READY and BRANCH-TOPOLOGY detail strings must say "dormant (deferred per ADR-0071 D4)" rather than "stub — full check in slice N".
- The ADR-0070 index row in `decisions/README.md` is annotated "Dormant per ADR-0071 D4 (deferred, not operational)".
- `tools/promote.sh` is retained as scaffolding and is not deleted.
- `origin/develop` does not yet exist; the single-branch workflow remains.

Revisit when the operator prioritizes the two-tier implementation as a standalone PRD.

**Enforcement:** The RELEASE-READY and BRANCH-TOPOLOGY registered health checks must return a detail string containing "dormant". Mechanized by `tests/test_make_real_pivot_856.py` (this slice).

### D5 — measurement honesty restored

The following operational wins from the make-the-core-real wave are recorded as the standing honest state:

- **Stale-server auto-restart** (#846): the `session-start.sh` hook restarts the dashboard server if its PID's start-time differs from the last root-sync timestamp, preventing phantom proofs from stale worktree servers.
- **UTC beacon timestamps** (#846): the ok-beacon now emits UTC ISO-8601 timestamps rather than local time, enabling cross-timezone drift comparisons.
- **HOOK-LIVENESS** (#849): a registered check detects when the hook layer has gone silent (no beacon within the configured dark threshold), catching total-dark failure modes that per-hook error reporting misses.
- **RULE-COVERAGE honest counting** (#851): the RULE-COVERAGE health row now counts only numbered rules with a verified enforcement mechanism, not all rule mentions in CLAUDE.md. Advisory rules tagged `(advisory)` are excluded from the denominator, preventing inflated coverage claims.

Each is a registered health check (STALE-SERVER, HOOK-LIVENESS, RULE-COVERAGE respectively); `check_hook_liveness` and `check_rule_coverage` are in the CHECK_REGISTRY.

**Enforcement:** Each is a registered health check (enforcement per ADR-0064 D3). The checks' presence in CHECK_REGISTRY is verifiable via `python dashboard/health.py --list`.

## Consequences

- The dashboard is honest: two health checks say "dormant" rather than "stub — full impl in slice N"; fleet-economics checks are removed rather than reporting stale/empty data.
- The single-branch workflow continues; there is no `develop` branch; all PRs target `main`.
- R-SENSITIVE is advisory, matching the actual enforcement gap during the dormant interim.
- The `model:` frontmatter invariant (ADR-0027 D1, FRONTMATTER-COVERAGE) and critic golden-set evals (ADR-0067 D5) survive as genuinely useful residue of the fleet-economics and regression-memory waves.
- ADR-0069 D1–D4 are superseded; ADR-0070 stands (its decisions are sound; its implementation is deferred).
- Future two-tier implementation will supersede the dormant annotations in D4 when prioritized.

### Enforcement (rule #23)

Per decision: D1 — tagged `(advisory)` per rule #23; direct evidence is the wave's health rows (RELEASE-READY and BRANCH-TOPOLOGY dormant detail strings, HOOK-LIVENESS, RULE-COVERAGE honest counting); no dedicated adr-critic rule backs this meta-principle; D2 — the four removed check IDs' absence from CHECK_REGISTRY (mechanized by existing test_fleet_economics_removal_854.py); D3 — the R-SENSITIVE advisory annotation in reviewer.md (mechanized by existing test_rsensitive_advisory_848.py) tagged `(advisory)` per rule #23; D4 — the dormant detail strings in RELEASE-READY and BRANCH-TOPOLOGY (mechanized by test_make_real_pivot_856.py); D5 — each named check present in CHECK_REGISTRY (verifiable via `python dashboard/health.py --list`).

## Alternatives considered

- **Delete RELEASE-READY and BRANCH-TOPOLOGY entirely:** rejected — the checks are a useful signal future implementers will need when wiring two-tier; removing them loses the scaffolding and forces a re-discovery. "Dormant" is honest without destructive.
- **Ship the full ADR-0070 two-tier implementation now:** rejected — the operator's stated priority (2026-06-16 grill) is operational honesty of what exists, not new delivery infrastructure. The implementation is a standalone PRD when prioritized.
- **Keep fleet-economics rows but mark them advisory:** rejected — advisory rows that observe nothing real add noise to the health dashboard without providing actionable signal. Removal is more honest than an advisory row with no data.
- **Activate R-SENSITIVE as a hard BLOCK while two-tier is dormant:** rejected — this would block all enforcement-path PRs (CI, hooks, settings.json) in an autonomous workflow with no promotion gate operational; the friction cost exceeds the safety gain while the tripwire is dormant.
- **New "dormant-machinery" health check pattern as a first-class concept:** rejected — YAGNI; the two specific checks' dormant detail strings are sufficient; a meta-check over dormant checks adds a layer without adding signal.

## References

- ADR-0069 D1–D4 (superseded fleet-economics decisions), ADR-0070 (two-tier, marked dormant), ADR-0064 D3 (health.py as the check registry), ADR-0064 D4 (R-SENSITIVE, now advisory per D3 above), ADR-0027 D1 (model: invariant retained), ADR-0067 D5 (critic evals retained), ADR-0004 D2 (bootstrap-mode), post-v2 make-the-core-real program grill (2026-06-16); issues #846 #848 #849 #851 #854 #856.

## Propagation

Tracked files citing the superseded ADR-0069 D1–D4 decisions or implying two-tier is operational, with disposition:

- `dashboard/health.py` — **update-in-this-wave**: RELEASE-READY and BRANCH-TOPOLOGY detail strings changed to say "dormant (deferred per ADR-0071 D4)"; fleet-economics check IDs were removed in slice #854 (already landed).
- `decisions/README.md` — **update-in-this-wave**: ADR-0069 status cell annotated "D1–D4 superseded by ADR-0071 D2"; ADR-0070 status cell annotated "Dormant per ADR-0071 D4 (deferred, not operational)"; new ADR-0071 row added.
- `CLAUDE.md` — **grandfather**: verified clean — no ADR-0069/ADR-0070 or two-tier/fleet-economics references in rule #4 or Map; no edit needed.
- `.claude/agents/reviewer.md` — **grandfather**: R-SENSITIVE is already annotated advisory per slice #848 (already landed before this ADR is written); the existing annotation satisfies the D3 requirement. No edit needed.
- `.claude/skills/ship/SKILL.md`, `.claude/skills/build/SKILL.md`, `.claude/hooks/session-start.sh`, `tools/promote.sh` — **grandfather**: references to `develop`/`main` promotion were never fully wired; the code is inert. Updating references is a task for the full two-tier implementation PRD, not this pivot ADR. The dormant annotations in the health checks are the honest signal.
- `tests/test_make_real_pivot_856.py` — **created-in-this-wave**: regression tests for D4 dormant detail strings + ADR-0071 structure.
- `tests/test_fleet_economics_removal_854.py` — **landed in slice #854**: regression tests for D2 removed check IDs (already passing).
- `tests/test_rsensitive_advisory_848.py` — **landed in slice #848**: regression tests for D3 advisory R-SENSITIVE (already passing).
