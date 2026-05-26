---
title: PC-RABBIT-HOLES-NAMED — prd-critic criterion 5, rabbit-holes + open questions both surfaced (not silently answered)
summary: The prd-critic rule that the Rabbit-holes & Open questions section explicitly lists traps implementers must avoid AND that genuinely-unresolved questions are listed as OQs rather than silently answered; missing known rabbit-holes or hallucinated decisions FAIL the rule.
tags: [rule, prd-critic-rubric]
type: concept
last_updated: 2026-05-26
sources:
  - .claude/agents/prd-critic.md criterion 5 (rabbit-holes named)
  - .claude/agents/prd-critic.md criterion 6 (open questions surfaced — no hallucinated answers)
  - decisions/0003-autonomous-pipeline-with-critics.md D1
---

# PC-RABBIT-HOLES-NAMED

**PC-RABBIT-HOLES-NAMED** is the prd-critic rubric criterion that enforces the §6 Rabbit-holes & Open questions section explicitly lists traps the implementer must avoid AND that genuinely-unresolved questions are listed as Open questions rather than silently answered with hallucinated decisions. Missing known rabbit-holes (e.g., one surfaced during the grill session but absent from the PRD body) or asserted-but-unsettled decisions FAIL the rule.

This rule consolidates two upstream prd-critic concerns — rabbit-holes named (no known trap missing) and open questions surfaced (no hallucinated answer to a still-open question) — because both fail in the same section and the fix shape (add the missing item with explicit "OQ-N:" or "rabbit-hole:" tag) is the same.

## What

The rule fires on every draft PRD's §6 Rabbit-holes & Open questions section. Mechanics:

- **Rabbit-holes named:**
  - Read the grill-session transcript context (the PRD's grill-input source if available) AND read every referenced ADR's "Alternatives considered" / "Rabbit-holes" sub-sections.
  - For each surfaced trap, verify §6 lists it as a rabbit-hole.
  - Any missing known trap → FAIL with the missing-item quoted.
- **Open questions surfaced:**
  - For each design decision the PRD asserts (in §1, §2, or §5), trace back: did the grill session settle it?
  - If the grill session did NOT settle a decision the PRD asserts → that's a **hallucinated answer** → FAIL.
  - If a question is implied by the design (e.g., "qa-tester needs cluster split — but how many sub-slices?") but neither answered nor flagged → also a hallucinated answer → FAIL.

The "default conservative" stance applies: when in doubt about whether a question was settled or assumed, BLOCK and ask the generator to either flag the OQ or cite the grill turn that settled it.

## Why

This rule exists because **rabbit-holes are the largest single source of slice-time scope explosion**, and **hallucinated decisions are the largest single source of post-merge revert**. Both are PRD-time-cheap, slice-time-expensive, PR-time-very-expensive to catch.

The asymmetric cost (PRD revision is cheap, slice respin is expensive, PR revert is more expensive) justifies the conservative default. A missing rabbit-hole at PRD time becomes a slicer scope-violation at slicing time (SC-NO-RABBIT-HOLES triggers); a hallucinated decision at PRD time becomes a reviewer R-ADR-CONFLICT or R-SCOPE block at PR time, or worse, ships and needs a revert PRD.

The "no hallucinated answers" sub-test is the most adversarial: the grill session is the contract; everything the PRD asserts must have a grill-turn it traces back to. Anything the PRD invents must be flagged as an OQ.

## How to check

For each draft PRD:

1. Read §6; verify it has at least one rabbit-hole and at least one OQ (or explicit "no known rabbit-holes" with rationale).
2. Cross-check against the grill session: for each surfaced trap, verify §6 mentions it. Missing → FAIL.
3. For each decision the PRD asserts (§1/§2/§5), trace to grill source. Untraced → either flag as OQ in §6 or FAIL.
4. Cross-check against referenced ADRs: any "Alternatives considered" item that the PRD silently picks without naming → FAIL or OQ.

## Examples

- **§6 lists "qa-tester cluster split — slice count TBD per slicer-critic discretion" as OQ-2** → PASS (genuinely open question explicitly flagged).
- **§5 asserts "qa-tester will be split into 3 sub-slices" but grill session never discussed sub-slice count** → FAIL (hallucinated decision; should be OQ).
- **Grill turn explicitly surfaced "what if the existing qa-automation.md needs migration?" — PRD body silently picks "defer to T6" without listing as OQ** → FAIL (asserted answer without OQ flag).
- **§6 lists 3 rabbit-holes + 4 OQs, all traceable to grill or ADR** → PASS.

## Edges

- **part_of:** [[entities/subagents/prd-critic]]
- **related_to:** [[concepts/rules/sc-no-rabbit-holes]]
- **related_to:** [[concepts/rules/pc-prd-completeness]]
- **related_to:** [[concepts/rules/pc-adr-consistency]]
