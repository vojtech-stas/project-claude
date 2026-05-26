---
title: to-prd — PRD authoring skill with embedded critic loop and macro-ADR drafting
summary: Stage-2 PRD authoring skill that synthesizes grilled context into the canonical 6-section PRD template, drafts any warranted macro-ADR alongside, and runs prd-critic (+ adr-critic if ADR drafted) in a ≤3-round joint-APPROVE loop before publishing via gh issue create.
tags: [skill, pipeline, generator, to-prd]
type: entity
last_updated: 2026-05-27
sources:
  - .claude/skills/to-prd/SKILL.md
  - decisions/0003-autonomous-pipeline-with-critics.md
  - decisions/0004-bypass-prevention.md
---

# /to-prd

The `/to-prd` skill is the **PRD authoring stage** of the autonomous pipeline. It synthesizes the current conversation context (typically a recently-settled `/grill-me` session) into the canonical 6-section PRD template, optionally drafts a macro-ADR alongside, runs the relevant critic(s) in a ≤3-round APPROVE/BLOCK loop, and publishes the result to GitHub on joint-APPROVE. It does NOT interview the user — synthesis only.

## Role and responsibility

`/to-prd` has three jobs, in order:

1. **Synthesize the PRD** from conversation context and repo state, using the canonical 6-section template (Problem / Goal / Non-goals / Appetite / Solution sketch / Rabbit-holes & Open questions). This skill is the canonical home of the PRD template; CLAUDE.md links here and does not restate it.
2. **Decide if a macro-ADR is warranted** per the heuristic in [`decisions/README.md`](../../../decisions/README.md) — write one iff the decision was hard, constrains future work, or a future maintainer would ask "why did they do it this way?". If yes, draft the ADR markdown in parallel using `decisions/README.md` conventions; number it as the next unused integer. ADRs ship as files in slice 1's PR per [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D8, not as separate issues.
3. **Run the critic loop and publish on APPROVE.** Invoke `prd-critic` always; invoke `adr-critic` in parallel under a **shared round counter** when a macro-ADR was drafted (per [ADR-0004](../../../decisions/0004-bypass-prevention.md) D1). Both must APPROVE in the same round before publishing — the joint-APPROVE gate.

## Invocation contract

- **Caller:** the user via `/to-prd`, or the [`/ship`](ship.md) orchestrator at stage 2.
- **Input:** the current conversation context (no positional arguments). The skill reads the prior `/grill-me` discussion and existing repo state.
- **Output:** a posted PRD GitHub Issue with the `prd` label and the canonical 6-section body, plus any drafted ADR file(s) written to `decisions/NNNN-<slug>.md` (committed by slice 1 of the resulting implementation, not separately). PRD body ends with the `> **Pipeline metadata** — Approved by prd-critic round <N>/3` audit-trail footer.
- **Tool boundaries:** main-agent context. Uses `Read`, `Grep`, `Glob`, `Bash` (`gh issue create`), `Write` (ADR file authoring), `Agent` (critic dispatch).

## Joint-APPROVE gate and shared round counter

Per [ADR-0004](../../../decisions/0004-bypass-prevention.md) D1, when both critics are invoked they share a **single round number** (Option A — shared round counter). If either returns BLOCK on round N, the loop revises and re-invokes BOTH critics on round N+1 (even if one already APPROVED — the re-revision may have invalidated its prior verdict). Round-3 escalation triggers when EITHER critic returns BLOCK on round 3. Rationale: simpler invariant; conservative; matches existing `prd-critic` semantics byte-for-byte for the PRD-only case (no ADR drafted → `adr-critic` not invoked → behavior unchanged).

On round-3 BLOCK or `ESCALATE: needs-human` in either verdict: STOP, do NOT post the PRD, do NOT commit the ADR. Apply `needs-human` per the I5 escalation pattern and surface both verdicts to the user.

## The 6-section PRD template (canonical location)

This skill is the canonical home of the template. See [`.claude/skills/to-prd/SKILL.md`](../../../.claude/skills/to-prd/SKILL.md) for the full template text. The 6 sections are:

1. **Problem** — who is hurting, how, and why now.
2. **Goal / Success criteria** — single observable outcome plus mechanically-verifiable checklist.
3. **Non-goals / Out of scope** — bulleted, with one-line reasons.
4. **Appetite / Constraints** — slice budget, time appetite, per-slice LoC cap, dep stance.
5. **Solution sketch** — coarse module shape; walking-skeleton slice 1 named.
6. **Rabbit-holes & Open questions** — explicit traps + genuinely unresolved questions.

## Relationship to other skills and agents

- **Called by** [`/ship`](ship.md) at stage 2; can also be invoked directly by the user.
- **Invokes** [`prd-critic`](../subagents/prd-critic.md) always, and [`adr-critic`](../subagents/adr-critic.md) in parallel when a macro-ADR is drafted.
- **Upstream consumer of** `/grill-me` output (conversation context).
- **Downstream producer for** [`/to-issues`](to-issues.md) (consumes the posted PRD at stage 3).
- **Honors the 6-critic-cap** per [ADR-0008](../../../decisions/0008-workflow-autolog-bootstrap-and-naming.md) D7 — `/to-prd` is a skill, not a critic; its gates are `prd-critic` + `adr-critic`.
- **Authority:** [ADR-0003](../../../decisions/0003-autonomous-pipeline-with-critics.md) D2 (critic loop pattern), D6 (skill vs subagent), D8 (ADR placement); [ADR-0004](../../../decisions/0004-bypass-prevention.md) D1 (adr-critic exists, joint-APPROVE), D2 (bootstrap-mode).

## Edges

- **part_of:** [[topics/pipeline-stages]]
- **related_to:** [[entities/skills/ship]]
- **related_to:** [[entities/skills/to-issues]]
- **related_to:** [[entities/subagents/prd-critic]]
- **related_to:** [[entities/subagents/adr-critic]]
- **related_to:** [[concepts/glossary/prd]]
- **related_to:** [[concepts/glossary/adr]]
- **related_to:** [[concepts/glossary/joint-approve-gate]]
- **related_to:** [[topics/output-shapes]]
