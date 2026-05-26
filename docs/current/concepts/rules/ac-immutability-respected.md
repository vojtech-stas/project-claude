---
title: AC-IMMUTABILITY-RESPECTED — adr-critic criterion 6, no proposed edits to existing ADR files
summary: The adr-critic rule that a draft ADR may never propose edits to existing ADR files; corrections to prior ADRs flow through new ADRs with explicit `Supersedes:` headers per `decisions/README.md` immutability convention.
tags: [rule, adr-critic-rubric]
type: concept
last_updated: 2026-05-26
sources:
  - .claude/agents/adr-critic.md criterion 6
  - decisions/README.md (immutability convention)
  - decisions/0001-foundational-design.md D8
---

# AC-IMMUTABILITY-RESPECTED

**AC-IMMUTABILITY-RESPECTED** is criterion 6 in the [`adr-critic`](../../../.claude/agents/adr-critic.md) rubric. The draft ADR must never propose edits to existing ADR files. Corrections to prior ADRs flow through new ADRs with explicit `Supersedes:` headers per `decisions/README.md`'s immutability convention ("Once accepted, it's frozen at the moment of decision … the old one is never edited").

The only legal mutation to an existing ADR file is flipping its `Status` field to `Superseded by ADR-NNNN` — and even that is performed mechanically by tooling, not described as a decision in a new ADR. This rule paired with [AC-CROSS-ADR-CONSISTENCY](ac-cross-adr-consistency.md) and [AC-SUPERSEDES-BY-D-ID](ac-supersedes-by-d-id.md) forms the three-rule defense of the supersession-by-new-ADR mechanism.

## What

The rule fires on every draft ADR. Mechanics:

- Scan the draft's Decisions and Consequences sections for any phrasing like:
  - "update ADR-NNNN"
  - "edit ADR-NNNN"
  - "amend ADR-NNNN"
  - "fix ADR-NNNN inline"
  - "patch ADR-NNNN's Decision X"
  - any implication that an existing `decisions/NNNN-*.md` file's content will be modified.
- If found → FAIL with `"immutability violation: D<X> proposes editing existing <ADR-NNNN>; corrections must ship as a new ADR with a Supersedes header"`.

## Why

This rule exists because **ADR immutability is the load-bearing property** that makes supersession-by-D-ID meaningful. If a prior ADR can be edited in place, then:

- D-ID citations become unreliable (a cited D2 may now say something different).
- `git blame` on `decisions/*.md` becomes the supersession record, not the `Supersedes:` headers — defeating the entire mechanism.
- Future ADRs cannot trust their own cites.
- The `git log` audit trail loses its property as the changelog of decisions.

The mechanism's value comes from its unconditional discipline: corrections cost a new ADR, not an inline edit. The cost is paid once at correction time; the value (trustworthy citations) is paid out every subsequent read.

The exception — flipping `Status: Superseded by ADR-NNNN` mechanically — is not a Decision-level mutation; it is a tooling-applied metadata flip that the new ADR's merge triggers. It does not change the historical content of the prior ADR; it only adds the forward-pointer.

## How to check

For each draft ADR:

1. Read Decisions and Consequences sections. Scan for the listed phrasings or semantic equivalents.
2. If any Decision proposes editing an existing ADR's content → FAIL with the offending Decision number and the targeted ADR.
3. The fix is mechanical: rewrite the Decision to ship a corrective new ADR with an explicit `Supersedes:` header naming the D-ID being overridden.
4. Acceptable: "Status of ADR-NNNN will be flipped to `Superseded by ADR-MMMM` on merge of this ADR" — this is the legal mechanical flip.

## Examples

- **Draft D3 says "Amend ADR-0007 D2 to add the new edge case"** → FAIL (immutability violation; ship a new ADR with `Supersedes: ADR-0007 D2`).
- **Draft Consequences says "Will update ADR-0003 D4's wording to clarify"** → FAIL (immutability violation; clarification flows through a new ADR).
- **Draft D5 says "This ADR supersedes ADR-0006 D4 via `Supersedes:` header; ADR-0006's Status will flip to `Superseded by ADR-0024`"** → PASS (legal supersession + legal mechanical status flip).
- **Draft has no mention of editing prior ADRs** → PASS.

## Edges

- **part_of:** [[entities/subagents/adr-critic]]
- **related_to:** [[concepts/rules/ac-cross-adr-consistency]]
- **related_to:** [[concepts/rules/ac-supersedes-by-d-id]]
- **related_to:** [[concepts/glossary/adr]]
- **related_to:** [[concepts/glossary/supersession]]
