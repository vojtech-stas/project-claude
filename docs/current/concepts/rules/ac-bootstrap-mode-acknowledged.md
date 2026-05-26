---
title: AC-BOOTSTRAP-MODE-ACKNOWLEDGED — adr-critic criterion 5, new enforcement ADRs must cite or restate bootstrap policy
summary: The adr-critic rule that any ADR introducing a new enforcement mechanism (hooks, branch protection, critics, reviewer rules, gate subagents, mandatory loops) must either cite ADR-0004 D2's bootstrap-mode policy OR include its own explicit bootstrap-mode acknowledgment naming the slices affected.
tags: [rule, adr-critic-rubric]
type: concept
last_updated: 2026-05-26
sources:
  - .claude/agents/adr-critic.md criterion 5
  - decisions/0004-bypass-prevention.md D2 (canonical bootstrap-mode policy)
  - decisions/0004-bypass-prevention.md D5c (the ADR-0003 lacuna this rule was designed to prevent)
---

# AC-BOOTSTRAP-MODE-ACKNOWLEDGED

**AC-BOOTSTRAP-MODE-ACKNOWLEDGED** is criterion 5 in the [`adr-critic`](../../../.claude/agents/adr-critic.md) rubric. If the ADR introduces a new enforcement mechanism — hooks, branch protection, critics, reviewer rules, gate subagents, mandatory loops — it MUST either:

- **(a)** explicitly cite [ADR-0004](../../../decisions/0004-bypass-prevention.md) D2's bootstrap-mode policy, OR
- **(b)** include its own explicit bootstrap-mode acknowledgment naming which slices are subject to the new mechanism and which are grandfathered.

This rule exists to prevent the **silent immediate-application assumption** — the recursive paradox where a critic introduced in slice N attempts to gate slice N's own creation. This is the exact lacuna [ADR-0004](../../../decisions/0004-bypass-prevention.md) D5c records against ADR-0003: ADR-0003 introduced the critic-loop architecture without acknowledging its own ship slice could not be gated by critics that did not yet exist.

## What

The rule fires on any draft ADR whose Decisions introduce a new enforcement mechanism. Mechanics:

- Identify each Decision that introduces enforcement (a gate, a critic, a hook, a mandatory rule, a branch protection, a label-driven workflow).
- For each such Decision, search the draft for either:
  - (a) a citation of ADR-0004 D2 (text like "per ADR-0004 D2" or "bootstrap-mode policy"), OR
  - (b) an explicit paragraph naming the slice(s) subject to the new mechanism and the grandfathered set.
- If neither (a) nor (b) is present → FAIL with `"missing bootstrap-mode policy: D<X> introduces enforcement mechanism '<name>' but does not cite ADR-0004 D2 or explain which slices it applies to"`.

## Why

The recursive paradox is real and load-bearing: an enforcement mechanism that ships in slice N cannot, by definition, have gated slice N itself. The bootstrap-mode policy resolves this by binding **forward from the merge** of the ship slice; earlier slices are grandfathered, future slices are subject. Without an explicit acknowledgment, the next reader has no way to tell whether the mechanism is immediately retroactive (it cannot be), forward-binding (the default), or transitional with a specific cutover.

The asymmetric cost: catching this lacuna at ADR-draft time costs one revision round (add the acknowledgment paragraph); catching it later (per the ADR-0004 D5c historical case) requires a corrective ADR plus reconciliation against every downstream slice that may have made an immediate-application assumption.

Bootstrap-mode acknowledgment is also a load-bearing input for the slicer-critic's downstream judgment of slice 1's special status — slice 1 ships the mechanism; subsequent slices are subject. Without the acknowledgment, slice 1's failure to gate itself reads as a violation rather than the intentional design.

## How to check

For each draft ADR:

1. Read every Decision. Identify those introducing enforcement (new gate, new critic, new mandatory rule, new hook, new branch protection).
2. For each enforcement-introducing Decision, search the draft (Decisions, Consequences, Future direction) for either an `ADR-0004 D2` citation OR a paragraph naming subject vs grandfathered slices.
3. If neither present → FAIL with the literal "missing bootstrap-mode policy" message naming the Decision and the mechanism.
4. A citation must be substantive (not just an incidental ADR-0004 reference elsewhere); a parenthetical "(per ADR-0004 D2)" inside the Decision body qualifies.

## Examples

- **ADR introduces a new `R-FOO` reviewer rule with no mention of bootstrap-mode** → FAIL (missing bootstrap-mode policy).
- **ADR introduces a new critic with text "Per ADR-0004 D2, this critic binds forward from the merge of its ship slice"** → PASS (option a satisfied).
- **ADR introduces a hook with paragraph "This hook applies to slices N+1 onward; slices ≤N predating this ADR's merge are grandfathered"** → PASS (option b satisfied).
- **ADR-0003's original draft introducing critic loops without bootstrap acknowledgment** → FAIL (the historical lacuna this rule prevents).

## Edges

- **part_of:** [[entities/subagents/adr-critic]]
- **related_to:** [[concepts/rules/ac-convention-compliance]]
- **related_to:** [[concepts/glossary/bootstrap-mode]]
- **related_to:** [[concepts/glossary/adr]]
