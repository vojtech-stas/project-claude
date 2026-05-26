---
title: N=1 degenerate carveout — slicer self-restraint when N=3 would produce only cosmetic variation
summary: The slicer's pattern of emitting N=1 alternative decomposition (instead of the default N=3) when all candidate decompositions would have bit-identical post-merge end-state, accompanied by explicit rationale answering three required questions.
tags: [pattern, slicing, slicer, slicer-critic]
type: pattern
last_updated: 2026-05-26
sources:
  - decisions/0013-slicer-n3-contract-refined.md D1
  - decisions/0013-slicer-n3-contract-refined.md D3
  - .claude/agents/slicer-critic.md (N=1 acceptance section)
  - decisions/0003-autonomous-pipeline-with-critics.md D3
---

# N=1 degenerate carveout

The slicer's pattern of self-restraint: emit a single alternative decomposition (N=1) instead of the default N=3 when the slicer judges all candidate decompositions would have bit-identical post-merge end-state. Per [ADR-0013](../../../decisions/0013-slicer-n3-contract-refined.md) D1, N=1 is a **legal input** for the [`slicer-critic`](../../../.claude/agents/slicer-critic.md) when accompanied by explicit rationale; D3 specifies the rationale must answer three required questions.

This is a partial supersession of [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D3's strict N=3 contract; the single-revision-loop semantics of D3 are preserved unchanged.

## What

The default contract from ADR-0003 D3 is N=3 alternative decompositions per PRD. ADR-0013 D1 carves out a degenerate case: when the slicer determines that **all candidate decompositions would converge to the same merged end-state** (e.g., the PRD's shape is locked by §4 appetite or §5 solution sketch with no meaningful variation axis), the slicer MAY emit N=1 with explicit rationale.

The three required rationale questions per [ADR-0013](../../../decisions/0013-slicer-n3-contract-refined.md) D3:

1. **What PRD section locks the shape?** (typically §4 Appetite or §5 Solution sketch)
2. **What variation axis was considered and rejected as non-meaningful?** (e.g., commit-ordering inside squash; trivial rewording; slice-count differences that don't change end-state)
3. **Would N=3 have produced genuinely-different alternatives, or only cosmetic variation?**

If the rationale is concrete on all three points, slicer-critic accepts and scores the single decomposition normally against the 10-criterion rubric (criteria 1-10 apply identically to a single decomposition).

If the rationale is vague ("only one way to do it" with no PRD citation), slicer-critic biases toward **requesting one revision** asking for the explicit rationale before scoring.

## Why

ADR-0013 added the carveout because **ADR-0003 D3's strict N=3 produces busywork on degenerate cases**. A PRD that explicitly locks its shape (e.g., "thin file X to ≤N lines per Y rule") admits no meaningful slicing variation: alternatives A/B/C would all merge to the same files-changed state. Forcing the slicer to fabricate three variants generates cosmetic differences (different commit ordering, different per-slice wording) that consume slicer/slicer-critic tokens and human review time without producing decision value.

The three-question rationale exists to **prevent slicer laziness from masquerading as degeneracy**. A slicer that lazily declares N=1 to skip the work of producing real alternatives degrades the project's exploration. The questions force concrete justification: which PRD section locks shape, which axis was rejected, would the rejected axis have produced genuinely-different alternatives. Without explicit answers, slicer-critic asks for the rationale before scoring.

Default bias should still favor N=3 unless the slicer is certain — the carveout is opt-in for genuinely degenerate cases, not a license to default-to-N=1.

## How to apply

Slicer side (when emitting N=1):

1. Verify the PRD's §4 Appetite or §5 Solution sketch unambiguously locks the slicing shape.
2. Identify the variation axis you considered (commit-ordering? slice-count? interface-split direction?) and why you rejected it as non-meaningful.
3. Confirm that N=3 alternatives would have been bit-identical post-squash-merge.
4. Emit the single decomposition with a "Rationale for N=1" block answering all three questions explicitly.

Slicer-critic side (when receiving N=1):

1. Read the rationale block; check all three questions are answered concretely.
2. If concrete → score the single decomposition normally against the 10-criterion rubric.
3. If vague → request one round of revision asking for the explicit rationale BEFORE scoring (per prd-critic recommendation on PRD #116).
4. Do NOT BLOCK on "didn't produce N=3" when N=1 has rationale.

## Examples

- **PRD #253 T2 reviewer-thinning slice 3** — slicer emitted N=1 with rationale: "§4 Appetite locks the thinning target; variation axis = commit ordering rejected as non-meaningful (all squash-merge identically); N=3 would have produced cosmetic variation only". Slicer-critic accepted, scored normally.
- **Hypothetical lazy N=1**: slicer emits "only one way to do this" with no PRD citation, no variation axis named → slicer-critic requests revision asking for explicit rationale per ADR-0013 D3.

## When NOT to use

- **Genuinely-open-shape PRDs** — if the PRD's §5 solution sketch lists multiple plausible directions, N=3 remains the default per ADR-0003 D3 (the unsuper­seded part).
- **PRDs introducing new subagents/skills** — interface variation is real; N=3 produces meaningfully different decompositions.
- **First slice of any complex PRD** — walking-skeleton boundary often has real variation in how layers cut; default to N=3.

## Edges

- **part_of:** [[entities/subagents/slicer]]
- **related_to:** [[entities/subagents/slicer-critic]]
- **related_to:** [[concepts/rules/sc-invest]]
- **related_to:** [[patterns/walking-skeleton]]
