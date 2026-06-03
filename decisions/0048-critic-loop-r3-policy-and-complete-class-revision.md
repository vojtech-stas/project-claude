# ADR-0048: Critic-loop r3 policy — strict-stop affirmed + complete-class revision discipline (rule #19)

- **Status:** Accepted
- **Date:** 2026-06-04
- **Extends / clarifies:** [ADR-0004](0004-bypass-prevention.md) D1 (the `adr-critic`'s joint-gate role, which establishes the shared 3-round APPROVE/BLOCK loop + I5 round-3 escalation surface — **affirmed**: round-3 BLOCK strict-stop, no fix-and-ship exception) + D2 (bootstrap-mode), [ADR-0003](0003-autonomous-pipeline-with-critics.md) D2 (critics-at-every-generation-stage loop — the revision step this discipline refines), [ADR-0045](0045-adr-citation-consult-discipline.md) D3 (the adr-critic citation-ledger that already reduces the origin case), [ADR-0043](0043-claude-md-restructure.md) D1 (CLAUDE.md rule-numbers-as-stable-anchors — the new rule takes the next free anchor #19) + D4 (precedent for adding numbered cross-cutting rules), [ADR-0009](0009-discipline-tightening.md) D3 (default-BLOCK disposition). Honors [ADR-0046](0046-codebase-critic-and-parsimony-reframe.md) D1 (critic parsimony — no new critic).
- **Supersedes:** none (additive — affirms the existing r3 policy and adds a revision discipline; no prior decision is reversed).

## Context

Backlog [#124](https://github.com/vojtech-stas/issues/124) (captured 2026-05-20 from the PRD #121 ship) surfaced a tension in the joint prd+adr-critic gate's strict 3-round ceiling ([ADR-0004](0004-bypass-prevention.md) D1: round-3 BLOCK → `needs-human` + STOP). PRD #121 resolved substantive critiques in rounds 1–2, then hit a **round-3 BLOCK on a single-line residual** — the *same* D-ID-miscite class already fixed in r2, but in one missed sibling location. Per the strict convention that should escalate to a human and stop shipping; pragmatically it was fixed inline + shipped with a transparent pipeline-metadata footer. #124 asked whether to formalize that "fix-and-ship" workaround (option B) or hold the strict line (option A).

The grill (2026-06-04) reframed the question by finding the **root cause**: #121 reached round 3 not because the gate is too strict, but because the **revision was incomplete** — the orchestrator fixed the one flagged instance and missed a sibling of the same defect class. If revisions swept the *whole class*, mechanical residuals would be gone by round 2 and a genuine round-3 BLOCK would be substantive — making strict-stop both correct and low-friction. The landscape also shifted: [ADR-0045](0045-adr-citation-consult-discipline.md) D3's adr-critic citation-ledger now enumerates *every* D-ID cite in one pass, so #121's exact "missed sibling D-ID" case is already structurally less likely.

A "fix-and-ship" exception (option B) — even one gated on a critic certifying triviality — is a permanent crack in a gate whose entire value is being **unbypassable**; it invites future autonomous runs to lean on "it's just mechanical, ship it" (the agent grading its own homework — the exact bypass critic gates exist to prevent). The grill resolved: **affirm strict-stop, and prevent the friction at its source via a complete-class revision discipline.**

## Decisions

### D1: Round-3 BLOCK is strict-stop — no fix-and-ship exception (affirms [ADR-0004](0004-bypass-prevention.md) D1)

A round-3 BLOCK from any critic escalates via the I5 surface (`needs-human` label + parent-context comment) and **stops the pipeline, regardless of the residual's apparent magnitude**. The fix-and-ship interpretation (#124 option B) is **rejected**: any ship-around path — even critic-certified — is a bypass in an unbypassable gate, and shifts the "is this trivial?" judgment to the agent/critic. The genuinely-rare case (a trivial residual surviving to r3 despite a complete-class revision) is handled by the existing escalation: a one-click human glance, which is cheap. The PRD #121 inline-fix was a one-off, not a precedent.

### D2: Complete-class revision discipline — CLAUDE.md rule #19

CLAUDE.md §1 gains **rule #19**: *when revising in response to a critic BLOCK, fix the ENTIRE flagged defect class — sweep all instances of the cited pattern (e.g. every `ADR-NNNN D<n>` cite, every over-cap commit, every missed-reason non-goal), not only the single instance the critic named — before re-invoking.* This is the root-cause fix for #124: with complete-class revision, mechanical residuals are cleared by round 2 and never reach round 3, so strict-stop (D1) rarely fires on trivia. The body is one behavioral constraint + the ADR-0048 citation (per [ADR-0043](0043-claude-md-restructure.md) D1's trim discipline). `#19` is the next free stable anchor (past `#18`; `#14` retired). The discipline is **shared across every critic-loop revision** (joint prd+adr gate, reviewer→implementer, slicer-critic→slicer, glossary-critic→glossary), so CLAUDE.md — the context all generators load — is its single DRY home (rule #9), not any one skill.

### D3: ADR-0045's ledger already reduces the case (recorded)

The adr-critic's citation-ledger ([ADR-0045](0045-adr-citation-consult-discipline.md) D3) enumerates every `ADR-NNNN D<n>` citation in one pass, so the critic now surfaces *all* instances of the D-ID-miscite class at once — structurally reducing the "missed sibling D-ID" scenario that produced #121. Rule #19 (D2) generalizes the same "fix the whole class" discipline to the **generator side** and to **non-D-ID** mechanical classes (commit length, missing-reason non-goals, etc.) that no ledger covers.

### D4: Bootstrap-mode (per [ADR-0004](0004-bypass-prevention.md) D2)

Binds forward from merge. Rule #19 + the strict-stop affirmation apply to critic-loop revisions from this ADR's ship slice onward; no retroactive sweep.

## Consequences

**Positive:**
- Removes #124's friction at its source (incomplete revision) without opening the gate — strict-stop authority is fully preserved.
- Rule #19 covers every critic-loop revision with one DRY home (no per-skill duplication, no drift surface).
- Closes #124's strict-vs-fix-and-ship question on the record, so it isn't re-litigated.

**Negative:**
- Rule #19 is a behavioral discipline, not a hard mechanical gate. Mitigated: a critic re-catches an incomplete sweep (re-BLOCK), so it self-corrects — at the cost of the extra round the discipline exists to avoid.
- A genuinely-novel trivial residual could still reach r3 and escalate to a human. Accepted: rare, and a one-click human glance is cheaper than a permanent bypass.

**Neutral:**
- No new critic ([ADR-0046](0046-codebase-critic-and-parsimony-reframe.md) D1 parsimony honored), no new dependency. Touch: `CLAUDE.md` (rule #19) + `decisions/0048-*.md` + `decisions/README.md` + README regen.

## Alternatives considered

- **Alt-A (chosen): strict-stop affirmed + complete-class revision discipline (rule #19).** Fixes the cause; keeps the gate unbypassable.
- **Alt-B: critic-certified fix-and-ship escape hatch.** Rejected (grill Q1): a permanent guarded bypass in an unbypassable gate; the rare genuine r3-trivial is cheap to escalate (a one-click human glance); adds triviality-classification machinery for a now-rare case (post-ledger).
- **Alt-C: put the discipline skill-local (in each revision loop).** Rejected (grill Q2): it fires across ≥4 revision loops, so per-skill copies duplicate (rule #9) and add a drift surface; CLAUDE.md is the shared DRY home (locality favors the skill only for *single-skill* rules).
- **Alt-D: do nothing (close #124 no-change).** Rejected: the friction is real and the fix is cheap; ADR-0045's ledger reduced but did not eliminate the non-D-ID mechanical-residual class.

## References

- Grill 2026-06-04 (#124). Closes backlog [#124](https://github.com/vojtech-stas/issues/124). Origin case: PRD [#121](https://github.com/vojtech-stas/issues/121) ship (round-3 BLOCK on a residual D-ID miscite, fixed inline with a transparent pipeline-metadata footer).
- [ADR-0004](0004-bypass-prevention.md) D1 (adr-critic exists — establishes the shared 3-round loop + I5 r3 escalation — affirmed) + D2 (bootstrap-mode). [ADR-0003](0003-autonomous-pipeline-with-critics.md) D2 (critics-at-every-stage loop). [ADR-0045](0045-adr-citation-consult-discipline.md) D3 (citation-ledger — reduces the case). [ADR-0046](0046-codebase-critic-and-parsimony-reframe.md) D1 (critic parsimony — no new critic). [ADR-0043](0043-claude-md-restructure.md) D1 (rule-anchors) + D4 (numbered-rule precedent). [ADR-0009](0009-discipline-tightening.md) D3 (default-BLOCK).
- `CLAUDE.md` (rule #19), `.claude/skills/to-prd/SKILL.md` (the joint-gate revision loop — optional one-line pointer).
