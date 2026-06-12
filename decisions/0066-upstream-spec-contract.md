# 0066 — Upstream spec contract: EARS-shaped criteria, coverage traceability, append-only amendments, reference pointers

- **Status:** Accepted (joint APPROVE per ADR-0004 D1; shipped with PRD #794 slice 1)
- **Date:** 2026-06-12
- **Extends:** ADR-0020 D2 (qa-plan's LLM-extract from PRD §2 prose — EARS-shaped criteria make the prose extractable by construction, shrinking the residual classes that decision created)

## Context

The downstream half of this pipeline (critics, proofs, trail comparison) is its differentiated strength — the six-researcher survey found no surveyed framework matching it. The upstream half is the weak end: PRD §2 criteria are free prose, so `/qa-plan` extraction yields EXTRACT_FAILED/JUDGMENT residuals by construction (the class ADR-0020 D2 knowingly created); nothing proves every criterion landed in some slice, so coverage gaps surface only at post-merge QA; mid-build requirement changes have no protocol — a PRD body edit after dispatch silently invalidates in-flight work with zero audit trail; and implementers in cold worktrees burn tokens rediscovering seam files every dispatch. Three surveyed spec frameworks (spec-kit, OpenSpec, Kiro) converged on the same three structures — requirement grammar, criterion→task traceability, spec deltas — which port cleanly onto our existing critics without adopting their living-spec-corpus model (rejected: second source of truth, deliberately retired here by ADR-0032).

## Decisions

### D1 — PC-EARS: criteria lead with trigger + observable behavior

PRD §2 criteria are EARS-shaped: numbered, each leading with a WHEN/WHERE trigger context and a SHALL-style single observable behavior (e.g. "WHEN /api/comparison is queried for a nonexistent PRD, the response SHALL carry run_pass != true and a non-null error field"). Non-behavioral criteria (doc presence, perf budgets) keep an explicit `Verifiable:` escape hatch naming their check command. `prd-critic` gains PC-EARS: BLOCK on trigger-less or multi-behavior criteria outside the escape hatch. Grammar only — none of Kiro's file workflow. Measurement: the (JUDGMENT + EXTRACT_FAILED)/total ratio per PRD from existing qa-plan trailers — if the ratio doesn't fall after adoption, the rule is theater and should be dropped (recorded drop-criterion). Per ADR-0004 D2 (bootstrap-mode), binds forward from the prd-critic/to-prd template merge; existing PRDs are not re-gated.

### D2 — SC-COVERAGE: criterion→slice traceability

The slicer writes `Covers: §2 #n[, #m]` into every slice body; `slicer-critic` gains SC-COVERAGE: the union of Covers across the decomposition must equal the PRD's numbered §2 set — BLOCK on orphan criteria (uncovered) or phantom citations (nonexistent numbers). This absorbs spec-kit's /analyze gate into the critic already sitting at that position (parsimony). Measurement: per-PRD coverage = |cited ∩ §2| / |§2| with orphan/phantom counts as a registry row, retroactively computable. Per ADR-0004 D2, binds forward from the slicer/slicer-critic prompt merge.

### D3 — Append-only amendment protocol

After a PRD's first implementer dispatch, its body is frozen; requirement changes land as append-only `## AMENDMENT <n>` issue comments declaring ADDED/MODIFIED/REMOVED against the numbered §2 criteria. `prd-critic` re-reviews the delta (delta mode); `slicer-critic` re-checks SC-COVERAGE against the amended set; `/ship` halts not-yet-started dispatches until both re-APPROVE (in-flight dispatches finish against their original contract and reconcile at review). Body edits after first dispatch are a violation. Measurement: GitHub edit-history — PRDs whose body changed post-first-dispatch without a matching AMENDMENT comment (silent-drift count, target 0) as a registry row; amendments-per-PRD as a volatility signal. Per ADR-0004 D2, binds forward from the ship/SKILL.md + critic prompt merges.

### D4 — References pointers in slice bodies

The slicer MAY add a `References:` line per slice — 2–5 file paths (the seam file, the closest existing pattern to imitate, the constraining ADR) — pointers only, never embedded prose (BMAD-style context copying violates DRY rule #9 and rots; our implementers read the repo). Advisory with a recorded drop-criterion: if first-round-APPROVE rates for slices with References do not exceed those without over a measurement window, drop the practice. Per ADR-0004 D2, binds forward from the slicer prompt merge. (advisory)

## Consequences

- Criteria become extractable by construction; coverage gaps surface at decomposition instead of post-merge; spec changes gain an audit trail and a re-gate; cold-start dispatches get cheap pointers.
- PRD authoring gets slightly more ceremonial (grammar + numbering discipline); the escape hatch keeps non-behavioral criteria honest rather than contorted.

### Enforcement (rule #23)

Deterministic, per decision: D1 — PC-EARS (prd-critic rubric) + the residual-ratio registry row; D2 — SC-COVERAGE (slicer-critic rubric) + the coverage registry row; D3 — the silent-drift edit-history registry row; D4 — explicitly tagged (advisory) with its measured drop-criterion (the References-vs-approval-rate comparison). Parsimony — mechanisms considered: PC-ACCEPTANCE-MECHANICALLY-VERIFIABLE already requires extractability but judges prose case-by-case (the grammar makes it structural); no existing rule maps criteria to slices (slicer-critic verifies INVEST per slice, not coverage across slices — verified against its rubric); no protocol exists for post-dispatch spec change at all; all three blocking rules land inside the two existing critics — no new agent. Shadow: untestable free-prose criteria, criteria lost between slices, silently rewritten specs.

## Alternatives considered

- **Living spec corpus (specs/ directory, OpenSpec/Kiro style):** rejected — a second source of truth that rots without a perpetual reconciler; GitHub issues remain the spec system of record (ADR-0032's retirement of the separate KB layer stands).
- **Full EARS (all five patterns, mandatory everywhere):** rejected — pure EARS forbids the non-behavioral criteria our PRDs legitimately carry; the escape hatch is the honest compromise.
- **Allowing in-place PRD body edits with history notes:** rejected — GitHub edit history is hard to diff in review flows; append-only comments match the existing critic-verdict idiom and are trivially auditable.
- **Embedded context blocks in slices (BMAD style):** rejected — duplicated prose rots; pointers age better and cost nothing.

## References

- ADR-0020 D2 (the extraction decision whose residuals D1 shrinks), ADR-0032 (workflow-only architecture — why no spec corpus), ADR-0040 (residual queue that absorbs JUDGMENT items), ADR-0004 D2 (bootstrap-mode), spec-ecosystem survey + workflow-v2 synthesis §B9/§C3/§C4/§C10 (2026-06-12).
- Numbering note: this draft is co-submitted with the rule-layer-integrity ADR (two numbers below it) in this wave's joint gate; both ship together in slice 1 per ADR-0003 D8. The number between them is reserved for the prompt-schema-v2 draft, which hit a round-3 strict-stop in the same gate and is escalated via needs-human #793 — an intentional, documented gap pending human adjudication, mirroring the ADR-0021 precedent recorded in decisions/README.md.
