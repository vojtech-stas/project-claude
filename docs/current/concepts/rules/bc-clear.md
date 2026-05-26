---
title: BC-CLEAR — backlog-critic criterion 4, body stands alone without source-conversation context
summary: The backlog-critic rule that a captured item's body must give a future `/grill-me` enough purchase to begin without re-asking what the item is; bodies that rely on conversation context ("the thing we talked about", "fix the reviewer thing") or carry unlinked ambiguous artifact references FAIL.
tags: [rule, backlog-critic-rubric]
type: concept
last_updated: 2026-05-26
sources:
  - .claude/agents/backlog-critic.md criterion 4 (clear)
  - decisions/0008-workflow-autolog-bootstrap-and-naming.md D4
---

# BC-CLEAR

**BC-CLEAR** is the backlog-critic rubric criterion that enforces a `captured`-labeled item's body stands alone — a future `/grill-me` session reading only the issue body (no access to the originating conversation) must have enough purchase to begin grilling. Implicit context from the source agent's conversation must be made explicit in the body. The rule fails on conversation-dependent phrasing and on unlinked ambiguous artifact references.

## What

The rule fires on every fresh `captured`-labeled issue. Mechanics:

- Read the body as if you have no prior context. Ask:
  - Are the **named artifacts identifiable**? File paths qualified (`.claude/agents/foo.md`, not "foo"); subagent names linked or full-spelled; ADR references include the D-ID; rule references include the rule ID.
  - Is the **why** at least gestured at — even briefly — so a `/grill-me` Q1 about appetite/scope has something to anchor on?
  - Is there enough specificity that a future Q1 of `/grill-me` ("what's the smallest end-to-end version?") would be **productive** rather than regressive ("wait, what does this even mean?").
- Common failure shapes:
  - **Conversation-context-dependent:** "the thing we talked about earlier"; "what Vojta mentioned"; "fix the reviewer thing"; "address the issue from this session".
  - **Unlinked ambiguous artifact:** "the critic" (which one?); "the skill" (which one?); "that rule" (which?).

## Why

This rule exists because **the gap between capture and `/grill-me` is unbounded**: a captured item may sit days, weeks, or months before promotion through the backlog into a PRD draft. The originating conversation is gone by then — the only context the future grill has is the issue body. A capture that says "fix the reviewer thing" loses its meaning the moment the source session ends; the user re-reads it during `/grill-me` and either has to remember what they were thinking (often impossible) or has to cull and recapture (waste).

The "even briefly" relaxation on *why* matters: the captured tier is zero-friction by design, and demanding full PRD-grade rationale at capture time would defeat the asymmetric-default of CLAUDE.md rule #11. A one-clause gesture toward motivation is sufficient — the full *why* is `/grill-me`'s job.

## How to check

For each captured-tier item:

1. Mentally strip all session context. Read the body as a first-time reader.
2. List every named artifact mentioned. For each: is it linked, file-path-qualified, or named with enough specificity that a `Read` or `gh issue view` would resolve it unambiguously?
3. Look for conversation-context-dependent phrasing ("the X we talked about", "fix the Y thing", "what user mentioned"). If present → FAIL with `"clear: body relies on out-of-issue conversation context; restate the what and the why explicitly in the issue body"`.
4. Look for unlinked ambiguous artifact references ("the critic", "the skill", "that rule"). If present → FAIL with `"clear: named artifact <X> is ambiguous; link or file-path-qualify it"`.
5. If body is comprehensible standalone with at least one gesture toward *why* → PASS.

## Examples

- **"Fix the reviewer thing — it's blocking too aggressively"** → FAIL (conversation-context-dependent; "the reviewer thing" is anaphoric to a prior conversation; no link to a specific rule or behavior).
- **"Rename `R-CLOSES` rule heading in `.claude/agents/reviewer.md` from 'Closes the slice issue' to 'Closes #<n> link present' for symmetry with `R-LOC` heading shape — improves audit-skill grep targets"** → PASS (artifact path-qualified, rule ID, why gestured).
- **"Improve the critic"** → FAIL (which critic? what improvement? no why).
- **"What we talked about with grill-me skipping should be captured"** → FAIL (relies on out-of-issue conversation context; "what we talked about" is anaphoric).
- **"Add `Depends on:` field to slice issue template per ADR-0013 D2 — closes the gap where slicer-critic's SC-DEP-ORDERING rule has no input data to check"** → PASS (linked authority, named gap, clear why).

## Edges

- **part_of:** [[entities/subagents/backlog-critic]]
- **related_to:** [[concepts/rules/bc-actionable]]
- **related_to:** [[concepts/rules/bc-scoped]]
- **related_to:** [[concepts/glossary/captured]]
