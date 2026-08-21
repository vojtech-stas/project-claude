---
id: "ADR-0080"
title: "Frontend reduced to the run-board; batch-plan verb retired"
status: "accepted"
date: "2026-08-20"
scope: "pipeline"
rule_ids:
  - "PIP-024"
supersedes:
  - "ADR-0076 D1"
  - "ADR-0076 D2"
  - "ADR-0078 D1"
  - "ADR-0075 D6"
  - "ADR-0055 D1"
  - "ADR-0055 D4"
  - "ADR-0055 D5"
superseded_by: []
---

# 0080 — Frontend reduced to the run-board; batch-plan verb retired

Status: Accepted
Date: 2026-08-20
**Supersedes (per-decision):** ADR-0076 D1 (verb-set enumeration — `batch-plan` leaves it), ADR-0076 D2 (closed kind enum — `batch_planned` leaves it), ADR-0078 D1 (its "architecture view one click away" clause and its `next` panel/`next_source` marker are retired; its landing-view and reader-only clauses STAND), ADR-0075 D6 (its "the gh-reconstructed layer is never deleted" clause — rationale in D1 below), ADR-0055 D1/D4/D5 (the runtime-observation evidence tier, capture-liveness gating, and coverage strip — their sole implementation `runtime_observer.py` is deleted with its rendering surfaces; rationale in D1 below). All other decisions of those ADRs stand unchanged. **Extends:** ADR-0075 D2 (fold-only read-model — unchanged and re-affirmed), ADR-0055 D2 (`run_pass` remains permanently untouched — `comparison.py`'s source is retained byte-identical partly on this guarantee), ADR-0004 D2 (bootstrap-mode).

**Bootstrap-mode (ADR-0004 D2):** binds forward from its PRD's slices; the ledger's history is never rewritten (the retired kind has zero recorded spans — verified 0 of 101 lines — so nothing historical is orphaned).

## Context

The 2026-08-20 full-component audit measured the frontend against its purpose and the operator ruled on every item (review checkpoint: Q1=A, Q2=DELETE, items A1–A7). Corrected per-tab accounting (hook-registration-traced, superseding the audit's coarser attribution): of `index.html`'s 3,868 script lines, the **Architecture tab is the largest single mass at ~1,646 lines (~43 %)** — topology, hooks and file-viewer panels duplicating the CI-gated `_repo-map.md`, plus the embedded PRD-trail comparison/rollup panel — and the **Live tab is ~1,068 lines (~28 %)** with a 17.3 MB polling payload and a 38 s cold route. Four engine modules totalling ~4,200 lines (`transcript.py` 1,946, `runtime_observer.py` 1,329, `live.py` 435, `prd_firing.py` 488) feed only surfaces this ADR deletes, and carry the suite's two slowest tests (169 s of 336 s wall, both in `transcript.py`'s orbit). `comparison.py` (826 lines) is NOT in that set: `collector.py` imports `compare`/`get_spec_for_compare` (lines 1060/1164) for its CLI, and ADR-0055 D2 guarantees `run_pass` stays untouched — it is engine, misclassified by the audit, and stays. Separately, `tools/pipe/batch-plan` recorded ZERO spans in the ledger's entire history despite a ship-loop mandate and two eligible iterations (#1185). A full frontend drop was adversarially REFUTED (16 test files, the qa-tester browser-proof contract, 8 consumers of `/api/meta`); this ADR encodes the refuter-upheld partial boundary, including its correction that the Firing tab's recorded-runs panel belongs inside the Run-board.

## Decisions

### D1 — The dashboard UI is the run-board plus a thin health strip; every other tab is deleted

The served UI reduces to the **Run-board** as the only tab: its existing `now`/`recent` sections, the recorded-runs panel absorbed from the Firing tab, and a **thin health strip** (verdict counts + FAIL check names, consuming the existing health engine's summary payload — the 53-check registry, check functions, and CLI are untouched). Deleted, in paired route+markup+test units (DEAD-ROUTES enforces route↔fetch parity throughout): the **Architecture tab** (~1,646 JS lines incl. the comparison/rollup panel — the panel's UI dies; `comparison.py` itself stays as engine), the **Live tab** (~1,068 JS lines), the **existing Health tab** (~577 JS lines — replaced by the strip, not left running beside it), the **Firing tab** including its gh-reconstructed cross-check panel, their UI-only API routes, and the four orphaned engine modules (`transcript.py`, `runtime_observer.py`, `live.py`, `prd_firing.py`) with their tests — including `tools/test_obs_715.py` (imports `runtime_observer` and `comparison`; deleted with its subject, which also moots backlog #719).

**On superseding ADR-0075 D6:** that clause ("the gh-reconstructed layer is never deleted; it is relabeled 'reconstructed (cross-check)'") protected the gh-derived panel as the honesty cross-check against the recorded layer. Precisely what replaces it, and what does not: the recorded-vs-gh MERGE-EVENT cross-check is mechanized by the RECORD-VS-GH reconciler (CHECK 22 — real-verifying wherever local trace data exists, honest WARN in fresh hosted checkouts, the accepted family limitation captured as #1212), and verdict-presence-for-merged-PRs gains a HOSTED-CI-REAL gate in the same landing (operator decision 2026-08-21 on escalation #1196, option B; PRD criterion 3c): a new ci-checks.sh check asserts each recently-merged PR carries its reviewer `VERDICT: APPROVE` comment via the gh API — a ground truth fresh checkouts DO have — failing CI outright on a violation, while the ledger-side MERGED-WITHOUT-VERDICT reconciler stays as the complementary local span cross-check. Both cross-checks run on every PR with their environment guarantees stated precisely, where the panel ran only when a human looked. The panel's rendered per-PR TIMELINE narrative (implementer→critic-verdict→merge, reconstructed from PR comments) has NO mechanized replacement and disappears — an accepted loss, listed in Consequences, not an equivalence claim. `prd_firing.py` and `/api/prd-firing` go with it.

**On superseding ADR-0055 D1/D4/D5:** the runtime-observation layer's only renderers die with the tabs, and its sole implementation (`runtime_observer.py`) is deleted. `comparison.py` stays byte-identical — its `_annotate_runtime()` already wraps the observer import in try/except (line 74) modeling exactly this absence — so its runtime-annotation fields (`runtime_edges`, `runtime_coverage`, `capture_liveness`, `capture_unavailable`, `coverage_strip`, `_observer_error`) permanently take their existing capture-unavailable dark shape. No stub is kept: the supersession is the decision, and the dark shape is the already-modeled state, not a new failure mode. ADR-0055 D2's `run_pass` guarantee is unaffected and remains extended.

Externally-consumed surfaces are preserved byte-compatible: `/api/meta` (8 consumer files), `/api/runboard`, the health summary payload the strip consumes, README generation, `tracestore.py`, `collector.py` (with `comparison.py` intact). ADR-0078 D1's reader-only discipline is unchanged: the board renders only recorded spans, states source and freshness, gains no write path. The "architecture view one click away" clause is retired — topology lives in the generated `_repo-map.md` (CI-gated fresh), which the operator ruled sufficient.

**Enforcement (rule #23):** (a0) the new gh-comment verdict-presence CI check (criterion 3c) is the D6-supersession's enforcement — a merged develop PR lacking its reviewer `VERDICT: APPROVE` comment fails HOSTED CI from this PRD onward (anti-pattern shadow: the admin-bypass merge class ADR-0076 D3's residual #1098 names); the span-side ledger reconciler remains the local cross-check layer; (a) DEAD-ROUTES stays PASS on the reduced route set; (b) grep count=0 for imports of the four deleted modules across the WHOLE repo (`dashboard/`, `tests/`, `tools/`, `.claude/` — the `decisions/` archive excepted); (c) the qa-tester browser route still screenshots `/` with real ledger rows — ADR-0078's landing-view production check remains binding on the reduced surface; (d) suite green with subject tests deleted alongside their subjects, never orphan-skipped.

### D2 — The batch-plan verb is retired; the board shows what is recorded, not what is promised

`tools/pipe/batch-plan` is deleted; `batch_planned` leaves `tools/trace.py`'s closed kind enum (safe: zero recorded spans, verified); the ship-loop mandate prose is deleted in the same PR; the Run-board's `next` panel and `next_source` marker are removed — the board shows `now` and `recent`, both backed by spans that verifiably occur. Rationale per the operator's ruling on #1185: honest absence beats mandated ceremony that two eligible iterations never performed. **Return trigger (checkable):** the verb returns only via a new ADR, and the evidence bar is two `captured` issues from distinct PRDs, each documenting a concrete mis-dispatch or planning failure caused by absent recorded batch state (queryable: `gh issue list --label captured` citing this ADR's trigger).

**Enforcement (rule #23):** PIP-024 (this ADR's rule_ids) renders the reduced verb set; `trace.py` hard-errors on the removed kind exactly as on any unknown kind (PIP-015's existing closed-enum behavior); grep count=0 for `batch-plan`/`batch_planned` across `tools/`, `.claude/skills/`, `.claude/agents/`, `dashboard/` (ledger history and `decisions/` archive excepted); STREAM-LIVENESS's per-kind rows drop the dead kind.

## Propagation

Per-file disposition for EVERY grep hit of the superseded ADR numbers across the runtime prompt surface (.claude/agents/, .claude/skills/, .claude/settings.json), re-derived at origin/develop 4988c7a — edits and grandfathers both listed so survival of any hit is a caught omission, not an assumption:

- `.claude/skills/ship/SKILL.md:167` — the batch-plan invocation mandate: DELETED (D2).
- `.claude/agents/reviewer.md:310` — R-FIXTURE's authorized-emitter allowlist enumerates `tools/pipe/batch-plan` and the `batch_planned` kind: both entries PRUNED in the same PR (a deleted tool must not remain "authorized").
- `CLAUDE.md` §4 Map — the dedicated "Batch-plan verb" row (cites ADR-0076 D1/D5): DELETED by name; the trace-store and pipeline-wrapper rows' kind enumerations updated; the dashboard row's summary updated to the reduced surface.
- `tools/gen_rules.py` — the hardcoded statement strings for PIP-014, PIP-015 and PIP-022 are EDITED in the implementing PR to the post-ADR-0080 enumeration with an "(as amended by ADR-0080)" pointer, then regenerated (`.claude/generated/_global.md`); CHECK 17 gates the freshness of exactly that edit. This is the workable interim mechanism — the generator has no per-D-ID supersession channel (whole-ADR only, statements hardcoded), a structural gap captured as #1194; the frontmatter `supersedes` list above is the machine-readable record that mechanism will consume when built.
- `decisions/README.md` — ADR-0080's own new row, AND Status-column supersession annotations on the FOUR target rows (ADR-0055, ADR-0075, ADR-0076, ADR-0078: "D<n> superseded by ADR-0080"), matching the repo's 15+ prior superseding-ADR precedents. Note: DOCS-8's regex only recognizes the bullet form `- **Supersedes:**`, so it cannot police this header's per-decision prose form — blind spot captured as #1195; the companion PRD carries a grep criterion as the interim check.
- `.claude/skills/ship/SKILL.md:308` — the References-section echo of the batch-plan call: falls with the :167 block's deletion.
- GRANDFATHERED, no edit needed (cite decisions this ADR does NOT supersede): `.claude/agents/implementer.md:52` (ADR-0075 D3, pr-open wrapper span); `.claude/agents/reviewer.md:408` (ADR-0076 D3, R4 status-check floor); `.claude/agents/reviewer.md:472` and `:500` (ADR-0075 D3, pr-merge wrapper); `.claude/skills/ship/SKILL.md:170` (ADR-0076 D1's dispatch‑‑end clause — dispatch survives the verb-set change) and `:176` (ADR-0076 D1's record-green chaining clause — likewise unaffected); `.claude/agents/reviewer.md:446` (ADR-0075 D3, pr-merge protocol wrapper — the wrapper survives, only batch-plan leaves the verb set).
- `README.template.md` tab prose + regenerated `README.md` (CHECK 2); `dashboard/README.md` view inventory.
- Riders dispositioned: #1186 closed as absorbed (its two subject tests die with `transcript.py`); #1179 survives (empty-state error message — subject kept); #1180 survives (tracestore constant — subject kept); #1176's remaining items adjudicated in the implementing PR.

## Consequences

- ~3,300 of 3,868 script lines across four tabs (Architecture ~1,646 + Live ~1,068 + Health ~577 + Firing shell), 12 of 20 API routes, and ~4,200 orphaned engine lines are deleted; the suite's two slowest tests die with their subjects — every local run roughly halves without touching a kept test (#1186 closed as absorbed, not done separately).
- The board's honesty improves by subtraction: every rendered element is backed by a span kind that actually occurs, and the one cross-check the UI used to render is now performed mechanically on every PR by the reconciler that replaced it.
- Lost capabilities, accepted knowingly: per-session live tool-event streaming; the rendered per-PR timeline narrative (implementer→verdict→merge — no mechanized replacement exists); the trail-comparison/rollup view; and the runtime-observation annotations, which go PERMANENTLY dark in `compare()` output (capture-unavailable shape) per the ADR-0055 D1/D4/D5 supersession. The underlying evidence (`workflow-events.jsonl`, collector caches) remains recorded and CLI-queryable — `collector.py --compare/--rollup` keeps working with the dark runtime fields as the named exception.
- The rendered rules PIP-014/PIP-015/PIP-022 would silently contradict this ADR if left alone (CHECK 17 is a byte-diff, not a semantic check) — hence the Propagation section's explicit statement-string edits, and #1194 for the structural fix.
- The qa-tester browser route keeps a real subject: the reduced `/` with real rows remains the rule-#20 browser proof surface.

## Alternatives considered

- **Drop the entire frontend:** refuted with hard evidence (16 test files, ADR-0078/PIP-022 mandate, browser-proof contract, `/api/meta` consumers); rejected.
- **Keep the gh-reconstructed panel because ADR-0075 D6 says "never deleted":** honored in spirit, superseded in letter — the cross-check role moved to the RECORD-VS-GH reconciler, which runs on every PR instead of when a human clicks a tab; keeping the panel would preserve the weaker of two implementations of the same guarantee.
- **Delete comparison.py with the Architecture tab's rollup panel:** breaks `collector.py`'s CLI (live imports at 1060/1164) and strains ADR-0055 D2's `run_pass` guarantee; rejected — panel UI dies, module stays as engine.
- **Keep Live/Architecture but stop maintaining them:** rots in place while DEAD-ROUTES and the suite tax every PR; rejected — deletion is the honest form of deprecation here.
- **Wire batch-plan into dispatch instead of deleting (#1185's alternative):** mechanically sound but adds ceremony to a loop that never asked for it; operator ruled DELETE with a checkable return trigger; rejected for now.

## References

- ADR-0078 (D1 partially superseded: landing view + reader-only stand; architecture-click clause + next panel retired), ADR-0076 (D1/D2 superseded as enumerated; D3–D6 stand), ADR-0075 (D2 extended; D3 wrapper mechanism; D6 superseded with the reconciler rationale), ADR-0055 (D2 extended — `run_pass` guarantee, grounds for keeping `comparison.py`; D1/D4/D5 superseded — runtime-observation tier retires), ADR-0077 (ceremony-overhead arc; continued by the in-flight pipeline-speed PRD #1193)
- Operator review checkpoint 2026-08-20: Q1=A, Q2=DELETE, A1–A7 approved; #1185 decision comment
- 2026-08-20 audit + refutation (per-tab figures corrected by the prd-critic's hook-registration-traced accounting, adopted here)
- Issues: #1185 (batch-plan zero adoption), #1186 (closed as absorbed), #1194 (gen_rules partial-supersession gap), #719 (mooted by runtime_observer deletion), #1179/#1180/#1176 (riders, dispositioned in Propagation)
