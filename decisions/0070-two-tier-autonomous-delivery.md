# 0070 — Two-tier autonomous delivery: develop/main branches, deterministic promotion gate, meta-tripwire

- **Status:** Accepted (joint APPROVE per ADR-0004 D1; shipped with PRD #836 slice 1)
- **Date:** 2026-06-16
- **Supersedes:** ADR-0064 D4 (R-SENSITIVE per-PR human-ack on enforcement-path PRs — replaced by the promotion-time meta-tripwire defined in D4 below; the human gate moves from per-PR to per-promotion, covering a strictly larger surface)
- **Extends:** ADR-0042 D2 (required-status-checks enforcement — the PR-merge gate moves from `main` to `develop`; `main` gains the promotion gate); ADR-0062 D3 (the green-main pointer / post-merge verification checkpoint with a recorded event — that checkpoint becomes the promotion trigger and the event becomes green-develop); ADR-0058 D3 (worktree-guard ff-sync semantics — the integration target the guard ff-syncs becomes `develop`)

## Context

The fleet now verifies honestly (waves 1–4) but every change still merges straight to `main`, and wave 4 just installed R-SENSITIVE as a *per-PR human-ack* tripwire on enforcement-layer changes — a blocking human gate the operator does not want in the steady-state autonomous run. Two facts shape the redesign. First, the fleet authors its own guardrails (critics, hooks, CI checks, the gates themselves); a fully autonomous fleet that can both modify a gate and ship past it has no real constraint — it can weaken the check that would stop a bad ship, then ship the weakening. No amount of check-strength closes this; only a boundary the fleet cannot edit does. Second, this program's own history shows the mechanical gates are necessary but not sufficient: every wave added checks and every wave still discovered new failure classes the checks lacked (6 root-contamination incidents #804, 2 renderer-coverage misses #811/#833, false-FAIL regexes, the eval-runner crash) — each caught by a human-in-the-loop, not by the gates. The operator's resolution (post-v2 design grill, 2026-06-16): keep the human out of the per-change loop entirely, but make the one boundary the fleet cannot self-edit — promotion to `main` of the guardrail machinery — the single structural tripwire. For this repo `main` is the template future projects clone (recoverable, no external blast radius), which lowers the stakes enough to auto-promote everything *except* the machinery that polices promotion.

## Decisions

### D1 — Two-tier topology: `develop` (autonomous) + `main` (blessed)

Slice PRs target `develop`, not `main`. `develop` is the agent integration branch — fully autonomous, no human gate. `main` is the blessed/production branch, reached ONLY by promotion (D3). Rule #4 is rewritten: "never push directly to `main`; agents merge to `develop` via PR; `main` advances only by the promotion gate." Branch protection / required-status-checks (ADR-0042 D2) enforce on `develop` (the PR-merge gate); `main` is protected by the promotion gate (D2–D4). Per ADR-0004 D2 (bootstrap-mode), binds forward from this ADR's merge — which is the last change to reach `main` under the old single-main model; thereafter `develop` is the agent target. Existing `main` history is grandfathered.

### D2 — Deterministic `RELEASE-READY` gate (no new critic)

A registry check `RELEASE-READY` (per ADR-0064 D3, implemented in dashboard/health.py, CLI-runnable) is true for `develop` HEAD iff ALL hold: (a) CI green on `develop` HEAD; (b) the full test suite passes (ADR-0067 D1); (c) the latest production-verify for the change is PASS with DOM-attested proof (D5); (d) the green-develop streak is intact (no failing checkpoint since the last promotion); (e) zero open `needs-human` items; (f) the unpromoted batch touches no guardrail-machinery path (D4). Promotion is a deterministic consequence of the check — no judgment critic (the "checks > judgment" thesis; an 8th critic is rejected under the parsimony meta-rule). Per ADR-0004 D2 (bootstrap-mode), binds forward from the gate's own slice; the gate is inert until `develop`/`main` exist (D1's slice). **Cross-dependency bootstrap note:** condition (c)'s DOM-attested requirement depends on D5, which a later slice in this same wave implements; until the D5 proof-integrity slice merges, condition (c) degrades to the existing production-verify trailer requirement (`PRODUCTION_VERIFY: PASS`) WITHOUT the DOM assertion — RELEASE-READY is honestly partially-operative in that window, and the degradation is recorded in the check's detail string. From the D5 merge, (c) is fully DOM-attested.

