---
id: ADR-0075
status: accepted
supersedes: []
superseded_by: []
scope: pipeline
rule_ids: []
---
# ADR-0075: Trace core — recorded pipeline traces, narrowed system-of-record, deferral triggers

- **Status:** Accepted
- **Date:** 2026-08-02
- **Supersedes:** [ADR-0053](0053-artifact-trail-as-system-of-record.md) D1 *narrowed further* — for the specific pipeline transitions wrapped by a `tools/pipe/*` CLI (pr_opened, pr_merged, and future qa-verify/green/promotion spans), the recorded v3 trace-span log becomes the system of record; the GitHub artifact trail is demoted from "the system of record" to a **labeled cross-check** for exactly those wrapped transitions only. For every edge NOT wrapped by a v3 emitter, ADR-0053 D1/D3 stand completely unchanged (artifact trail remains sole system of record).
- **Extends:** [ADR-0016](0016-workflow-event-log-jsonl.md) D1 (JSONL format — the v3 trace log reuses the same one-object-per-line convention) while establishing a **parallel, wrapper-CLI-based delivery mechanism** alongside (not replacing) ADR-0016 D2's hook-based delivery for the existing `workflow-events.jsonl` v2 log — the two logs serve different transitions and neither supersedes the other's delivery mechanism. [ADR-0062](0062-merge-integrity-green-main.md) D1/D2 (BEHIND-retry merge-loop protocol — `tools/pipe/pr-merge` embodies the existing protocol as a callable wrapper rather than inline reviewer prose). [ADR-0004](0004-bypass-prevention.md) D2 (bootstrap-mode — this ADR's decisions bind forward from slice #1078's merge).
- **Honors:** [ADR-0055](0055-runtime-observation-layer.md) D1/D2 in full — this ADR narrows ADR-0053 the *same way* ADR-0055 already did (a retired premise narrows an exclusivity claim to exactly what it still protects), but does not itself touch ADR-0055's runtime-tier evaluators or its "runtime states never feed `run_pass`" guarantee: those govern hook-derived enrichment, a different, lower-trust evidence source than the wrapper-atomic v3 spans introduced here. [ADR-0046](0046-codebase-critic-and-parsimony-reframe.md) D1 (no new critic — the acid query and reconciler are tooling, not a critic); [ADR-0036](0036-worktree-isolation-all-dispatches.md) (worktree isolation unaffected — the trace log path resolves via git-common-dir, worktree-independent by construction).

## Context

