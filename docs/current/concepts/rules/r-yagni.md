---
title: R-YAGNI — reviewer hard-block on unused additions outside stated scope
summary: The reviewer rule that BLOCKs any code added to a PR that is not strictly necessary for the stated scope, including new abstractions, helper functions, configuration knobs for non-existent features, and speculative generality.
tags: [rule, reviewer-rubric, hard-block]
type: concept
last_updated: 2026-05-26
sources:
  - .claude/agents/reviewer.md rule 2
  - decisions/0001-foundational-design.md D12
---

# R-YAGNI

**R-YAGNI** is rule 2 in the [`reviewer`](../../../.claude/agents/reviewer.md) rubric. It hard-blocks any code added to a PR that is **not strictly necessary** for the stated scope. R-YAGNI mechanically enforces CLAUDE.md cross-cutting rule #1 ("Never add code outside the current slice's scope") at PR review time, originating from [ADR-0001](../../../decisions/0001-foundational-design.md) D12's "Hard rules that must be obeyed by every agent action".

## What

R-YAGNI fires on every PR's added lines. Mechanics:

- Reviewer reads the diff and asks per added line: *if I removed this line, would the stated scope still be deliverable?*
- If yes → that line is a YAGNI addition → BLOCK with `YAGNI: unused addition at <file>:<line>`.

Canonical YAGNI patterns:

- New abstractions, interfaces, or helper functions not used by the stated scope.
- Configuration knobs for features that don't exist yet.
- "Just in case" parameters or fields.
- Speculative generality ("we might need this later").
- Dead code or commented-out code.

The test is whether the slice's acceptance criteria CAN be satisfied without the added line. If yes, the addition is YAGNI by definition.

## Why

R-YAGNI exists because **speculative additions accumulate into unmaintainable complexity**. Each "we might need this" line is a future maintenance liability: future readers cannot tell whether the abstraction is load-bearing or vestigial; future implementers cannot safely delete it; future reviewers must re-evaluate whether it's still needed. The project's adversarial-reviewer doctrine (per [ADR-0009](../../../decisions/0009-discipline-tightening.md) D3) defaults to BLOCK when uncertain — speculative-generality additions are exactly the case where uncertainty should resolve toward removal.

Paired with [R-SCOPE](r-scope.md), R-YAGNI closes the "snuck in scope expansion" loophole: R-SCOPE blocks files outside the stated scope; R-YAGNI blocks unused code WITHIN scope-aligned files. Together they prevent both file-level and line-level drift.

## How to check

For each added line in the diff, ask: "if I removed this line, would the stated scope still be deliverable?" If yes, BLOCK with `YAGNI: unused addition at <file>:<line>`.

```bash
gh pr diff <PR> --patch
```

Scan added lines (prefixed `+`) for: new function declarations not called by the slice's stated behavior; new parameters with default values that nothing passes; new config keys that the agent doesn't read; new type definitions that nothing constructs.

## Exemptions

- **Test scaffolding** required to exercise the slice's new behavior (still subject to [R-TESTS](r-tests.md)).
- **Forward-binding edges in KB notes** (per [ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D3) that point to entity notes shipped in a later slice — explicitly authorized expansionary scope for the KB compiler pattern.
- **Cascade-doc updates** named in the slice body (per [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D3).

## Examples

- **PR adds a new "verbose" config flag the implementer "might want later"**: BLOCK — speculative generality.
- **PR factors out a helper function used in exactly one place**: BLOCK — premature abstraction; inline is correct until ≥2 callers exist.
- **PR adds a forward-binding `[[entities/subagents/reviewer]]` edge to a rule note (slice 1) before reviewer.md migration (slice 2)**: PASS — authorized walking-skeleton forward-binding per ADR-0031.

## Edges

- **part_of:** [[entities/subagents/reviewer]]
- **related_to:** [[concepts/rules/r-scope]]
- **related_to:** [[concepts/glossary/yagni]]
- **part_of:** [[topics/reviewer-philosophy]]