### D3 — Continuous auto-promotion

After each green-develop checkpoint (the post-merge green step, formerly green-main, now green-develop), the orchestrator evaluates `RELEASE-READY`. If true → fast-forward `main` to `develop` HEAD and append a `promotion` event ({"v":2,"event":"promotion","from","to","sha"}). If false → hold, recording the failing condition. Promotion is fast-forward-only (linear history; `main` is always an ancestor-prefix of `develop`). Measurement (registry row): promotion cadence + `main`↔`develop` lag (commits-behind + age); held-promotion reason histogram. Per ADR-0004 D2, binds forward from the promotion-automation merge.

### D4 — Meta-tripwire: guardrail-machinery promotions wait for the human

A promotion batch is **guardrail-touching** if any commit since the last promotion modifies the guardrail-machinery set: the ADR-0064 D4 enforcement paths (`.github/workflows/**`, `.claude/settings.json`, `.claude/hooks/**`, `tools/ci-checks.sh`, `.githooks/**`) PLUS `.claude/agents/*-critic.md` PLUS the release-gate definition (the `RELEASE-READY` check + promotion tooling) PLUS branch-protection config. A guardrail-touching batch does NOT auto-promote — it holds for an explicit human ack (a `promotion-ack` label or owner comment on the promotion record) before `main` advances. This SUPERSEDES ADR-0064 D4: the human tripwire moves from per-enforcement-path-PR (blocking the autonomous develop flow) to per-promotion (blocking only `main` advancement, and only for self-modifying batches) — a strictly larger protected surface at strictly lower friction. The R-SENSITIVE reviewer rule and its detector row are retired as a develop-merge gate; the detector is repurposed to count guardrail-touching promotions and their ack status. Per ADR-0004 D2, binds forward.

### D5 — Deterministic proof-integrity on rendered DOM

The proof artifacts surfaced for the human's chat-glance and consumed by `RELEASE-READY` (c) are validated by a deterministic proof-integrity check, NOT a judging agent: for browser-route proof the check asserts the claimed string appears in the captured **rendered-DOM `inner_text`** (never API JSON — the #811/#833 class shipped because API-layer proof passed while the DOM was empty); for all routes it asserts artifact-file existence, `PROOF_SOURCE` names a live non-fixture session, and `ENV` sha == promoted HEAD. A proof failing integrity is inadmissible and holds the promotion. Per ADR-0004 D2, binds forward.

## Consequences

- The human leaves the per-change loop entirely; the only blocking human roles become (1) acking guardrail-machinery promotions and (2) grilling future features at design time. Production tracks develop continuously behind a mechanical gate.
- The fleet cannot silently rewrite-and-ship its own safety rails — the one self-modification hole closes structurally rather than by per-PR vigilance.
- One-time migration cost: every `origin/main` reference in guards/CI/dashboard/skills moves to `origin/develop`; the green-main step becomes green-develop; the dashboard gains a promotion/lag panel. This ADR's own PR is the last merge to `main` under the old model.

### Enforcement (rule #23)

