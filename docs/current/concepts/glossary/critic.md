---
title: critic — adversarial subagent gating another stage's output
summary: A subagent whose sole job is adversarial scope/quality audit of another stage's output, emitting an APPROVE/BLOCK verdict in the canonical 5-section template; never edits artifacts directly.
tags: [glossary, pipeline, subagent, common-word-narrowed]
type: concept
last_updated: 2026-05-26
sources:
  - decisions/0003-autonomous-pipeline-with-critics.md
  - CLAUDE.md
---

# critic

A **critic** is a subagent whose sole job is adversarial scope/quality audit of another stage's output. It emits an APPROVE or BLOCK verdict in the canonical 5-section template + CRITIC trailer per [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D1, and never edits artifacts directly.

**Edges**

- **related-to:** [[concepts/glossary/subagent]]
- **related-to:** [[concepts/glossary/critic-trailer]]
- **part-of:** [[entities/subagents/reviewer]]

## What

A critic is one half of every generator-critic pair in the autonomous pipeline. Per [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D2, every generation stage is paired with an adversarial critic. The project currently runs 6 critics (the cap, per [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7):

1. [`reviewer`](../../../.claude/agents/reviewer.md) — judges PRs.
2. [`prd-critic`](../../../.claude/agents/prd-critic.md) — judges PRD drafts before `/to-prd` posts.
3. [`adr-critic`](../../../.claude/agents/adr-critic.md) — judges macro-ADR drafts alongside PRDs.
4. [`slicer-critic`](../../../.claude/agents/slicer-critic.md) — judges and picks the best of N slicer outputs.
5. [`glossary-critic`](../../../.claude/agents/glossary-critic.md) — judges single glossary entries before trivial-lane PR.
6. [`backlog-critic`](../../../.claude/agents/backlog-critic.md) — judges captured items before promotion to backlog.

Each critic operates a ≤3-round APPROVE/BLOCK loop and escalates via the `needs-human` label on round-3 BLOCK (I5).

## Why

Critics exist because **generators left to their own judgment drift**. The asymmetry is intentional: generators are biased toward "ship something"; critics are biased toward "block it". The composition produces ship-quality output without human-in-the-loop per stage (per [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D4: no human gates between pipeline stages). The canonical verdict template (Header / Subject of review / Rubric / Findings / Summary) + CRITIC trailer per [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D1 ensures critic findings are mechanically parseable by the generator and itemized enough for the generator to act on without re-asking.

Critics never write — they only judge. This separation prevents the conflict-of-interest failure mode where a generator-critic hybrid quietly fixes its own mistakes rather than blocking on them. The default-conservative bias (per [ADR-0009](../../../decisions/0009-discipline-tightening.md) D4) further tilts critics toward BLOCK on ambiguity, because a spurious BLOCK costs one round of regeneration while a leaked failure compounds downstream.

## Examples from this project

- **`reviewer` on this PR** — will judge whether the 5 atomic notes + INDEX scaffold satisfy slice #246's acceptance criteria, BLOCK on drift, APPROVE and auto-merge on success per [ADR-0002](../../../decisions/0002-autonomous-merge-policy.md).
- **`slicer-critic` on PRD #245** — produced the slice decomposition that yielded slice #246; ran the joint-best-of-N pick per [ADR-0013](../../../decisions/0013-slicer-n3-contract-refined.md).
- **`prd-critic` on PRD #245** — APPROVED the parent PRD before `/to-prd` posted it; no `adr-critic` needed (T1 is pure execution of ADR-0031, no new ADR).

## Anti-patterns

- **The critic that fixes things** — violates the judge-not-write separation; reintroduces the conflict-of-interest failure mode the critic pattern exists to prevent.
- **The critic without a rubric** — degenerates into "I don't like this"; findings become unactionable.
- **The 7th critic** — capped at 6 per [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7; new critic-shaped concerns must extend an existing critic's rubric unless a new ADR justifies otherwise.

## Scope

(c) common word with narrowed meaning here

## Authority

[ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D2

## References

- [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D2 — generator/critic pairing requirement.
- [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D1 — canonical verdict template + CRITIC trailer schema.
- [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7 — 6-critic-cap meta-rule.
- [ADR-0009](../../../decisions/0009-discipline-tightening.md) D4 — default-conservative bias.
- [CLAUDE.md](../../../CLAUDE.md) I5 — escalation surface; round-3 BLOCK applies `needs-human` label.
