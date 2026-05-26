---
title: YAGNI — You Aren't Gonna Need It
summary: "You Aren't Gonna Need It" — the rule #1 cross-cutting practice that no code is added outside the current slice's scope, enforced by the reviewer.
tags: [glossary, conventions, external-standard, discipline]
type: concept
last_updated: 2026-05-26
sources:
  - decisions/0001-foundational-design.md
  - CLAUDE.md
  - https://www.martinfowler.com/bliki/Yagni.html
---

# YAGNI

**YAGNI** ("You Aren't Gonna Need It") is the cross-cutting discipline that no code is added outside the current slice's scope, even when the addition "obviously" would be useful later. The project lists YAGNI as CLAUDE.md rule #1 — it precedes every other cross-cutting rule because every other rule depends on slice-scope being well-defined and enforced.

**Edges**

- **related-to:** [[concepts/glossary/slice]]
- **related-to:** [[patterns/walking-skeleton]]
- **part-of:** [[topics/discipline]]

## What

YAGNI says: don't write code for hypothetical future needs. If the current slice doesn't require a helper, abstraction, configuration knob, or extension point, don't add it — even if you "know" you'll want it next week. The reviewer's first job is to enforce YAGNI by blocking out-of-scope additions ("while I'm here" code).

The rule operationalizes as three rejection patterns the reviewer catches:

1. **Speculative abstraction** — generalizing a one-use helper into a multi-use one before the second use exists.
2. **Speculative configuration** — adding a config knob with one default and no second value yet proposed.
3. **Speculative scope creep** — "while editing this file I noticed X" additions that exceed the slice's "What ships" section.

If you feel the urge to add something "while you're here", STOP and ask the user (CLAUDE.md rule #1, verbatim).

## Why

YAGNI exists because **speculative code has the worst cost-benefit profile in software**. It pays its cost up front (design time, review time, maintenance burden), but its benefit is conditional on a future need that often doesn't materialize. When the future need DOES materialize, the speculative abstraction usually doesn't fit the actual shape of that need, and ends up being rewritten anyway. The net is: speculative code pays full cost for fractional benefit, with negative carrying-cost for the duration it sits unused.

For an autonomous agent pipeline specifically, YAGNI has a second load-bearing role: it makes **slices reviewable**. Without YAGNI, every slice is at risk of drift; reviewer has to litigate every "while I'm here" change. With YAGNI as the prior, reviewer's default is BLOCK on unjustified additions, and the implementer's default is "stay strictly within scope". Reviewer attention budget is the scarce resource; YAGNI conserves it.

The pairing with the walking-skeleton pattern is intentional: walking-skeleton says "ship the smallest end-to-end first"; YAGNI says "don't add to it speculatively". Together they keep slice scope honest.

## Examples from this project

- **A slice scoped to add a new ADR field.** YAGNI BLOCKs adding "the second field that will probably be needed in the next PRD" — that's the next slice's job.
- **A slice scoped to add one new critic rule.** YAGNI BLOCKs refactoring the rule-table format "for future rules" — refactor when a second rule actually requires it.
- **This very slice.** YAGNI blocks adding atomic notes for terms beyond the 9 named in the slice body, even if all 22 could be done in one sitting — slice 3 has its own scope.

## Anti-patterns

- **"It's only 5 more lines"** — the canonical YAGNI violation rationalization; the 5 lines pay full cost (review, maintenance, drift surface) for speculative benefit.
- **"While I'm here..."** — drift detector phrase; reviewer's R-LOC + scope-citation against the slice body BLOCKs.
- **"Let me make this more general"** — speculative abstraction; specialize until the second consumer exists.

## Scope

(b) external standard adopted

## Authority

[ADR-0001](../../../decisions/0001-foundational-design.md) D12

## References

- [ADR-0001](../../../decisions/0001-foundational-design.md) D12 — adoption of YAGNI as cross-cutting rule #1.
- [CLAUDE.md](../../../CLAUDE.md) rule #1 — operational statement; reviewer's first job.
- Martin Fowler, "Yagni": https://www.martinfowler.com/bliki/Yagni.html
- [`.claude/agents/reviewer.md`](../../../.claude/agents/reviewer.md) — primary enforcement surface.
- [[patterns/walking-skeleton]] — companion pattern; YAGNI conserves what walking-skeleton ships.
- [[concepts/glossary/slice]] — the scope boundary YAGNI defends.