Deterministic, per decision: D1 — branch-protection on `develop` + a topology check (slice PRs base `develop`; `main` advances only via `promotion` events); D2 — the `RELEASE-READY` registry check; D3 — `promotion` events + the cadence/lag registry row; D4 — the guardrail-machinery path-set check (a guardrail-touching promotion lacking an ack = a violation row; the repurposed R-SENSITIVE-DETECTOR); D5 — the proof-integrity DOM check (part of RELEASE-READY). Parsimony — mechanisms considered: D1's topology/branch-protection is NOT covered by the existing ADR-0042 CI gate — that gate fires on `pull_request` and verifies content correctness, but cannot enforce which branch a PR targets or prevent a direct push; branch-protection is the only mechanism that enforces PR routing, and the topology check confirms the routing property (PRs base `develop`; `main` advances only via `promotion` events) that no content check observes. A release-critic (8th critic) rejected (deterministic gate suffices; parsimony meta-rule's default is extend-not-add); R-SENSITIVE per-PR ack (ADR-0064 D4) superseded because it blocks the autonomous develop flow the operator wants unblocked while protecting a smaller surface than the promotion tripwire; the green-main step (ADR-0062 D3) is reused as the promotion trigger rather than a new scheduler; the meta-tripwire reuses the enforcement-path set rather than defining a new one. Shadow — per decision: D1, a change slipping onto `main` directly (or a PR based on `main`), bypassing the gate; D2, a gate reporting ready on incomplete conditions; D3, premature promotion on a transiently-green develop streak, or `main` advanced with no recorded `promotion` event; D4, a fleet shipping its own weakened guardrails to production; D5, proof that passes at the API layer while the rendered surface is broken.

## Alternatives considered

- **No human gate anywhere (max autonomy):** rejected — leaves the self-modification hole open; the fleet could weaken a gate and promote the weakening, and our own history shows the gates lag real failure classes by one wave.
- **Human owns every develop→main promotion (pure two-tier):** rejected — reintroduces a human-cadence cap on production and the per-batch friction the operator wants removed; the meta-tripwire achieves the safety with the human touching only self-modifying batches.
- **Release-critic (8th critic) for promotion judgment:** rejected — parsimony meta-rule; a deterministic gate is more honest in the one place determinism matters, and judgment is exactly what the operator does not want gating production.
- **Agent-attested proof (a second agent eyeballs the screenshots):** rejected (operator's call, Q12) — the deterministic DOM-inner_text check closes the measured #811/#833 class without an extra dispatch; revisit only if a class slips that requires visual judgment.
- **Keep merging to `main`, add `production` above it:** rejected — leaves agents merging to `main` (contradicting "main is blessed") and renames production confusingly; develop/main is the convention.

## References

- ADR-0064 D4 (the superseded per-PR ack), ADR-0042 D2 (CI gate target), ADR-0062 (green-main step reused as promotion trigger), ADR-0058 (worktree integration target), ADR-0067 D1 (the test suite RELEASE-READY consumes), ADR-0003 D8 (macro-ADR in slice 1), ADR-0004 D1/D2 (joint gate + bootstrap), issues #804 #811 #833, post-v2 design grill (2026-06-16).

## Propagation

Tracked files citing the superseded ADR-0064 D4 / R-SENSITIVE, with disposition:

- `.claude/agents/reviewer.md` — **update-in-this-wave**: the R-SENSITIVE rule (per-PR enforcement-path ack) is retired and replaced with a one-line pointer to the promotion meta-tripwire (D4); rule #4 references retargeted to `develop`.
- `CLAUDE.md` — **update-in-this-wave**: rule #4 rewritten to the develop/main promotion model; any R-SENSITIVE/enforcement-path mention updated to the promotion tripwire.
- `decisions/README.md` — **update-in-this-wave**: ADR-0064 status cell annotated "D4 superseded by ADR-0070"; new ADR-0070 index row.
- `decisions/0064-rule-layer-integrity.md` — **grandfather** (immutable ADR; the supersession is recorded in README and this ADR's Supersedes header, not by editing the file).
- `origin/main` tooling references (`tools/worktree-guard.sh`, `tools/ci-checks.sh`, `.claude/skills/ship/SKILL.md`, `.claude/skills/build/SKILL.md`, `.claude/hooks/session-start.sh`, `dashboard/health.py`, `dashboard/server.py`) — **update-in-this-wave**: the integration-branch references migrate `main`→`develop` across the wave's migration slices (the bulk of the implementation); this is the ADR-0042 D2 extension, not a D4 citation, and is dispositioned here for completeness.
- `.claude/logs/**` (trail-cache, review-archive) — **grandfather** (gitignored / non-runtime historical artifacts).
