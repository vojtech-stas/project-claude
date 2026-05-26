---
title: slicer-critic — best-of-N decomposition scorer with single revision loop
summary: Scores the slicer's N=3 decompositions against a 10-criterion rubric, picks the best with explicit tiebreak, runs at most one revision loop on the chosen decomposition, then APPROVE/BLOCK with the final approved decomposition.
tags: [subagent, critic, gate, slicer-critic]
type: entity
last_updated: 2026-05-26
sources:
  - .claude/agents/slicer-critic.md
  - decisions/0003-autonomous-pipeline-with-critics.md
  - decisions/0005-output-shape-and-slicing-methodology.md
  - decisions/0013-slicer-n3-contract-refined.md
---

# slicer-critic

The `slicer-critic` subagent is the **adversarial gate at stage 3.6** of the autonomous pipeline. It receives (1) the parent PRD and (2) the [`slicer`](slicer.md)'s N=3 decomposition block, scores all three against a 10-criterion rubric, picks the best with explicit tiebreak rationale, runs **exactly one revision loop** on the chosen decomposition, then emits APPROVE (with the final approved decomposition for `/to-issues` to post) or BLOCK (with reasons). Unlike most critics, it doubles as a generator — the "Final approved decomposition" extension is the artifact downstream consumers post.

## Role and responsibility

The slicer-critic has three jobs, in strict priority order:

1. **Score all N decompositions against the 10-criterion rubric** (or score a single N=1 with explicit rationale per [ADR-0013](../../../decisions/0013-slicer-n3-contract-refined.md) D2/D3).
2. **Pick exactly one** with explicit deterministic tiebreak path.
3. **Run at most one revision loop** on the chosen decomposition; if still unfit after one revision, BLOCK rather than re-loop.

It does NOT re-sample a new N=3 mid-loop, does NOT post GitHub issues directly (the `/to-issues` skill or `/ship` orchestrator does that on APPROVE), and does NOT edit the slicer's output without recording the revision request explicitly.

## Invocation contract

