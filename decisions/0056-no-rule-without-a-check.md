# 0056 — No rule without a check (rule #23) + mechanism-admission test

- **Status:** Accepted
- **Date:** 2026-06-12

## Context

The workflow-v2 introspection (2026-06-12, six-researcher synthesis over this repo's own telemetry and issue history) quantified a compliance gap this project had only felt anecdotally: **prose conventions decay to ≈0–17% compliance, while output contracts hold at ≈97.5%** (ADR-0054's own hand-study: prd-critic verdict comments 7/40 → 0/13; qa-plan comments 1/32; the `needs-human` / `needs-human-check` escalation surfaces have fired zero times in repo history — #725 showed bootstrap.sh did not even create the label). Issue #679 documented a prose-only ordering obligation (codebase-critic-before-closing-reviewer on manual dispatch paths) that nothing checks. The pattern: a rule whose only enforcement is "agents read it" is, on this repo's measured evidence, not a rule — it is a wish.

Meanwhile the mechanisms that DO hold (CRITIC/GENERATOR trailers, CI greps, branch protection, the dashboard's declared-vs-measured trail) share one property: a deterministic checker exists outside the rule-follower's head.

## Decisions

### D1 — Rule #23: every new rule ships with its check

Every NEW numbered CLAUDE.md rule, ordering convention, or orchestrator posting obligation introduced after this ADR MUST ship, in the same PR, with a deterministic enforcement mechanism — one of: an output-contract field (trailer schema), a hook validation, a CI grep (`tools/ci-checks.sh`), a pre-commit check, or a dashboard evaluator (health check or trail evaluator). A rule whose enforcement is genuinely impossible or not yet worth building MUST be explicitly tagged `(advisory)` in its rule text. Untagged + uncheckered new rules are a reviewer BLOCK under reviewer rule **R-RULE-CHECK**. Per ADR-0004 D2 (bootstrap-mode), R-RULE-CHECK binds forward from the merge of its ship slice: it applies to rules introduced after that merge; existing uncheckered rules are grandfathered, with D3's coverage row owning the retrofit cadence — no retroactive sweep.

### D2 — Mechanism-admission test in adr-critic (AC-ENFORCEMENT)

`adr-critic` gains rubric rule AC-ENFORCEMENT: any ADR that introduces a rule, convention, or recurring obligation must (a) name its deterministic enforcement mechanism (or carry the explicit `advisory` justification), (b) state why no existing mechanism already covers the concern — generalizing ADR-0046 D1's critic-parsimony principle to ALL mechanisms, and (c) name the anti-pattern it guards against (its "shadow"), so future audits can test whether the shadow re-appeared. Per ADR-0004 D2 (bootstrap-mode), AC-ENFORCEMENT binds forward from the merge of its ship slice: ADRs accepted before that merge are not retroactively re-gated; ADRs co-submitted in the same PRD wave are reviewed against it as drafts (as this wave's siblings are). This ADR satisfies its own test: enforcement = AC-ENFORCEMENT (judgment, adr-critic) + the D3 coverage row (deterministic); no existing mechanism covers rule-level enforcement coverage; shadow = prose-rule accretion with measured-zero compliance.

### D3 — Rule-coverage ratio as a standing Health row

`dashboard/health.py` gains a check that computes the rule-coverage ratio: numbered CLAUDE.md rules carrying either a named check or an `(advisory)` tag, over total rules. Pre-existing rules are grandfathered at baseline (bootstrap-mode per ADR-0008 D8): the row reports the ratio and lists unchecked-and-untagged rules; it WARNs (not FAILs) until the wave-3 conversion pass (synthesis B8) retrofits or tags the backlog of existing prose obligations.

### D4 — Scope boundary

Rule #23 governs rules and obligations, not code: it does not require tests for every code change (that is ADR sketch "regression memory", a separate decision), and it does not forbid judgment-based critic rubric items — a critic rubric IS a deterministic-enough mechanism (dispatch + verdict are observable) for judgment-shaped concerns.

## Consequences

- New conventions become measurably real or honestly advisory; the dashboard can render "is the workflow we designed truly used" at the rule granularity.
- ADRs get slightly longer (enforcement + parsimony + shadow paragraphs).
- Some friction on future rule-writing is intentional — it is the admission fee that keeps CLAUDE.md from accreting wishes.

## Alternatives considered

- **Advisory-only culture (status quo):** rejected — the 0–17% prose-compliance measurement is this repo's own data, not theory.
- **Hard-block everything (no advisory tag):** rejected — some legitimate judgment guidance (e.g. "prefer boring solutions") has no sane deterministic check; forcing fake checks would breed theater.
- **Periodic compliance audits instead of ship-with-check:** rejected — audits found these gaps months late; the check must arrive with the rule, while context exists.

## References

- ADR-0054 (output-contract compliance study that produced the 97.5% figure), ADR-0046 D1 (parsimony principle generalized here), ADR-0008 D8 (bootstrap-mode), issue #679 (prose-only ordering obligation), workflow-v2 synthesis §B8 (2026-06-12).
