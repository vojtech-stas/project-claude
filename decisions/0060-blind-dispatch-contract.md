# 0060 — Blind-dispatch contract: critics judge artifacts, not the generator's story

- **Status:** Accepted
- **Date:** 2026-06-12
- **Extends:** ADR-0054 D1 (critic verdict provenance via output contracts — the OUTPUT side stays as decided; this ADR constrains the INPUT side of critic dispatches)

## Context

Every critic in this pipeline currently receives the generator's narrative alongside the artifact: the reviewer reads the implementer's PR-body claims before the diff; slicer-critic receives the decomposition WITH the slicer's justifications; qa-tester is offered the implementer's own verification output. That is a structural anchoring channel — six independent researchers in the 2026-06-12 synthesis converged on it, and the strongest external pattern surveyed (doubt-driven development) states the mechanism plainly: "Pass ARTIFACT + CONTRACT only. Do NOT pass the CLAIM — handing the conclusion biases agreement." Local evidence: #618's opposite verdicts on structurally identical PRs are consistent with verdicts tracking the story, not the artifact; the 2026-05-31 forensics incident shows curated self-reported evidence passing a gate.

## Decisions

### D1 — Critics receive artifact references and rubric pointers only

Orchestrator dispatch templates for all critics carry: a `BLIND-REVIEW <artifact-ref>` marker prefix, the artifact reference (PR number, issue number, file path), the rubric pointer, and round context — and do NOT carry the generator's GENERATOR-trailer narrative, self-assessment, or success claims. Factual coordinates (branch names, slice numbers, what changed where) are admissible; characterizations ("correctly implements", "verified working") are not. Per ADR-0004 D2 (bootstrap-mode), binds forward from the merge of the dispatch-template slice; in-flight dispatches grandfathered.

### D2 — Generator self-assessment is inadmissible reviewer evidence

The reviewer's input contract states: PR-body claims of correctness/verification are not evidence — every load-bearing property is re-derived by the reviewer itself (the wave-1 reviewers already practice this; this makes it contract). If a dispatch or PR body smuggles self-assessment, the reviewer notes `ANCHORING-INPUT` in its verdict and proceeds blind. The sanctioned generator self-disclosure channel is the `CONCERNS:` field (doubts, not claims) decided by the co-submitted output-contract ADR in this wave's slice-1 PR.

### D3 — qa-tester regenerates every proof

In production-verify mode, implementer-supplied proof artifacts (screenshots, output excerpts) are inadmissible: qa-tester regenerates all proofs itself against the live environment. Per ADR-0004 D2, binds forward from the qa-tester prompt-update slice.

### D4 — Doubt-theater detection is the outcome-side check

Marker compliance proves the protocol was invoked, not that judgment was independent — the honest limit of D1. The outcome-side complement: the critic-health panel (co-submitted wave mechanism) flags doubt-theater — N consecutive first-round APPROVEs per critic (amber), red when a streak artifact later produced a violation or fix-PR. Detection only; no auto-action — a human reads the badge.

### D5 — Bootstrap-mode

Per ADR-0004 D2: D1–D3 bind forward from their implementing-slice merges; no retroactive re-review of merged PRs; historical dispatch records are evaluated best-effort for the rate metrics.

## Consequences

- Critic verdicts track artifacts; the anchoring channel closes; rubber-stamping becomes measurable instead of invisible.
- Dispatches lose narrative context that occasionally helped critics navigate — the rubric pointer and artifact coordinates must carry that weight (factual coordinates stay admissible by design).

### Enforcement (rule #23)

Deterministic: blind-dispatch rate evaluator — `agent_start` events' captured input prefix matched against `^BLIND-REVIEW` per critic dispatch (dashboard evaluator; target 100% post-migration; documented limit: verifies the marker, not prompt-body purity) + the D4 doubt-theater badge. Parsimony: no existing mechanism inspects dispatch INPUTS — CI CHECK 10 and the trailer evaluators verify output schema only, so the input side of the critic contract is currently unmeasured; this evaluator is net-new coverage of that surface, implemented inside the existing dashboard-evaluator pattern, constraining existing dispatch templates with no new agent or artifact type. Shadow: anchored verdicts and proof laundering.

## Alternatives considered

- **N-critic voting panels for independence:** rejected — parsimony meta-rule; cost multiplies; blind single critics + outcome detection first, revisit if eval data (future wave) shows verdict instability persists.
- **Strip ALL context including factual coordinates:** rejected — critics need to find the artifact; facts are not claims.
- **LLM judge scoring critic-reason quality:** rejected — non-reproducible judgment inside the honesty layer; the deterministic marker + outcome badge cover the measurable share.

## References

- ADR-0054 D1 (output-side provenance), ADR-0004 D2 (bootstrap-mode), issue #618, qa-proof/forensics (2026-05-31 incident), workflow-v2 synthesis §B3/§B4 + agent-skills doubt-driven-development survey (2026-06-12).
