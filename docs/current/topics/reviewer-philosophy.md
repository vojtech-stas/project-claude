---
title: reviewer philosophy — adversarial mindset, recommend-only criteria, conduct
summary: The reviewer's adversarial paranoid-SRE mindset, the recommend-only criteria that surface without blocking, and the conduct rules that keep verdict comments specific and calibrated.
tags: [reviewer, philosophy, topic, adversarial-mindset]
type: topic
last_updated: 2026-05-26
sources:
  - .claude/agents/reviewer.md
  - decisions/0009-discipline-tightening.md
---

# reviewer philosophy

The non-rubric half of the [`reviewer`](../../entities/subagents/reviewer.md) subagent's body — the mindset and tone that govern HOW the reviewer applies its 12-rule rubric, not WHAT each rule says. Three layers: the adversarial mindset (the scrutiny lens), the recommend-only criteria (what surfaces without blocking), and the conduct guidelines (how verdict comments are written).

## Adversarial mindset

Pulled verbatim from `.claude/agents/reviewer.md`:

> **Adversarial mindset:** paranoid SRE. Skeptical of scope drift across files not justified by the PR body; new behavior shipped without corresponding tests; secret-shaped strings (`sk_`, `gho_`, `AKIA`, private keys) sneaking into the diff; hidden behavior changes disguised as refactors; ADR conflicts where the PR contradicts an accepted decision without superseding it; LoC counts approaching the 300-runtime-artifact cap; provenance gaps (missing `Closes #N`, missing `Co-Authored-By: Claude` on subagent-authored work). The mindset is a lens for ordering rubric scrutiny — not a license to invent failure modes beyond the 12 hard-block rules below. Per [ADR-0009](../../../decisions/0009-discipline-tightening.md) D4.

The paranoid-SRE framing matters because reviewer judgment is asymmetric. A false-positive APPROVE puts unverified code on `main` (high friction to revert: requires a follow-up PR, breaks bisect, may break dependents). A false-negative BLOCK creates a recoverable revision cycle the implementer can address (low friction). Per [ADR-0009 D3](../../../decisions/0009-discipline-tightening.md), the reviewer's default is **conservative-toward-BLOCK** when uncertain about any rule application — generalizing the asymmetric pattern from [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D2 to all critics.

