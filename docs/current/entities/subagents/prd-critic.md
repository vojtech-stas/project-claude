---
title: prd-critic — adversarial auditor of draft PRDs against the 6-section template + rubric
summary: Reads a draft PRD (and any macro-ADRs drafted alongside); applies the prd-critic rubric; emits APPROVE on publishable PRDs and BLOCK with itemized findings the generator can mechanically address; default-conservative when uncertain.
tags: [subagent, critic, gate, prd-critic]
type: entity
last_updated: 2026-05-26
sources:
  - .claude/agents/prd-critic.md
  - decisions/0003-autonomous-pipeline-with-critics.md
  - decisions/0004-bypass-prevention.md
  - decisions/0005-output-shape-and-slicing-methodology.md
  - decisions/0009-discipline-tightening.md
---

# prd-critic

The `prd-critic` subagent is the **adversarial gate at stage 2.6** of the autonomous pipeline. It receives a draft PRD (and any macro-ADRs drafted alongside per [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D8), applies the prd-critic rubric, and emits APPROVE (the [`/to-prd`](../../../.claude/skills/to-prd/SKILL.md) skill then posts the PRD as a GitHub Issue) or BLOCK (with itemized findings the generator mechanically addresses in a ≤3-round revision loop). When a macro-ADR is drafted alongside, prd-critic and [`adr-critic`](adr-critic.md) form a **joint-APPROVE gate** per [ADR-0004](../../../decisions/0004-bypass-prevention.md) D1 — BOTH must APPROVE before `/to-prd` posts anything.

This entity note is the **canonical full role synthesis** for the prd-critic subagent. After the T4 knowledge-architecture migration ([ADR-0031](../../../decisions/0031-knowledge-architecture-v2.md) D10 step 4 of 9, PRD #283 slice 1), the operational [`.claude/agents/prd-critic.md`](../../../.claude/agents/prd-critic.md) carries only the prompt-level operational mechanics (mandatory reading order, rubric trigger lines, output-format pointer, tool boundaries, conduct) and links here for the rubric-criterion full bodies (each shipped as a `docs/current/concepts/rules/pc-*.md` atomic note), the iteration shape, the ADR-existence sub-check rationale, and the joint-gate relationship to `adr-critic`.

## Role and responsibility

The prd-critic has two jobs, in strict priority order:

1. **Hard-block** any draft PRD that violates a rubric criterion. Emit itemized findings the `/to-prd` generator can mechanically address.
2. **Recommend** non-blocking improvements after the verdict body, before the trailer (the canonical `Recommendations` extension per [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D1).

It does NOT write or edit any file (including auto-creating a missing ADR — see "ADR existence sub-check" below). It does NOT post GitHub issues directly except to comment its verdict on an already-posted PRD; the `/to-prd` skill posts the PRD on APPROVE.

## Invocation contract

- **Caller:** the [`/to-prd`](../../../.claude/skills/to-prd/SKILL.md) skill (typically dispatched via [`/ship`](../../../.claude/skills/ship/SKILL.md) stage 2), or any agent/human via the `Agent` tool with `subagent_type: "prd-critic"`.
- **Input:** EITHER a draft PRD as inline markdown (typical — invoked before the issue is posted) AND optionally one or more draft ADRs alongside, OR a posted PRD issue reference (e.g., `vojtech-stas/project-claude#NN`) which prd-critic fetches via `gh issue view`. Plus the round number (1, 2, or 3); if omitted, assume round 1.
- **Output:** the canonical verdict template per [[topics/output-shapes]] — 5-section body (Header → Subject of review → Rubric → Findings → Summary) + optional Recommendations extension + CRITIC trailer. Either posted as a comment on the PRD issue via `gh issue comment` if already posted, OR returned inline to the calling agent if the PRD is still a draft.
- **Tool boundaries:** `Read`, `Glob`, `Grep`, `Bash` (read-only `gh issue view/list/comment` + `git log decisions/` + `ls decisions/`). NOT authorized: `Write`/`Edit`, `gh issue create` / `gh issue edit` / `gh issue close`, branch creation, agent invocation.

## Iteration shape — ≤3-round APPROVE/BLOCK loop with escalation

Per [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D2, the iteration shape matches the project's standard critic loop:

- **Max 3 rounds** of APPROVE/BLOCK.
- Each BLOCK emits an itemized findings list the generator can mechanically address.
- **Round-3 BLOCK escalates** via the `needs-human` label on the draft (or posted PRD issue if already posted) AND a summary comment on the parent grill-session context, matching the I5 escalation surface used by `slicer-critic` and `reviewer`.

Default-conservative: when uncertain about any rubric criterion, BLOCK per [ADR-0009](../../../decisions/0009-discipline-tightening.md) D3 (generalizes [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D2's pattern to all critics). Adversarial mindset is a lens for ordering rubric scrutiny, not a license to invent new failure modes beyond the rubric per [ADR-0009](../../../decisions/0009-discipline-tightening.md) D4.

## Rubric

Each linked rule note expands the criterion's What / Why / How-to-check / Examples. The atomic-note layer is the canonical home; the [`prd-critic.md`](../../../.claude/agents/prd-critic.md) executable shell quotes each criterion's name + one-line trigger only.

1. [[concepts/rules/pc-prd-completeness]] — all six PRD template sections present and concretely populated
2. [[concepts/rules/pc-acceptance-mechanically-verifiable]] — every Goal bullet is bash-checkable OR JUDGMENT-extractable at merge
3. [[concepts/rules/pc-non-goals-explicit]] — Non-goals are named specifically with one-line reasons
4. [[concepts/rules/pc-appetite-bounded]] — Appetite is concrete and coheres with the Solution sketch's scope
5. [[concepts/rules/pc-rabbit-holes-named]] — Rabbit-holes + Open questions both surfaced; no hallucinated answers
6. [[concepts/rules/pc-solution-sketch-actionable]] — Solution sketch enumerates work-units the slicer can decompose; stays within stated feature; implies walking-skeleton slice-1

## ADR consistency sub-check (carried in this entity note pending future atomic note)

In addition to the 6 atomic rule notes above, prd-critic enforces an **ADR-consistency** check the slice body did not factor into its own atomic note: the PRD must not contradict any accepted ADR, and any PRD that references an ADR by number (e.g., "per ADR-0007") MUST cite an ADR file that exists on `origin/main`. If a referenced ADR is missing, prd-critic BLOCKs with the **literal finding** `"ADR-XXXX referenced but not present"` (substituting the actual number).

**Resolved per PRD #3 §6 OQ#3 — BLOCK, do not auto-create.** Auto-creating an ADR is a side-effect that pulls the critic outside its review-only contract (analogous to `reviewer` not editing code per [ADR-0002](../../../decisions/0002-autonomous-merge-policy.md)). It also masks a real generator bug — `/to-prd` should never emit a reference it didn't draft. BLOCK keeps the critic focused, surfaces the bug, and lets `/to-prd` either draft the missing ADR (per [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D8 macro-ADR placement) or fix the reference. A single-finding BLOCK costs one round of regeneration; an undetected dangling reference costs trust in the whole pipeline.

**Stale-worktree mitigation.** ALWAYS use `gh api repos/{owner}/{repo}/contents/decisions/<file>.md` to check ADR file existence on origin/main, NOT local `ls decisions/`. The worktree's local `decisions/` may be stale (this is a common stale-worktree false-alarm pattern — 3+ instances observed 2026-05-20/21). Only trust `gh api` results.

## Joint-APPROVE gate with adr-critic

When `/to-prd` drafts a macro-ADR alongside the PRD (per ADR-0003 D8 macro-ADR placement), prd-critic and [`adr-critic`](adr-critic.md) form a **joint-APPROVE gate** per [ADR-0004](../../../decisions/0004-bypass-prevention.md) D1: BOTH must APPROVE before `/to-prd` posts anything. Either BLOCK gates publication. The two critics run in parallel (no ordering); each scores its own rubric independently. The joint gate exists because PRD-level concerns (scope, appetite, non-goals) and ADR-level concerns (convention compliance, cross-ADR consistency, supersession) are orthogonal — and either failure mode would silently ship if only one critic gated.

## Open-question → captured issue convention

When an Open question surfaces during PRD review that warrants future-PRD treatment, prd-critic MUST create a `captured`-labeled GitHub Issue to track it and immediately invoke `/promote-to-backlog <N>` per [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D3 inline-firing convention. Mandatory per CLAUDE.md rule #11; the autopilot's [`backlog-critic`](backlog-critic.md) decides quality downstream, not the prd-critic.

## Relationship to other agents

- **Joint-gate partner of** [`adr-critic`](adr-critic.md). Both must APPROVE before `/to-prd` posts per [ADR-0004](../../../decisions/0004-bypass-prevention.md) D1.
- **Sibling critic of** [`reviewer`](reviewer.md), [`slicer-critic`](slicer-critic.md), [`adr-critic`](adr-critic.md), [`glossary-critic`](../../../.claude/agents/glossary-critic.md), [`backlog-critic`](../../../.claude/agents/backlog-critic.md). All 6 critics conform to the same verdict template + CRITIC trailer ([[topics/output-shapes]]).
- **Honors the 6-critic-cap** per [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7.
- **Authority:** [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D2 (critic loop pattern), [ADR-0004](../../../decisions/0004-bypass-prevention.md) D1 (joint gate), [ADR-0005](../../../decisions/0005-output-shape-and-slicing-methodology.md) D1 (output shape), [ADR-0009](../../../decisions/0009-discipline-tightening.md) D3/D4 (default-BLOCK + adversarial-mindset bounding).

## Edges

- **part_of:** [[concepts/rules/pc-prd-completeness]]
- **part_of:** [[concepts/rules/pc-acceptance-mechanically-verifiable]]
- **part_of:** [[concepts/rules/pc-non-goals-explicit]]
- **part_of:** [[concepts/rules/pc-appetite-bounded]]
- **part_of:** [[concepts/rules/pc-rabbit-holes-named]]
- **part_of:** [[concepts/rules/pc-solution-sketch-actionable]]
- **related_to:** [[entities/subagents/adr-critic]]
- **related_to:** [[entities/subagents/slicer-critic]]
- **related_to:** [[entities/subagents/reviewer]]
- **part_of:** [[topics/pipeline-stages]]
- **related_to:** [[topics/output-shapes]]
- **related_to:** [[concepts/glossary/critic]]
- **related_to:** [[concepts/glossary/joint-approve-gate]]
- **related_to:** [[concepts/glossary/prd]]