- **Caller:** the `/ship` orchestrator at stage 3.6 (per [`.claude/skills/ship/SKILL.md`](../../../.claude/skills/ship/SKILL.md)), invoked through `/to-issues` per [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D3. May also be invoked directly via the `Agent` tool with `subagent_type: "slicer-critic"`.
- **Input:** the parent PRD (issue reference or inline body) AND the slicer's output block. If either is missing → return `INVALID_INPUT: <reason>` and stop.
- **Output:** the canonical verdict template per [[topics/output-shapes]] — 5-section body (Header → Subject of review → Rubric → Findings → Summary) + permitted critic-specific extensions (Scoring matrix / Chosen decomposition / Revision round / Final approved decomposition) + CRITIC trailer. The "Final approved decomposition" extension is the generator-shaped half — it carries the slice list that `/to-issues` posts.
- **Tool boundaries:** `Read`, `Glob`, `Grep`, `Bash` (read-only `gh` / `git` only). NOT authorized: `Write`/`Edit`, `gh issue create` / `gh issue comment` / `gh issue edit`, branch creation, agent invocation.

## Iteration shape — best of N + single revision

Per [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D3, the iteration shape is locked:

- **Pick best of N** (with tiebreak path below).
- **Single revision loop only** — re-score once; never re-sample N=3 mid-loop.
- If after one revision the chosen decomposition is still unfit → BLOCK and escalate. No second revision.

This is asymmetric vs the `reviewer`'s ≤3-round loop: slicing-time fixes are cheaper to recompute upstream (re-run the slicer) than to keep grinding on a poor candidate.

## 10-criterion rubric

Each criterion is scored per decomposition (A / B / C) as PASS / FAIL / WARN. A decomposition is **viable** if it has zero FAILs; WARN count is a tiebreaker among viable ones. Default-conservative: when uncertain about any rule, BLOCK (per [ADR-0009](../../../decisions/0009-discipline-tightening.md) D3 generalizing [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D2). Adversarial mindset: paranoid project manager (PM-of-projects) — skeptical of ordering risks, risk burying, cascade-doc gaps, INVEST shape failures, LoC cap proximity (per [ADR-0009](../../../decisions/0009-discipline-tightening.md) D4).

Each linked rule note expands the criterion's What / Why / How-to-check / Examples. The atomic-note layer is the canonical home; the [`slicer-critic.md`](../../../.claude/agents/slicer-critic.md) executable shell quotes each criterion's name + one-line trigger only.

1. [[concepts/rules/sc-invest]] — every slice satisfies all six INVEST letters
2. [[concepts/rules/sc-walking-skeleton]] — exactly one slice 1 tagged walking-skeleton, exercises every layer end-to-end
3. [[concepts/rules/sc-spidr-splitability]] — near-cap or risky slices name a SPIDR split-fallback hint
4. [[concepts/rules/sc-no-non-goals]] — no slice chases a PRD §3 non-goal
5. [[concepts/rules/sc-no-rabbit-holes]] — no slice walks into a §6 rabbit-hole
6. [[concepts/rules/sc-dep-ordering]] — `Depends on` edges form a DAG with no arbitrary serialization
7. [[concepts/rules/sc-slice-count-loc]] — slice count + per-slice LoC fit the PRD §4 appetite
8. [[concepts/rules/sc-risk-front-loading]] — biggest risk lands in slice 1 or 2
9. [[concepts/rules/sc-cascade-docs-covered]] — cascade-docs identified and covered per ADR-0005 D3
10. [[concepts/rules/sc-cross-pr-collision]] — slice cascade-doc edits don't collide with currently-open PRs

(Numbering note: criterion 10 was added per backlog #194 / PRD #210 as the root-cause workflow improvement after the PR #183 + PR #186 cascade-doc rebase incident; not in the original 9-criterion rubric.)

## Selection step and tiebreak path

After scoring, pick exactly one decomposition as the candidate. The deterministic tiebreak order:

1. Fewest FAILs (a viable decomposition always wins over a non-viable one).
2. Among viable: fewest WARNs.
3. Among viable with equal WARNs: front-loads risk earlier (criterion 8 PASS over WARN).
4. Among still-tied: the decomposition with the thinner walking-skeleton slice 1 (smaller LoC estimate).

The choice and the tiebreak path are stated explicitly in the verdict's "Chosen decomposition" extension. The selection rationale is what makes this critic auditable.

If ALL N decompositions are non-viable (≥1 FAIL each), do NOT pick a candidate. Return BLOCK immediately with the union of failures — the slicer must regenerate a fresh N upstream.

## N=1 acceptance per ADR-0013

Per [ADR-0013](../../../decisions/0013-slicer-n3-contract-refined.md) D2/D3, **N=1 with explicit rationale is a legal input** — do NOT BLOCK on "didn't produce N=3" when the slicer has emitted a single alternative with rationale. Verify the rationale answers (1) what PRD section locks the shape, (2) what variation axis was rejected as non-meaningful, (3) whether N=3 would have produced genuinely-different alternatives. If concrete, score normally against the 10 criteria (they apply identically to a single decomposition). If vague ("only one way to do it" with no PRD citation), bias toward requesting one revision asking for the explicit rationale before scoring. See [[patterns/n1-degenerate-carveout]] for the full pattern.

## Single revision loop

If the candidate has zero FAILs but some WARNs, request **one round of revision** to address the WARNs. Otherwise skip straight to APPROVE.

The revision request must: name the specific slices and the specific WARN criterion to address; be answerable by editing the chosen decomposition only (not by re-sampling); be bounded to at most 5 concrete fixes. The slicer (or calling agent) returns a revised version of the SAME decomposition; the critic re-scores once. If viable → APPROVE. If still FAILs or net more WARNs → BLOCK; do not loop again. The decision is locked by ADR-0003 D3.

## WARN-flagged → captured issue

When WARN-flagging an item for follow-up (criterion 9 cascade-doc check, criterion 10 cross-PR collision, or any other WARN), the critic MUST create a `captured`-labeled issue if the follow-up isn't already tracked, and immediately invoke `/promote-to-backlog <N>` per [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D3 inline-firing. Mandatory per CLAUDE.md rule #11; does not gate APPROVE.

## Relationship to other agents

- **Sequential partner to** [`slicer`](slicer.md). The slicer generates N=3; this critic scores best-of-N + single revision. The pair together fills stages 3.5 + 3.6 of `/ship`.
- **Sibling critic of** [`reviewer`](reviewer.md), [`prd-critic`](../../../.claude/agents/prd-critic.md), [`adr-critic`](../../../.claude/agents/adr-critic.md), [`glossary-critic`](../../../.claude/agents/glossary-critic.md), [`backlog-critic`](../../../.claude/agents/backlog-critic.md). All 6 critics conform to the same verdict template + CRITIC trailer ([[topics/output-shapes]]); the slicer-critic is the only one that doubles as a generator (the "Final approved decomposition" extension is the generator-shaped output `/to-issues` posts on APPROVE).
- **Honors the 6-critic-cap** per [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7.
- **Authority:** [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D3 (best-of-N + single revision shape), [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D1 (output shape), [ADR-0013](../../../decisions/0013-slicer-n3-contract-refined.md) D2/D3 (N=1 acceptance).

## Edges

- **part_of:** [[concepts/rules/sc-invest]]
- **part_of:** [[concepts/rules/sc-walking-skeleton]]
- **part_of:** [[concepts/rules/sc-spidr-splitability]]
- **part_of:** [[concepts/rules/sc-no-non-goals]]
- **part_of:** [[concepts/rules/sc-no-rabbit-holes]]
- **part_of:** [[concepts/rules/sc-dep-ordering]]
- **part_of:** [[concepts/rules/sc-slice-count-loc]]
- **part_of:** [[concepts/rules/sc-risk-front-loading]]
- **part_of:** [[concepts/rules/sc-cascade-docs-covered]]
- **part_of:** [[concepts/rules/sc-cross-pr-collision]]
- **related_to:** [[entities/subagents/slicer]]
- **related_to:** [[entities/subagents/reviewer]]
- **part_of:** [[topics/pipeline-stages]]
- **related_to:** [[topics/output-shapes]]
- **related_to:** [[patterns/cascade-doc-check]]
- **related_to:** [[patterns/n1-degenerate-carveout]]
- **related_to:** [[concepts/glossary/critic]]
