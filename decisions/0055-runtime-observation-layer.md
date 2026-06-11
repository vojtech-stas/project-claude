# ADR-0055: Runtime observation layer — second-class evidence for runtime-tier edges

- **Status:** Accepted
- **Date:** 2026-06-11
- **Deciders:** user (vojtech-stas) + Claude session
- **Supersedes:** [ADR-0053](0053-artifact-trail-as-system-of-record.md) D1 *narrowed* — the clause "runtime hook events are live enrichment only and never feed the comparison engine" becomes "never feed `run_pass` or the github-tier evaluation"; [ADR-0053](0053-artifact-trail-as-system-of-record.md) D2 *narrowed* — the runtime-tier definition "never compared against the trail; rendered as context where available, silently absent where not" becomes "observed by the runtime layer with explicit states; never authoritative". All other ADR-0053 decisions (system-of-record, SPEC single-source, run_pass semantics, collector, golden run) stand unchanged.

## Context

The SPEC v2 declares 45 edges across three evidence tiers: 17 `github`, 26 `runtime`, 2 `unmeasurable`. The comparison engine ([ADR-0053](0053-artifact-trail-as-system-of-record.md) D3) implements evaluators for all 17 github-tier edges and none of the others — by design: ADR-0053 D1 made runtime hook events "live enrichment only" because, at decision time, the capture layer was empirically dead (the jq ENOEXEC era) and runtime evidence could not be trusted to exist.

That premise has been retired. Capture v2 (PRD #668) ships a beaconed, quarantined, validated event feed; PRD #704 extended it to `user_prompt` and assistant turn tails; PRDs #680/#703 made the feed visible. The production consequence of D1's exclusivity is now a standing falsehood on the dashboard: every run's comparison shows 26 of 45 edges as `not-evaluated` — the user reads it as "no starting edges have been measured," and they are right. The front of the pipeline (user → skills → agent dispatches → verdict returns) produces no GitHub artifact and therefore can never be measured under the current rules, no matter how healthy the runtime feed is.

The user's directive: measure all the edges until declared and measured match.

## Decision

### D1: Runtime-tier edges get runtime evaluators producing second-class states

`dashboard/comparison.py` gains a runtime observation pass: for each `runtime`-tier SPEC edge, an evaluator predicate over the v2 event feed (`workflow-events.jsonl`) scoped to the run's window. New per-edge states, distinct from the github-tier vocabulary: `runtime-confirmed` (predicate true with event evidence), `runtime-unobserved` (predicate false while capture was provably alive in the window), `not-observable` (capture dead or absent for the window — honest, never drift-colored), and `not-exercised` (conditional edge whose trigger never arose; shared semantics with github tier). Every declared edge therefore has an evaluator or an explicit `unmeasurable` designation: the `not-evaluated` state is abolished.

### D2: Second-class means run_pass is untouched

`run_pass` ([ADR-0053](0053-artifact-trail-as-system-of-record.md) D3) remains computed exclusively from github-tier required-always edges plus zero-unexpected. Runtime states never feed it — a run with dead capture still PASSes if its artifact trail is clean, and a runtime-confirmed flood can never compensate for a missing reviewer verdict. This preserves ADR-0053 D1's integrity guarantee (fixture pollution or capture gaps cannot corrupt the system of record) while ending its display-level consequence (dark edges). The report carries a separate `runtime_coverage` summary (observed/unobserved/not-observable counts) alongside `run_pass`.

### D3: Run-window correlation by time span plus identifier hints

A run's runtime window = PRD `created_at` → `closed_at` (open PRDs: → now). Events within the window match an edge's predicate by event type, payload fields (`skill`, `subagent_type`, verdict trailers in `tail`, issue numbers in `input` excerpts), and intra-session ordering where the predicate requires sequence (e.g. `slicer-critic` dispatched after `slicer` completes). Cross-run ambiguity (two PRDs in flight in one window) is tolerated in v1: an event may confirm the same edge in both runs' reports — runtime states are observational, not attributional, and D2 keeps the ambiguity out of the record of record. Fixture-pattern sids stay excluded (rule #21).

### D4: Capture-liveness gating

For each run window, the observer first computes capture liveness from the feed itself (any v2 event in window, per session). Edges whose predicate window had no live capture render `not-observable` — the honest tri-state the Live tab pills already use. A `runtime-unobserved` verdict is only ever issued when capture was demonstrably alive and the predicted event genuinely did not occur: that is a real declared≠measured finding (e.g. an orchestrator bypassing a declared skill), and surfacing it is the point of this layer.

### D5: Declared-vs-measured coverage closure

The dashboard's comparison view gains a coverage strip: `45 declared = 17 github-evaluated + 26 runtime-observed + 2 unmeasurable-by-design`, with per-edge rollup exercise counts ([ADR-0053](0053-artifact-trail-as-system-of-record.md) D3's rollup extended to runtime states). "Declared == measured matches" is defined as: zero `not-evaluated` edges anywhere, every always-edge on an exercised path confirmed (github) or runtime-confirmed, and every never-exercised edge either `conditional` (with its trigger named) or flagged for SPEC re-tiering. Edges that stay dark after real exercising are SPEC defects and get captured per rule #11.

