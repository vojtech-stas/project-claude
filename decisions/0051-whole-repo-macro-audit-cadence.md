# ADR-0051: Whole-repo macro-audit cadence — cross-session seam audit via codebase-critic whole-repo mode

- **Status:** Accepted
- **Date:** 2026-06-05
- **Supersedes:** none
- **Extends:** [ADR-0046](0046-codebase-critic-and-parsimony-reframe.md) D3 (the per-PRD cadence — this ADR adds the whole-repo complement that ADR-0046 D3 deliberately scoped out) + [ADR-0034](0034-build-orchestrator-and-generated-docs.md) D1 (`/build`→`/ship` lifecycle — the whole-repo audit hooks into `/ship` at start)
- **Decided in:** 2026-06-05 grill (PRD #601)

---

## Context

[ADR-0046](0046-codebase-critic-and-parsimony-reframe.md) D3 established the per-PRD codebase-critic cadence: fires once per PRD, at the last open slice, reviewing the cumulative PRD diff. ADR-0046 D3 explicitly scoped out the "whole-repo periodic" half — the cadence that catches drift accumulating **across** PRDs, in the seams between subsystems that no single PRD's diff would surface. [ADR-0018](0018-boy-scout-reviewer-rule.md) D7 originally reserved this cadence relationship (the "second half of #47"); ADR-0046 D5 superseded ADR-0018 D1–D7 in full and filled the per-PRD half, leaving the whole-repo half open. ADR-0018 D7 is cited here for **historical lineage only** — it is not a live authority.

The gap became concrete in the 2026-06-05 session: the dashboard had re-implemented the `/audit-meta` rubric and drifted from canonical across multiple PRD eras (the DOCS-1 / DOCS-10 bugs). This was a **duplicated-mechanism smell** no single PRD's diff would surface — caught only by a manual whole-repo audit. The repo had also grown to 50 ADRs / 10 agents / 11 skills, the scale that makes cross-subsystem drift progressively harder to catch by inspection.

The deterministic whole-repo layer is already covered by `audit-meta` (on-demand) + `ci-checks.sh` (per-PR, CHECK 9). The gap is **judgment-based cross-subsystem coherence**: whether the seam files that wire subsystems together still accurately reflect the canonical sources each subsystem lives in.

Parsimony ([ADR-0046](0046-codebase-critic-and-parsimony-reframe.md) D1) is honored: no new critic and no new agent — the existing `codebase-critic` gains a new invocation mode. The whole-repo audit is explicitly **non-blocking** (reflection, not a gate), fires **once per session**, and runs **in the background** to not impede the `/ship` pipeline.

---

## Decisions

### D1: Whole-repo macro-audit cadence — extends ADR-0046 D3 to the cross-session complement

A judgment-based whole-repo audit auto-launches as a background subagent at `/ship` start, **once per session** — the cross-session "cadence half" complementing the per-PRD `codebase-critic`. This extends [ADR-0046](0046-codebase-critic-and-parsimony-reframe.md) D3 (the per-PRD cadence) to cover the whole-repo half ADR-0046 D3 deliberately scoped out. (ADR-0018 D7 originally reserved this cadence; superseded per ADR-0046 D5 — **historical lineage only, not a live authority**.)

The audit is **non-blocking**: it runs concurrently with the `/ship` pipeline implementation work and does NOT gate it. Findings are a reflection output, harvested by the main agent downstream (slice #603). `/ship` is the single trigger because `/build` routes through it ([ADR-0034](0034-build-orchestrator-and-generated-docs.md) D1 — no double-fire).

### D2: Mechanism = codebase-critic whole-repo mode (no new critic — parsimony ADR-0046 D1)

Reuse `codebase-critic` (no new critic) with a **whole-repo mode** invocation path — a distinct entry from the per-PRD diff mode ([ADR-0046](0046-codebase-critic-and-parsimony-reframe.md) D3). The distinction:

| Dimension | Per-PRD mode (ADR-0046 D3) | Whole-repo mode (this ADR D2) |
|---|---|---|
| Trigger | `/ship` detects last open slice of a PRD | `/ship` start, once per session |
| Input | `PRD_NUMBER`, `BASE_REF`, `HEAD_REF` | `WHOLE_REPO: true` (no diff refs) |
| Scope | Cumulative PRD diff | Repo map + seam spot-reads |
| Output shape | CRITIC trailer (VERDICT/REASON/ROUND) | GENERATOR trailer (RESULT/FINDINGS_COUNT) |
| Blocking | BLOCK on PRD-introduced drift | Non-blocking (reflection only) |
| Issue filing | RECOMMEND findings → `captured` issues | None — main agent harvests |

Same agent, different trigger and scope. The whole-repo mode: reads the repo **map** (the CLAUDE.md component map + `decisions/README.md` ADR index + bounded `git ls-files` tree) and **spot-reads the connecting/seam files** (skills that dispatch agents, agents that cite ADRs, the dashboard↔canonical-rubric seam). It judges three concern classes: `CROSS_SUBSYSTEM_DRIFT` (a canonical definition contradicts a different subsystem's file), `DUPLICATED_MECHANISM` (same mechanism independently implemented in two+ files — the dashboard-re-impl class), and `PROSE_BEHAVIOR_DRIFT` (prose documents describe behavior the seam files implement differently). It **emits a structured finding list** and stays **read-only**.

### D3: Background dispatch + harvest-on-completion

`/ship` dispatches the whole-repo audit via `run_in_background` — the main agent is notified on completion and **harvests** the findings. Harvest behavior (slice #603): file each finding as a `captured`-labeled GitHub issue (rule #11/#13 shape) and run the `backlog-critic` autopilot (`/promote-to-backlog`). On completion the main agent surfaces a one-line summary: "whole-repo audit: N findings captured (#…)".

The audit **never gates `/ship`**. If the background run errors or times out, the main agent logs the failure as a captured issue and the `/ship` pipeline continues unaffected.

### D4: Once-per-session guard

A session-scoped marker file (`.claude/logs/.macro-audit-<session_id>`, gitignored) prevents re-runs across the session's multiple `/ship` invocations. On each `/ship` start:
1. Check for the marker file (keyed on the session ID from the workflow event log per [ADR-0016](0016-workflow-event-log-jsonl.md)).
2. If the marker exists → skip the background dispatch (log a note: "whole-repo audit skipped: already ran this session").
3. If absent → write the marker, then dispatch.

This ensures the audit fires at most once per session regardless of how many `/ship` invocations the session has (grill Q2b).

### D5: Deferrals + caps (scope boundaries)

The following are explicitly **out of scope** for this ADR:

- **Deep fan-out mode** (deferred — [#600](https://github.com/vojtech-stas/project-claude/issues/600)): the on-demand `/audit --deep` mode that fans out per-subsystem. The seam-focused single-subagent audit is the every-session default.
- **New critic or agent**: this ADR adds no new critic and no new agent (parsimony per ADR-0046 D1). The codebase-critic is reused with a new mode.
- **Codebase-critic filing issues directly**: it stays **read-only**; the main agent harvests (keeps the read-only invariant and makes issue-quality a main-agent responsibility, not a background-subagent responsibility).
- **Deterministic whole-repo checks**: already covered by `audit-meta` + `ci-checks.sh`; this is the judgment complement only.
- **Re-running every `/ship`**: once per session (D4 guard).
- **Gating `/ship`**: the audit is parallel and non-blocking by design (D3).

The context bound for the whole-repo mode is map + seam spot-reads only — NOT a whole-repo deep read (it won't fit in context and is unnecessary for cross-subsystem seam judgment).

### D6: Bootstrap-mode (per ADR-0004 D2)

The `/ship` auto-launch + once-per-session guard mechanism (D3/D4) binds **forward from the merge of its ship slice**. `/ship` invocations on branches cut before that merge are not subject to the auto-launch (the mechanism cannot have gated the slice that ships it). No retroactive sweep.

The whole-repo mode in `codebase-critic` (D2) is available from the merge of the walking-skeleton slice (#602). Slices cut before that merge do not retroactively receive whole-repo audit output.

---

## Consequences

**Positive:**
- Closes the genuinely-uncovered cross-session, cross-subsystem judgment gap that no single PRD's diff surfaces.
- No new critic or agent (parsimony honored — the codebase-critic gains a mode, the net agent count is unchanged).
- Non-blocking: the audit runs in the background; findings are queued for harvest, never halt a pipeline.
- Once-per-session guard keeps the overhead bounded: one background subagent dispatch per session regardless of PRD count.
- Closes [#522](https://github.com/vojtech-stas/project-claude/issues/522) (the open "cadence half" issue).

**Negative:**
- One background subagent dispatch per session adds modest overhead. Mitigated: `run_in_background` means it runs concurrently; the main pipeline is not slowed.
- The codebase-critic prompt grows to support two modes. Mitigated: the modes are clearly delimited sections; the per-PRD mode is untouched.
- The session marker mechanism adds a small file-system artifact. Mitigated: gitignored, cleared on session end.
- Harvest wiring (D3) ships in a later slice (#603); until that slice merges, findings are emitted but not auto-harvested.

**Neutral:**
- Runtime touch: `.claude/agents/codebase-critic.md` (whole-repo mode section), `.claude/skills/ship/SKILL.md` (background dispatch + session guard + harvest notification — slice #603), `decisions/0051-*.md` + `decisions/README.md` (this ADR + index row + ADR-0046 Status annotation). No new agent, no new critic.

---

## Alternatives considered

- **Alt-A (chosen): extend codebase-critic with a whole-repo mode; non-blocking background dispatch.** Parsimony honored; no new agent; clear separation of per-PRD mode (unchanged) and whole-repo mode (new).
- **Alt-B: new dedicated whole-repo-critic agent.** Rejected (parsimony — ADR-0046 D1: each new critic must earn its place; the codebase-critic can absorb this concern with a mode extension; adding a new agent for it would violate the parsimony principle without a distinct concern).
- **Alt-C: make the whole-repo audit a blocking gate in `/ship`.** Rejected: would halt the pipeline if the audit finds anything — the intent is reflection, not blocking; cross-session drift rarely demands immediate halt.
- **Alt-D: have the whole-repo audit file issues directly (not harvest pattern).** Rejected: keeps the codebase-critic read-only (the design invariant established in ADR-0046 D3/D4); main-agent-harvested `captured` issues follow the rule #11 shape correctly; backgrounded subagent filing issues directly would make issue quality hard to review.
- **Alt-E: trigger on `/build` directly instead of `/ship`.** Rejected: `/build` routes through `/ship` (ADR-0034 D1), so triggering on `/ship` naturally covers both; triggering on `/build` would miss `/ship`-direct invocations and create a coverage gap.
- **Alt-F: run on every `/ship` call (no once-per-session guard).** Rejected (grill Q2b): whole-repo drift barely changes between PRDs within a session; re-running every `/ship` call is wasteful and would produce near-identical findings repeatedly.

---

## References

- [ADR-0046](0046-codebase-critic-and-parsimony-reframe.md) D1 (parsimony — no new critic) + D3 (per-PRD cadence — extended by this ADR's whole-repo complement) + D5 (superseded ADR-0018 D1–D7; R-BOY-SCOUT retired).
- [ADR-0018](0018-boy-scout-reviewer-rule.md) D7 — **historical lineage only** (originally reserved this cadence; superseded by ADR-0046 D5; not a live authority).
- [ADR-0004](0004-bypass-prevention.md) D2 — bootstrap-mode policy (D6 above cites it).
- [ADR-0034](0034-build-orchestrator-and-generated-docs.md) D1 — `/build`→`/ship` lifecycle (D1 above cites it for trigger placement).
- [ADR-0016](0016-workflow-event-log-jsonl.md) — session/event log the D4 once-per-session guard keys on.
- [ADR-0037](0037-production-verification-gate.md) — production verification gate model (this is explicitly NON-gating per D3 above).
- [ADR-0011](0011-subagent-quality-framework.md) — subagent-quality framework; rubric for the whole-repo mode lives in `.claude/agents/codebase-critic.md`.
- `.claude/agents/codebase-critic.md` (whole-repo mode added), `.claude/skills/ship/SKILL.md` (background dispatch — slice #603).
- PRD #601 (parent), slice #602 (walking skeleton — this ADR ships here), [#522](https://github.com/vojtech-stas/project-claude/issues/522) (closed by this ADR), [#600](https://github.com/vojtech-stas/project-claude/issues/600) (deferred deep mode).