The 2026-08-01 forensic audit (PRD [#1075](https://github.com/vojtech-stas/project-claude/issues/1075) §1) found the tracking/enforcement core structurally dishonest: the fired path is reconstructed (gh/regex heuristics), never recorded; the telemetry layer died silently for six weeks with zero error beacons; emission decayed to LLM-remembered prose exactly as predicted; and zero of the project's 21 CLAUDE.md rules have a transition-time enforcer. The acid test — "show one PR's complete causal path, ordered, with durations" — fails today: no mechanism records it end-to-end.

This directly confronts [ADR-0053](0053-artifact-trail-as-system-of-record.md)'s architecture: ADR-0053 made the GitHub artifact trail the system of record precisely because the *hook*-based runtime feed was empirically dead (ENOEXEC-in-claude-shells era). [ADR-0055](0055-runtime-observation-layer.md) later narrowed that stance once hook capture was proven alive again, giving runtime-tier edges second-class observed states — but kept the hard rule that runtime evidence never feeds `run_pass`, because hook-derived events are enrichment, not atomic with the side effect they describe (a hook can misfire, die, or simply not exist for a given transition, and the side effect still happens).

This slice introduces a *third* evidence class that neither ADR-0053 nor ADR-0055 anticipated: a span emitted **atomically with its side effect**, by a wrapper CLI that IS the side effect's only entry point (`tools/pipe/pr-open`, `tools/pipe/pr-merge`). A PR structurally cannot open or merge through the wrapped path without a span landing in the same execution — this is a stronger guarantee than either the artifact trail (reconstructed after the fact, subject to `closingIssuesReferences` join gaps) or hook enrichment (best-effort, can die silently). Per PRD #1075 criterion 1, this warrants promoting the wrapped-transition subset of the trace-span log to system-of-record status, while explicitly leaving every other edge under ADR-0053/ADR-0055's existing rules untouched.

The operator locked seven fork decisions (2026-08-02) after reviewing an architecture study (Options A/B/C, including a LangGraph conductor); this ADR transcribes those seven decisions plus the binding B/C deferral triggers, so future slices in PRD #1075 build against a recorded rationale rather than re-litigating the fork each time.

## Decisions

### D1: Scope — "A+ rider" only; the transition executor (B) and LangGraph conductor (C) are explicitly deferred

This PRD builds **only** the recorded trace store + the three incident-proven blocking gates + deploy-gap immunity (Option A, "A+" because it adds the blocking gates and deploy-handshake on top of a bare recorder). It does **not** build a transition executor that owns state-machine enforcement (Option B) or a LangGraph-based conductor that replaces the skill/subagent orchestration model (Option C). Both remain available future options, designed *against the recorded traces* this PRD produces, gated by D8's deferral triggers below.

**Rationale:** YAGNI at the architecture level — B and C are justified by evidence this PRD's recorder doesn't exist to produce yet. Building the recorder first and then measuring whether B/C are warranted is the walking-skeleton-correct order; building B or C first would mean designing an executor against reconstructed, provably-unreliable telemetry.

### D2: Store — append-only JSONL source-of-truth at the git-common-dir root + disposable SQLite read-model

The durable record is `<git-common-dir-parent>/.claude/logs/trace-v3.jsonl` (append-only, one v3 span object per line) — the single canonical, worktree-independent path, resolved the same way `promote.sh` resolves `LOGROOT` (killing the cwd-relative stranding class that bit `promote.sh` in #1038 from day one, see `tools/trace.py`'s docstring). A derived SQLite read-model (`.claude/state/trace.db`, gitignored, disposable) is planned for a later slice per PRD §5 (`dashboard/tracestore.py`) to back richer queries; it is explicitly **refoldable-from-log, never a second source of truth** — any divergence is a fold bug, fixed in the fold, never patched by writing to the DB directly (PRD §6 rabbit-hole).

Slice #1078 (this slice) ships only the JSONL emitter + a crude linear-scan acid query (`tools/trace.py path --pr <n>`) — the SQLite read-model is out of scope here (SPIDR-Interface fallback available if this slice needed to trim further; it did not).

### D3: Emitters — side-effect wrapper CLIs, atomic with the transition; hooks/OTEL stay enrichment-only; artifact trail demoted to labeled cross-check for wrapped transitions

Five pipeline transitions get wrapper CLIs that append a v3 span in the **same execution** as the side effect: `pr-open` (pr_opened) and `pr-merge` (pr_merged) ship in this walking-skeleton slice; `qa-verify`, `record-green` (extending the existing `tools/record-green.sh`), and `promote` (extending the existing `tools/promote.sh`) are later-slice breadth work per PRD §5. Existing hooks continue to fire as agent/tool-level **enrichment only** — unchanged in kind from [ADR-0055](0055-runtime-observation-layer.md) D1's runtime-tier evaluators; native-OTEL adoption (stream-json `parent_tool_use_id` trees, `--json-schema` verdicts — Option C's free pieces) may be adopted in headless lanes immediately where cheap, per D8.

**The narrowing (see header):** for exactly the transitions a v3 wrapper emits, the recorded span is the system of record (PRD #1075 criterion 1's "structurally cannot merge untraced" guarantee). The RECORD-VS-GH reconciler (PRD criterion 3, later slice) makes the artifact trail's new role explicit and mechanical: it compares recorded `pr_merged` spans against `gh`'s merged-PR list on `develop`, and any merge lacking a span surfaces as a named FAIL row — the artifact trail's job narrows from "the record" to "the honest disagreement detector." This is the same narrowing *pattern* ADR-0055 D1 used against ADR-0053 D1 (a premise that justified an exclusivity claim was retired by later work, so the exclusion narrows to exactly what it still protects) — here the retired premise is "there is no stronger-than-hooks evidence source," retired by the wrapper-CLI's atomicity guarantee.

For every non-wrapped edge (everything the acid-test query and RECORD-VS-GH reconciler don't touch), [ADR-0053](0053-artifact-trail-as-system-of-record.md) D1/D3 and [ADR-0055](0055-runtime-observation-layer.md) D1/D2 apply exactly as written — this ADR changes nothing about `run_pass` semantics, runtime-tier states, or the collector.

### D4: Deploy-gap — topology fix + blocking handshake (later slice; decision recorded now)

The root-checkout topology repair (retire detached HEAD; attach to `main`, ff-only, after verifying clean) and `tools/deploy-handshake.sh` (content-hash of running `.claude/hooks/` + `settings.json` vs the deployed branch; mismatch blocks loudly at session-start + CI) are **decided** here per the operator's lock but land in a dedicated later slice (PRD §4 appetite: ~7–9 slices total; this is slice 1 of 9). Recording the decision now means the later slice implements against an already-settled rationale rather than re-opening the fork.

**Rationale:** the #879 hook-consolidation-never-executed incident (PRD §1) was a deploy-gap failure, not a design failure — the fix was correct but never ran because hooks execute from a detached, unfast-forwarded checkout. Fixing this is orthogonal to the trace store itself but shares this PRD because both are "the enforcement core was structurally dishonest" fixes.

### D5: Gates — blocking day-1 for the 3 incident-proven classes only; advisory elsewhere

Three gates get GitHub-server-side or CI-mechanical blocking status because each maps to a named incident: (1) branch-protection on `main` rejecting direct pushes (closes the #880 class structurally, not just by convention); (2) a CI pre-review job failing commit-subject violations before reviewer dispatch (closes the #869 recurring-churn class); (3) the slice-provenance-at-creation check, already lane-aware per #1067, wired as a named gate (closes the #918 hand-created-slice class). Every other prospective gate (stream-liveness, deploy-handshake mismatch outside CI, dashboard cross-check disagreement) stays **advisory** until it, too, accumulates a named incident — blocking-by-default-everywhere would re-create the "prose rule with 0% compliance" failure mode ADR-0056 documented; blocking is earned per-incident, not applied speculatively.

### D6: Dashboard — repoint incrementally, one panel per slice, riskiest first; gh layer stays as a labeled cross-check

The dashboard's PR-firing timeline is the first panel repointed to the trace store (paired with D3's RECORD-VS-GH reconciler, in the same later slice per PRD criterion 9's verify clause). Further panels repoint in subsequent slices/PRDs as traces accumulate — no big-bang dashboard rewrite. The gh-reconstructed layer is **never deleted**; it is relabeled "reconstructed (cross-check)" wherever a recorded-panel equivalent exists, so recorded and reconstructed values visibly disagree rather than silently diverge (PRD §3 non-goal: "NOT deleting the gh-reconstruction layer — it is demoted to labeled cross-check").

### D7: Registry — keep the existing health-check registry; add 3 rows; fix 2 integrity defects; prune only if subsumed later

`dashboard/health.py`'s `CHECK_REGISTRY` gains three rows in later slices — `STREAM-LIVENESS` (per-stream denominator, no aggregate-newest-beacon blindness), `DEPLOY-HANDSHAKE` (content-hash mismatch surfaced as a named FAIL), `RECORD-VS-GH` (D3's reconciler) — and two audit-found integrity defects get fixed: `CRITIC-HEALTH` gains a `CHECK_REGISTRY` entry, and `reviewer.md`'s stated hard-block rule count is corrected to match its actual enumerated count. The registry is **not** pruned in this PRD; broader pruning is explicitly out of scope (PRD §3 non-goal) and happens only if/when a future executor (Option B/C, per D8) subsumes some rows' function entirely.

### D8: Deferral triggers for Option B (transition executor) and Option C (LangGraph conductor) — recorded, binding

B and/or C are commissioned — designed against the traces this PRD produces — when **either**: (a) the RECORD-VS-GH reconciler (D3/D7) shows a nonzero emission-gap rate after 2+ PRDs have been traced end-to-end through the wrapped transitions, **or** (b) one new bypass incident occurs (a #880/#869/#918-class event, post this PRD's gates). Until a trigger fires, B/C stay undesigned — no speculative architecture. Option C's free native pieces (stream-json `parent_tool_use_id` trees, `--json-schema` structured verdicts) are the one exception: they may be adopted **immediately** in headless lanes where cheap, independent of the B/C commissioning triggers, per the operator's lock.

## Consequences

### Positive

- **The acid test becomes answerable.** Once `pr-open`/`pr-merge` land (this slice), one real PR's `pr_opened`→`pr_merged` spans exist in the store end-to-end, and `tools/trace.py path --pr <n>` answers the causal-path query from recorded spans alone — zero gh calls, zero regex reconstruction, for that PR.
- **No architecture over-commitment.** D1/D8 keep B and C undesigned until evidence (not speculation) justifies them — walking-skeleton discipline applied at the ADR level, not just the code level.
- **The artifact trail's demotion is narrow and honest.** ADR-0053/ADR-0055's collector, `run_pass` semantics, and runtime-tier evaluators are untouched for every edge this PRD doesn't wrap. Nothing about the existing dashboard comparison engine breaks.
- **Parsimony preserved.** No new critic (Honors: ADR-0046 D1); the acid query and reconciler are CLI tooling consumed by the existing dashboard and reviewer, not a new adversarial gate.

### Negative / Accepted

- **Two parallel JSONL logs now exist** (`workflow-events.jsonl` v2, hook-delivered; `trace-v3.jsonl`, wrapper-CLI-delivered). This is an accepted, explicit non-goal-bounded trade (PRD §3: "NOT rewriting the delivery pipeline") rather than a consolidation — a future PRD may fold them if the dual-log seam proves confusing in practice.
- **The SQLite read-model, the deploy-handshake, and the three new registry rows are decided but not yet built** — this ADR records rationale ahead of implementation across ~7–9 slices; a reader following only merged code (not this ADR) will not yet see D4/D6/D7 realized.
- **Bootstrap-mode gap is permanent and named.** PRD #1075's own bootstrap exception means this slice's PR (#1078's PR) merges through the pre-repoint path and is the one structurally untraceable PR forever (RECORD-VS-GH will honestly show this single gap). This is accepted, not hidden.

### Neutral

- No change to `run_pass` computation, the collector's degradation ladder, or the SPEC evidence-tier vocabulary for any edge outside the five wrapped transitions.
- `decisions/README.md` gains an ADR-0075 index row (this PR).

## Alternatives considered

- **Alt-A (rejected): keep the artifact trail as sole system of record everywhere, add only advisory tracing.** Rejected — this reproduces exactly the audit's finding: "the acid test fails" would remain true, because `closingIssuesReferences`-based reconstruction is retrospective and gap-prone, not atomic with the side effect. PRD #1075 criterion 1 explicitly requires a structural guarantee no reconstruction-based approach can provide.
- **Alt-B (rejected for now, deferred per D8): commission the transition executor (Option B) immediately.** Rejected at this time — no recorded-trace evidence yet exists to design an executor against; building one now would be speculative architecture, the exact anti-pattern PRD §4's appetite section warns against ("nothing removed before its replacement is proven with real data").
- **Alt-C (rejected for now, deferred per D8): adopt the LangGraph conductor (Option C) wholesale.** Rejected — PRD §3 non-goal explicitly excludes rewriting the delivery pipeline (skills/subagents/critics/worktree isolation) now; only C's free native pieces (stream-json trees, `--json-schema` verdicts) are adopted early, and only where cheap in headless lanes.
- **Alt-D (rejected): make every new gate blocking immediately.** Rejected per D5 — ADR-0056's own evidence (0–17% prose-rule compliance vs 97.5% output-contract compliance) argues for earning blocking status per incident, not applying it everywhere speculatively; over-blocking risks the same friction the two-tier delivery model (ADR-0070) was built to reduce.

## References

- PRD [#1075](https://github.com/vojtech-stas/project-claude/issues/1075) — parent PRD ("A+ trace core"); this ADR ships in slice [#1078](https://github.com/vojtech-stas/project-claude/issues/1078) (walking skeleton, slice 1 of 9) per [ADR-0003](0003-autonomous-pipeline-with-critics.md) D8.
- [ADR-0053](0053-artifact-trail-as-system-of-record.md) D1/D2/D3 — narrowed by D3 above (wrapped-transition subset only); D3/D4/D5/D6 (collector, degradation ladder, golden-run, bootstrap-mode) unaffected.
- [ADR-0055](0055-runtime-observation-layer.md) D1/D2 — untouched; this ADR introduces a third, higher-trust evidence tier (wrapper-atomic spans) distinct from ADR-0055's second-class runtime-observed states.
- [ADR-0016](0016-workflow-event-log-jsonl.md) D1/D2/D4 — D1 (JSONL format) extended by the new log; D2 (hook-only delivery) stays scoped to `workflow-events.jsonl`; the v3 log's wrapper-CLI delivery is a parallel mechanism, not a supersession.
- [ADR-0062](0062-merge-integrity-green-main.md) D1/D2 — BEHIND-retry protocol lineage; `tools/pipe/pr-merge` wraps this existing protocol.
- [ADR-0070](0070-two-tier-autonomous-delivery.md) D2/D4 — RELEASE-READY condition (f) / META-TRIPWIRE; the promotion-time guardrail-machinery gate this PRD's blocking gates (D5) complement, not duplicate.
- [ADR-0056](0056-no-rule-without-a-check.md) D1 — rule-#23 discipline; cited in D5's rationale for earning blocking status per-incident.
- [ADR-0046](0046-codebase-critic-and-parsimony-reframe.md) D1 — no new critic (Honors).
- [ADR-0004](0004-bypass-prevention.md) D2 — bootstrap-mode; this ADR's decisions bind forward from slice #1078's merge.
- `tools/trace.py`, `tools/pipe/pr-open`, `tools/pipe/pr-merge` — the slice-#1078 implementation of D2/D3.
- `decisions/README.md` — ADR-0075 index row.