## Consequences

**Positive:** the user's question becomes answerable on the dashboard; bypasses of declared flows (manual orchestration skipping /ship, mislabeled subagent dispatches) become visible as `runtime-unobserved` findings; the rollup's exercise counts show which declared lanes are real and which are aspirational.

**Negative / accepted:** window-based correlation can double-attribute events to overlapping runs (tolerated per D3; revisit only if it misleads in practice); runtime evaluators are coupled to the v2 event vocabulary — new event types ride [ADR-0016](0016-workflow-event-log-jsonl.md) D6 and extend predicates in the same PR; the comparison report grows (~26 more edge entries with evidence excerpts).

**Supersession scope:** narrow and explicit (see header). The artifact trail remains the sole system of record; runtime observation is permanently second-class. The narrowing follows the same pattern ADR-0053 D1 itself used against [ADR-0016](0016-workflow-event-log-jsonl.md) D2's exclusivity: the premise that justified the exclusion (untrustworthy/dead runtime feed) was retired by later work, so the exclusion narrows to exactly the part that still protects integrity (`run_pass`).

## Alternatives considered

- **Keep runtime permanently excluded (ADR-0053 D1's original position, unchanged).** Rejected: the premise (a dead, untrustworthy feed) was retired by PRDs #668/#704, both production-verified; what remains of the exclusion is a standing display falsehood — 26 of 45 declared edges permanently dark — that directly contradicts the project's own declared==measured goal and prompted the user's complaint.
- **A standalone coverage panel outside the comparison report (no comparison.py involvement).** Rejected: it duplicates the per-run reporting surface while leaving the comparison report itself dishonest (`not-evaluated` would persist in the canonical report and its downloadable JSON); two parallel per-edge reports for one run invites divergence — the exact two-sources-of-truth failure mode the trail-of-record refactor exists to kill.
- **Elevate runtime evidence to co-equal authority (runtime states feed `run_pass`).** Rejected: window-based correlation carries tolerated double-attribution ambiguity (D3) and the runtime feed structurally disappears in resumed sessions (capture-dead windows); letting either property influence `run_pass` would re-open the fixture/gap contamination class that ADR-0053 D1's integrity guarantee closed. Second-class observation keeps the guarantee intact.
- **Backfill runtime evidence from session transcripts instead of the event log.** Rejected: transcripts are Claude Code internals with no schema contract, can be huge, and reading them in the dashboard couples the comparison to an undocumented format; the v2 event log is the project's own validated, quarantined vocabulary ([ADR-0016](0016-workflow-event-log-jsonl.md) D1/D4) and already carries exactly the fields the predicates need.
