---
id: "ADR-0077"
status: "accepted"
supersedes: []
superseded_by: []
scope: "pipeline"
rule_ids:
  - "PIP-020"
  - "PIP-021"
---
# 0077 — Ceremony-overhead reduction: R-LOC cap 600 + concurrent reviewer dispatch

Status: Accepted
Date: 2026-08-03
**Extends:** ADR-0003 D2 (narrows the ≤300 LoC cap figure it originally set to ≤600 — the reviewer's rule set and 3-tier hierarchy are otherwise unchanged), ADR-0056 (rule #23 mechanization — the `ship/SKILL.md` pre-review CI gate this ADR reworks), ADR-0075 D3 (`pr-merge` wrapper's existing bounded-retry/CI-poll behavior, unchanged), ADR-0076 D3 (`develop`'s server-side `ci`-status floor, unchanged — still the safety net for any red-CI merge attempt), ADR-0004 D2 (bootstrap-mode — see binding paragraph below)

**Bootstrap-mode (ADR-0004 D2):** every decision below binds FORWARD from the merge of the PR that ships this ADR. Slices already in flight when this PR merges keep the cap and gate sequencing that was live when their implementer was dispatched; the raised cap and concurrent-dispatch sequencing apply to every slice dispatched afterward. No retroactive re-review of already-merged PRs is triggered by this change.

## Context

W1 (PRD #1075 / #1127's implementation wave) shipped 8 slices; each paid a measured ~45–75 minutes of fixed ceremony (agent ramp-up, serial CI-then-review sequencing, merge serialization) for a ~9-hour wall-clock batch. The operator reviewed this ledger and ruled the pipeline too slow for the review value it was buying, per the root-cause capture filed as issue #1162 (rule #13 shape: Symptom / Root cause / Proposed).

Two independent root causes were named:

1. **The ≤300-LoC cap (I4 / R-LOC)** was sized before per-slice ceremony costs were measurable. At 300 LoC, delivering an amount of scope that would fit in 3–5 thicker slices instead forces 6–9 thinner ones — each paying the full fixed ceremony cost (implementer ramp-up + ADR/PRD reading + reviewer dispatch + CI wait) independent of how much code it carries. Raising the cap trades slice granularity for fewer fixed-cost payments at equivalent total review surface.
2. **`ship/SKILL.md`'s pre-review CI gate serialized reviewer dispatch strictly AFTER `ci` completion**, even though the reviewer's read/verify rubric (diff quality, scope, tests, commit format, ADR conflicts) does not depend on CI's outcome — only the final merge action does. Waiting for `ci` to reach a terminal state before ever dispatching the reviewer wastes the CI run's wall-clock time instead of overlapping it with the reviewer's own (LLM-driven, comparably slow) read/verify pass.

The operator explicitly considered and **rejected tiering review rigor by risk class** (e.g. skipping or shortening rubric application for "low-risk" slices) — full review rigor is retained unconditionally; only the LoC cap number and the CI/review sequencing move.

## Decisions

### D1 — R-LOC cap raised 300 → 600 runtime-artifact LoC; slicer targets 3–5 slices/PRD

The canonical R-LOC cap in [`reviewer.md`](../.claude/agents/reviewer.md) rises from 300 to 600 LoC of runtime-artifact diff. This is the sole canonical definition site (CLAUDE.md I4 continues to point at it rather than restating the number). Every other live reference to the 300 figure — CLAUDE.md I4 and its R-LOC/slice glossary entries, [`slicer.md`](../.claude/agents/slicer.md), [`slicer-critic.md`](../.claude/agents/slicer-critic.md)'s INVEST/SC-SLICE-COUNT-LOC/SC-DUAL-CAP-MATH rubrics, `implementer.md`, `ship/SKILL.md` and `build/SKILL.md`'s bisect notes, `README.template.md`'s glossary excerpt, and the `slicer-critic` golden-set eval fixtures — updates in the same PR (rule #19 complete-class sweep). Historical incident narrative (the PR #267/slice #258 postmortem in `slicer-critic.md`) is preserved verbatim with a note that 300 was the cap in effect at the time; it is not rewritten to imply the incident occurred under the new cap.

Because R-LOC's own reviewability-degradation rationale scales with the cap (not with an absolute constant), the SPIDR-split-fallback WARN threshold in `slicer-critic.md`'s INVEST "Small" check moves proportionally: 250 LoC (≈83% of 300) becomes 500 LoC (≈83% of 600).

`slicer.md` gains an explicit guidance line: with the doubled cap, target 3–5 slices per PRD for equivalent scope (down from the ~6–9 a 300-LoC cap implied) — advisory guidance for the PRD's own §4 appetite, not an override of it.

### D2 — Reviewer dispatch made concurrent with CI; format-fail intercept relocates to the reviewer's own pre-merge gate

`ship/SKILL.md`'s former "Pre-review CI gate" — which polled `gh pr checks` to a terminal state and only then decided whether to dispatch the reviewer — is replaced with immediate reviewer dispatch: the reviewer is invoked right after `codebase-critic` clears (or right after implementer `SUCCESS` when no `codebase-critic` dispatch applies), without waiting on `ci`. The reviewer's rubric application (reading the diff, judging scope/tests/commits/ADR-conflict) is independent of CI status and now runs concurrently with GitHub Actions' `ci` run instead of serially after it.

The #869 recurring-format-BLOCK-class protection (a CI CHECK-3 commit-format failure silently starving 3 implementer rounds because the orchestrator dispatched the reviewer against stale/misclassified CI output) is preserved, not dropped — it relocates into a new "Pre-merge CI-terminal gate" section in [`reviewer.md`](../.claude/agents/reviewer.md): before posting a tentative-APPROVE comment, the reviewer itself polls `gh pr checks` to a terminal state using the same `tools/ci-failure-kind.sh` classifier as before, and on a CHECK-3 format-class failure flips its own verdict to `BLOCK` with the identical corrective message, reusing the reviewer's own round-cap (CRI-001, ≤3 rounds) instead of a second orchestrator-tracked round counter. A non-format CI failure does not itself flip the verdict — `tools/pipe/pr-merge`'s existing bounded retry plus `develop`'s ADR-0076 D3 server-side `ci`-status floor remain the unchanged safety net; a red-CI PR still never merges regardless of the reviewer's verdict.

**Explicitly unchanged:** `pr-merge`'s bounded-budget/MERGE-PENDING contract (ADR-0075 D3), the server-side `ci`-status branch-protection floor on `develop` (ADR-0076 D3), and merge-collection serialization for simultaneously-APPROVE-ready sibling PRs (ADR-0062 D2).

## Measured rationale

- W1: 8 slices, ~45–75 min fixed ceremony each, ~9h wall-clock for the batch (operator-observed, 2026-08-03).
- Doubling the LoC cap targets roughly halving the fixed-ceremony-payment count for equivalent scope (3–5 slices vs. 6–9) without changing per-slice review depth.
- Concurrent dispatch removes the CI run's wall-clock time from the implementer→reviewer critical path entirely in the common case (CI passes before or around when the reviewer finishes its own read/verify pass); it costs nothing extra when CI is genuinely slower than the review, since the reviewer's pre-merge gate still waits for a terminal state before merging.

## Alternatives considered

- **Tiering review rigor by risk class (e.g., skip/shorten rubric for low-risk PRs):** rejected. The operator explicitly retained full review rigor unconditionally — the incident record (PR #543/#545, PR #267/#258, #869) shows every rubric line item has caught a real defect class; shortening the rubric trades a measured ceremony cost for an unmeasured regression risk.
- **Raising the cap further (e.g., 1000+ LoC):** rejected as excessive for a first measurement. 600 is a 2x step from the existing, empirically-tuned 300; a further raise can be re-evaluated against the next wave's ledger rather than guessed now.
- **Skipping the terminal-CI-poll entirely at merge time:** rejected — "merge still requires `ci`=pass" was an explicit, non-negotiable operator constraint; only the review phase moved earlier, not the merge gate.
- **A second orchestrator-tracked round-counter for the relocated format-fail intercept:** rejected in favor of reusing the reviewer's own `ROUND` field and CRI-001 round-cap — one counter, not two, is simpler and already mechanically enforced.

## Consequences

- Fewer, thicker slices reduce per-PRD fixed-ceremony-payment count roughly proportionally to the cap's 2x increase.
- The implementer→reviewer critical path no longer serially includes the full CI wall-clock time in the common case; the reviewer's own pre-merge poll absorbs whatever CI wait remains.
- The format-fail round-trip now consumes one of the reviewer's own ≤3 rounds instead of a separate orchestrator-tracked counter — one round-cap mechanism instead of two.
- `slicer-critic.md`'s illustrative dual-cap-math-trap numbers needed rescaling to remain meaningful examples at the new cap (non-normative correction, landed in this same PR); the historical PR #267/#258 incident narrative is preserved as-is with a clarifying note.
- Cascade-doc surface (rule #16 / ADR-0005 D3): CLAUDE.md I4 + glossary, `reviewer.md`, `slicer.md`, `slicer-critic.md`, `implementer.md`, `ship/SKILL.md`, `build/SKILL.md`, `README.template.md` (→ regenerated `README.md`), `tests/evals/slicer-critic/*.md`, `tools/gen_rules.py`'s `_RULE_STATEMENTS` + `RULE_IDS_BASELINE`, `.claude/generated/_global.md` (regenerated) all move with this ADR.

## References

- Root-cause capture #1162 (operator-directed 2026-08-03, W1 ledger data: 8 slices, ~45–75 min ceremony each, ~9h batch)
- ADR-0003 (D2 — original ≤300 LoC cap + reviewer rule set)
- ADR-0056 (rule #23 mechanization; the pre-review CI gate this ADR reworks)
- ADR-0075 (D3 — `pr-merge` wrapper bounded-budget/CI-poll contract, unchanged)
- ADR-0076 (D3 — `develop` server-side `ci`-status floor, unchanged; D1 — verb-set precondition/span pattern this ADR does not alter)
- ADR-0062 (D2 — merge-collection serialization, unchanged)
- ADR-0048 (D1 — CRI-001 round-3 strict-stop; the reviewer's own round-cap this ADR reuses for the relocated format-fail intercept)
- Incident classes: #869 (format-review burn), PR #543/#545 (destructive shared-git fixture discipline), PR #267/slice #258 (dual-cap math trap)
- Riders folded into this PR: #1157 (CLAUDE.md CI-check-script Map row missing CHECK 22), #1158 (decisions/README.md ADR-0075 row missing "extended by ADR-0076" note)
