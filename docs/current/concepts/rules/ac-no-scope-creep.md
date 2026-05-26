---
title: AC-NO-SCOPE-CREEP — adr-critic criterion 4, every Decision serves the ADR's stated theme
summary: The adr-critic rule that the ADR title + Context establish the theme; every Decision must serve that theme. "While we're here, also fix Y" Decisions belong in a separate ADR; the rule rejects them at draft time.
tags: [rule, adr-critic-rubric]
type: concept
last_updated: 2026-05-26
sources:
  - .claude/agents/adr-critic.md criterion 4
  - decisions/0004-bypass-prevention.md D1
  - CLAUDE.md cross-cutting rule #1 (YAGNI)
---

# AC-NO-SCOPE-CREEP

**AC-NO-SCOPE-CREEP** is criterion 4 in the [`adr-critic`](../../../.claude/agents/adr-critic.md) rubric. The ADR title and Context section establish the theme; every Decision must serve that theme. Decisions of the "while we're here, also fix Y" shape are rejected — they belong in a separate ADR with its own Context and Alternatives considered.

This rule is the ADR-layer analog of CLAUDE.md cross-cutting rule #1 (YAGNI) and the slicer-critic's SC-NO-NON-GOALS rule. Just as a slice should not chase a non-goal of its parent PRD, a Decision should not pursue a problem outside its parent ADR's stated theme — the same coupling-by-proximity failure mode applies at both layers.

## What

The rule fires on every Decision in the draft. Mechanics:

- Read the ADR title and Context section. State the theme in one sentence.
- For each Decision, ask: "does this serve the stated theme?"
- A Decision that addresses a problem the Context did not name → FAIL with `"scope creep: D<X> '<title>' does not serve the ADR's stated theme of '<theme>'; belongs in a separate ADR"`.
- The bar is **served-by-theme**, not **mentioned-in-context** — the Context may have implicitly invited the Decision; explicit alignment is required.

## Why

This rule exists because ADRs are the **load-bearing decision substrate** for the project. A scope-creeping Decision pollutes the audit trail: future readers looking for the rationale on Y will find it buried in an ADR ostensibly about X, with no Context or Alternatives considered specific to Y. Worse, the Decision becomes uncitable by D-ID-disciplined supersession (no future ADR will know to look there for the Y policy).

The asymmetric cost: catching scope creep at ADR-draft time costs one revision round (move the Decision to its own ADR draft); catching it later means a corrective ADR plus reconciliation of any downstream cites that already pointed to the buried Decision. The discipline mirrors YAGNI at the code layer — each ADR addresses one problem; multi-problem ADRs are a smell.

## How to check

For each draft ADR:

1. Read the title and Context section. State the theme in one sentence (e.g., "How to gate adoption of new enforcement mechanisms").
2. For each Decision, ask: "does this serve the stated theme?"
3. If a Decision addresses a different problem area (e.g., "also, here's the new branch naming convention") → FAIL with the offending Decision number and the stated theme.
4. The fix is mechanical: move the off-theme Decision to a separate draft ADR with its own Context and Alternatives.

## Examples

- **ADR titled "Autonomous merge policy"; Context discusses critic-loop architecture; D4 says "Also, rename `feat/` branches to `feature/`"** → FAIL (D4 is off-theme; belongs in a naming-convention ADR).
- **ADR titled "Bypass prevention"; all Decisions concern enforcement-gate scope and bootstrap-mode policy** → PASS (each Decision serves the stated theme).
- **ADR titled "Knowledge architecture v2"; D12 introduces a thinning target table; D13 mandates a topic-mapping JSON** → PASS if both serve the stated knowledge-architecture theme; FAIL if either is unrelated.

## Edges

- **part_of:** [[entities/subagents/adr-critic]]
- **related_to:** [[concepts/rules/ac-convention-compliance]]
- **related_to:** [[concepts/rules/sc-no-non-goals]]
- **related_to:** [[concepts/glossary/yagni]]
- **related_to:** [[concepts/glossary/adr]]