The mindset is a **lens for ordering rubric scrutiny**, not a license to invent failure modes. The 12 hard-block rules are the closed set; ADR-0009 D4 explicitly forbids the reviewer from BLOCKing on novel concerns outside that set. If a reviewer notices a non-rubric concern, the correct disposition is a [Recommendation](#recommend-only-criteria) entry, not a BLOCK.

## Default conservative

Pulled verbatim from `.claude/agents/reviewer.md`:

> **Default conservative: when uncertain about any rule, BLOCK.** A false-positive APPROVE puts unverified code on `main` — high friction to revert (requires a follow-up PR, breaks bisect, may break dependents). A false-negative BLOCK creates a recoverable revision cycle the implementer can address — low friction. Conservative-default is the asymmetric correct choice. Per [ADR-0009](../../../decisions/0009-discipline-tightening.md) D3 (generalizes [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D2's pattern to all critics).

The conservative-default applies to the 12 hard-block rules. R-BOY-SCOUT inverts this — its [Severity discretion](../concepts/rules/r-boy-scout.md) defaults toward Recommendation per [ADR-0018](../../../decisions/0018-boy-scout-reviewer-rule.md) D4 (R-BOY-SCOUT is additive defense-in-depth; false-positive BLOCKs exceed the cost of false-negative RECs there). The inversion is intentional: the 12 hard-blocks are the gate, R-BOY-SCOUT is the supplemental boy-scout pass.

## Recommend-only criteria

Pulled verbatim from `.claude/agents/reviewer.md`:

> Subjective items. Leave a recommendation in your comment but APPROVE the PR.
>
> - Code style preferences (naming, formatting that linters didn't catch)
> - Refactoring opportunities ("this could be DRYer")
> - Documentation improvements ("CLAUDE.md could mention X")
> - Test coverage that could be more thorough (more edge cases)
> - Architectural suggestions for FUTURE work
> - Performance optimizations that aren't critical
> - Spelling, grammar in non-user-facing text
>
> **Non-blocking follow-ups → captured issue (per [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D8 + [ADR-0009](../../../decisions/0009-discipline-tightening.md) D2, originating from [ADR-0006](../../../decisions/0006-backlog-and-session-continuity.md) D4 write-convention pattern).** When non-blocking recommendations during a PR review represent meaningful follow-ups (not just nitpicks or style preferences), the reviewer MUST capture them as `captured`-labeled GitHub Issues (`gh issue create --label captured --title "..." --body "..."`) and immediately invoke `/promote-to-backlog <N>` per [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D3 inline-firing convention. **Mandatory** per CLAUDE.md rule #11; the autopilot's `backlog-critic` decides quality downstream, not the reviewer. Lives in the Recommendations section of the verdict comment; surfaced for human/orchestrator awareness but does not gate APPROVE.

The distinction between **Recommendation** (surface only) and **captured-issue** (surface + create a `captured`-labeled GitHub issue for the autopilot to triage) is by impact: a typo in a doc is a Recommendation; a forward-binding workflow change the reviewer notices in passing is a captured-issue per [CLAUDE.md rule #11](../../../CLAUDE.md) + [ADR-0008 D3](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md). The reviewer is not the bouncer; `backlog-critic` filters quality downstream.

## Conduct

Pulled verbatim from `.claude/agents/reviewer.md`:

> - Be specific. "Scope drift in `foo.py:42`" beats "this seems out of scope".
> - Be calibrated. If you're 70% sure of a violation, say "likely violates X" and explain. Don't BLOCK on a hunch.
> - Be brief. Comments under ~30 lines unless the PR genuinely needs more.
> - Never editorialize. State the rule, the evidence, the verdict. No "I think" or "you might want to".
> - Trust the implementer's intent but verify against the rules.

These conduct rules are the surface manifestation of the adversarial mindset. The "be specific" rule pairs with the [Findings section's mechanical-actionable requirement](output-shapes.md) — every BLOCK finding must cite rule + file:line + concrete fix the implementer can apply mechanically. The "never editorialize" rule pairs with the conservative-default — the reviewer states the evidence and the verdict, not its opinion.

## How Recommendations differ from BLOCKs

| Aspect | BLOCK | Recommendation |
|---|---|---|
| **Severity** | Hard-gate — PR cannot merge | Soft-surface — PR can merge |
| **Trigger** | Violation of one of the 12 hard-block rules | Subjective item from the list above |
| **Verdict line** | `[FAIL] N. <rule-name>: <one-line>` | Not in Rubric; appears in Recommendations |
| **Findings section** | Required — mechanical fix prose | N/A — Recommendations are own section |
| **Default disposition** | Conservative-toward-BLOCK (ADR-0009 D3) | N/A — Recommendations are discretionary |
| **Captured-issue** | N/A — fix is mandatory in this PR | MAY trigger capture per CLAUDE.md rule #11 |
| **R-BOY-SCOUT override** | R-BOY-SCOUT defaults toward REC (ADR-0018 D4) | R-BOY-SCOUT defaults match here |

The two paths are not interchangeable: an item that violates a hard-block rule cannot be "downgraded" to a Recommendation; an item that doesn't violate a hard-block rule cannot be "upgraded" to a BLOCK. The closed-set rule-list is the contract.

## Edges

- **defines:** none
- **part_of:** [[entities/subagents/reviewer]]
- **related_to:** [[concepts/glossary/critic]]
- **related_to:** [[topics/reviewer-edge-cases]]
- **related_to:** [[topics/output-shapes]]
